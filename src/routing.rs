use hashbrown::raw;
use rstar::RTreeObject;
use std::cmp::max;
use std::cmp::min;
use std::cmp::Reverse;
use std::collections::hash_map::DefaultHasher;
use std::collections::BinaryHeap;
use std::collections::HashMap;
use std::collections::HashSet;
use std::fs;
use std::hash::Hash;
use std::hash::Hasher;
use std::marker::PhantomData;
use std::ops::Index;
use std::ops::IndexMut;
use std::result;

use rand::rngs::StdRng;
use rand::Rng;
use rand::SeedableRng;
use serde_json::json;

use pyo3::prelude::*;
use rand::seq::SliceRandom;

use crate::geometry::Orientation;
use crate::geometry::PointLike;
use crate::{
    geometry::{BoundingBox, DirectedPoint, Direction, Neighborhood, PlacedRectangularNode, Point},
    pyindexset::PyIndexSet,
};

#[pyclass]
#[derive(Clone, PartialEq, Debug, Copy)]
pub struct RoutingConfig {
    neighborhood: Neighborhood,
}

#[pymethods]
impl RoutingConfig {
    #[new]
    fn new(neighborhood: Neighborhood) -> Self {
        RoutingConfig { neighborhood }
    }
}

impl Default for RoutingConfig {
    fn default() -> Self {
        RoutingConfig {
            neighborhood: Neighborhood::Orthogonal,
        }
    }
}

impl RTreeObject for PlacedRectangularNode {
    type Envelope = rstar::AABB<Point>;

    fn envelope(&self) -> Self::Envelope {
        let top_left = self.top_left();
        let bottom_right = self.bottom_right();
        rstar::AABB::from_corners(
            Point {
                x: top_left.x,
                y: top_left.y,
            },
            Point {
                x: bottom_right.x,
                y: bottom_right.y,
            },
        )
    }
}

#[pyclass]
#[derive(Clone, PartialEq, Debug)]
pub struct EdgeRoutingResult {
    pub path: Vec<DirectedPoint>,
}

#[pymethods]
impl EdgeRoutingResult {
    #[new]
    fn new(path: Vec<DirectedPoint>) -> Self {
        EdgeRoutingResult { path }
    }

    #[getter]
    fn get_path(&self) -> Vec<DirectedPoint> {
        self.path.clone()
    }
}

#[pyclass]
#[derive(Clone, PartialEq, Debug)]
pub struct EdgeRoutingsResult {
    pub paths: Vec<Vec<DirectedPoint>>,
}

/// Wrapper around a routed path of grid points that provides helper iteration methods.
#[allow(dead_code)]
#[derive(Clone, PartialEq, Debug)]
pub struct Path {
    pub points: Vec<Point>,
}

#[derive(Clone, PartialEq, Debug)]
pub struct PathWithEndpoints {
    pub path: Path,
    pub start: DirectedPoint,
    pub end: DirectedPoint,
}

impl Path {
    pub fn new(points: Vec<Point>) -> Self {
        Path { points }
    }

    pub fn as_slice(&self) -> &[Point] {
        &self.points
    }

    pub fn into_inner(self) -> Vec<Point> {
        self.points
    }

    /// Iterate over segment indices without counting consecutive duplicates.
    pub fn segments<'a>(&'a self, raw_area: &'a RawArea) -> PathSegments<'a> {
        PathSegments::new(self, raw_area)
    }

    /// Iterate over raw grid points where the path turns.
    pub fn corners<'a>(&'a self, raw_area: &'a RawArea) -> PathCorners<'a> {
        PathCorners::new(self, raw_area)
    }
}

impl PathWithEndpoints {
    pub fn new(path: Path, start: DirectedPoint, end: DirectedPoint) -> Self {
        PathWithEndpoints { path, start, end }
    }

    pub fn segments<'a>(&'a self, raw_area: &'a RawArea) -> PathSegments<'a> {
        self.path.segments(raw_area)
    }

    pub fn corners<'a>(&'a self, raw_area: &'a RawArea) -> PathCorners<'a> {
        self.path.corners(raw_area)
    }

    pub fn to_directed_points(&self) -> Vec<DirectedPoint> {
        self.point_path_to_directed_points()
    }

    fn point_path_to_directed_points(&self) -> Vec<DirectedPoint> {
        let mut result_path = Vec::new();

        for window in self.path.points.windows(2) {
            let window_start = window[0];
            let window_end = window[1];

            // Skip duplicate points.
            if window_start == window_end {
                continue;
            }

            if window_start.x == window_end.x {
                // Vertical segment
                let direction = if window_end.y < window_start.y {
                    Direction::Up
                } else {
                    Direction::Down
                };
                let direction_offset = if direction == Direction::Up { -1 } else { 1 };

                result_path.push(DirectedPoint {
                    x: window_start.x,
                    y: window_start.y,
                    direction: if result_path.is_empty() {
                        self.start.direction
                    } else {
                        direction
                    },
                    debug: false,
                });

                for y in 1..=(window_end.y - window_start.y).abs() {
                    result_path.push(DirectedPoint {
                        x: window_start.x,
                        y: window_start.y + y * direction_offset,
                        direction: direction.opposite(),
                        debug: false,
                    });
                }
            } else if window_start.y == window_end.y {
                // Horizontal segment
                let direction = if window_end.x > window_start.x {
                    Direction::Right
                } else {
                    Direction::Left
                };

                result_path.push(DirectedPoint {
                    x: window_start.x,
                    y: window_start.y,
                    direction: if result_path.is_empty() {
                        self.start.direction
                    } else {
                        direction
                    },
                    debug: false,
                });

                let direction_offset = if direction == Direction::Left { -1 } else { 1 };
                for x in 1..=(window_end.x - window_start.x).abs() {
                    result_path.push(DirectedPoint {
                        x: window_start.x + x * direction_offset,
                        y: window_start.y,
                        direction: direction.opposite(),
                        debug: false,
                    });
                }
            } else {
                // Diagonals should not occur.
            }
        }

        // Add final endpoint.
        result_path.push(DirectedPoint {
            x: self.end.x,
            y: self.end.y,
            direction: self.end.direction.opposite(),
            debug: false,
        });

        result_path
    }
}

pub struct PathSegments<'a> {
    indices: Vec<usize>,
    position: usize,
    _phantom: PhantomData<&'a ()>,
}

impl<'a> PathSegments<'a> {
    fn new(path: &'a Path, raw_area: &'a RawArea) -> Self {
        let mut indices = Vec::new();

        for window in path.points.windows(2) {
            let from = window[0];
            let to = window[1];

            // Skip duplicate points.
            if (from.x, from.y) == (to.x, to.y) {
                continue;
            }

            // Only handle Manhattan steps.
            if from.x != to.x && from.y != to.y {
                continue;
            }

            let step_x = (to.x - from.x).signum();
            let step_y = (to.y - from.y).signum();
            let steps = (to.x - from.x).abs().max((to.y - from.y).abs());

            let mut current = from;
            for _ in 0..steps {
                let next = Point {
                    x: current.x + step_x,
                    y: current.y + step_y,
                };

                if let Some(idx) = raw_area.segment_index_between(&current, &next) {
                    if indices.last().copied() != Some(idx) {
                        indices.push(idx);
                    }
                }
                current = next;
            }
        }

        PathSegments {
            indices,
            position: 0,
            _phantom: PhantomData,
        }
    }
}

pub struct PathCorners<'a> {
    indices: Vec<usize>,
    position: usize,
    _phantom: PhantomData<&'a ()>,
}
impl<'a> Iterator for PathSegments<'a> {
    type Item = usize;

    fn next(&mut self) -> Option<Self::Item> {
        if self.position >= self.indices.len() {
            return None;
        }
        let idx = self.indices[self.position];
        self.position += 1;
        Some(idx)
    }
}

impl<'a> PathCorners<'a> {
    fn new(path: &Path, raw_area: &RawArea) -> Self {
        let mut indices = Vec::new();
        let mut prev_dir: Option<(i32, i32)> = None;

        for window in path.points.windows(2) {
            let from = window[0];
            let to = window[1];

            let dx = to.x - from.x;
            let dy = to.y - from.y;

            // Only consider Manhattan steps.
            if dx != 0 && dy != 0 {
                prev_dir = None;
                continue;
            }
            let dir = (dx.signum(), dy.signum());

            if let Some(prev) = prev_dir {
                if prev != dir {
                    if let Some(raw_idx) = raw_area.point_to_raw_point(&from) {
                        let idx = raw_idx.0 as usize;
                        if indices.last().copied() != Some(idx) {
                            indices.push(idx);
                        }
                    }
                }
            }

            prev_dir = Some(dir);
        }

        PathCorners {
            indices,
            position: 0,
            _phantom: PhantomData,
        }
    }
}

impl<'a> Iterator for PathCorners<'a> {
    type Item = usize;

    fn next(&mut self) -> Option<Self::Item> {
        if self.position >= self.indices.len() {
            return None;
        }
        let idx = self.indices[self.position];
        self.position += 1;
        Some(idx)
    }
}

#[pymethods]
impl EdgeRoutingsResult {
    #[new]
    fn new(paths: Vec<Vec<DirectedPoint>>) -> Self {
        EdgeRoutingsResult { paths }
    }

    #[getter]
    fn get_paths(&self) -> Vec<Vec<DirectedPoint>> {
        self.paths.clone()
    }
}

#[derive(Clone, Hash)]
pub struct RawArea {
    pub top_left: Point,
    pub bottom_right: Point,
}

impl RawArea {
    pub fn width(&self) -> i32 {
        self.bottom_right.x - self.top_left.x + 1
    }

    pub fn height(&self) -> i32 {
        self.bottom_right.y - self.top_left.y + 1
    }

    pub fn size(&self) -> usize {
        (self.width() * self.height()) as usize
    }

    pub fn num_segments(&self) -> usize {
        ((self.width() - 1) * self.height() + (self.height() - 1) * self.width()) as usize
    }

    pub fn point_to_raw_point(&self, point: &Point) -> Option<RawPoint> {
        if point.x < self.top_left.x
            || point.x > self.bottom_right.x
            || point.y < self.top_left.y
            || point.y > self.bottom_right.y
        {
            return None;
        }
        Some(RawPoint(
            ((point.x - self.top_left.x) + (point.y - self.top_left.y) * (self.width())) as u32,
        ))
    }

    pub fn raw_index_to_point(&self, raw_index: usize) -> Point {
        let width = self.width() as usize;
        let x = raw_index % width;
        let y = raw_index / width;
        Point {
            x: self.top_left.x + x as i32,
            y: self.top_left.y + y as i32,
        }
    }

    pub fn segment_index_between(&self, from: &Point, to: &Point) -> Option<usize> {
        let dx = to.x - from.x;
        let dy = to.y - from.y;

        // Grid coordinates relative to top-left.
        let grid_from_x = from.x - self.top_left.x;
        let grid_from_y = from.y - self.top_left.y;

        if dx == 1 && dy == 0 {
            // Right
            Some((grid_from_y * (self.width() - 1) + grid_from_x) as usize)
        } else if dx == -1 && dy == 0 {
            // Left
            Some((grid_from_y * (self.width() - 1) + (grid_from_x - 1)) as usize)
        } else if dx == 0 && dy == 1 {
            // Down
            Some(
                ((self.width() - 1) * self.height()
                    + grid_from_x * (self.height() - 1)
                    + grid_from_y) as usize,
            )
        } else if dx == 0 && dy == -1 {
            // Up
            Some(
                ((self.width() - 1) * self.height()
                    + grid_from_x * (self.height() - 1)
                    + (grid_from_y - 1)) as usize,
            )
        } else {
            None
        }
    }
    pub fn edge_prefix_sums<T>(
        &self,
        edge_buffer: &Vec<T>,
        prefix_x: &mut Vec<T>,
        prefix_y: &mut Vec<T>,
    ) where
        T: Copy + Default + std::ops::AddAssign,
    {
        let width = self.width() as usize;
        let height = self.height() as usize;
        let num_edges = self.num_segments();

        assert!(prefix_x.len() == (width * height) as usize);
        assert!(prefix_y.len() == (width * height) as usize);

        // Fill horizontal prefix sums
        for y in 0..height {
            let mut sum: T = T::default();
            prefix_x[y * width] = sum;
            for x in 0..(width - 1) {
                let edge_index = (y * (width - 1) + x) as usize;
                let prefix_index = y * width + x + 1;
                sum += edge_buffer[edge_index];
                prefix_x[prefix_index] = sum;
            }
        }

        // Fill vertical prefix sums
        for x in 0..width {
            let mut sum: T = T::default();
            prefix_y[x] = sum;
            for y in 0..(height - 1) {
                let edge_index = ((width - 1) * height + x * (height - 1) + y) as usize;
                let prefix_index = (y + 1) * width + x;
                sum += edge_buffer[edge_index];
                prefix_y[prefix_index] = sum;
            }
        }
    }
}

#[derive(Clone, Hash, Default)]
pub struct Grid {
    pub min_x: i32,
    pub min_y: i32,
    pub max_x: i32,
    pub max_y: i32,
    pub width: usize,
    pub height: usize,
    pub size: usize,
    pub num_segments: usize,
    pub x_lines: Vec<i32>,
    pub y_lines: Vec<i32>,
}

#[repr(transparent)]
#[derive(Copy, Clone, Eq, PartialEq, Ord, PartialOrd, Hash, Default, Debug)]
pub struct RawPoint(pub u32);

#[repr(transparent)]
#[derive(Copy, Clone, Eq, PartialEq, Ord, PartialOrd, Hash, Default, Debug)]
pub struct RawSegment(pub u32);

#[repr(transparent)]
#[derive(Copy, Clone, Eq, PartialEq, Ord, PartialOrd, Hash, Default, Debug)]
pub struct GridPoint(pub u32);

impl<T> Index<GridPoint> for Vec<T> {
    type Output = T;

    fn index(&self, index: GridPoint) -> &Self::Output {
        &self[index.0 as usize]
    }
}

impl<T> IndexMut<GridPoint> for Vec<T> {
    fn index_mut(&mut self, index: GridPoint) -> &mut Self::Output {
        &mut self[index.0 as usize]
    }
}

#[repr(transparent)]
#[derive(Copy, Clone, Eq, PartialEq, Ord, PartialOrd, Hash, Default)]
pub struct GridSegment(pub u32);

impl Grid {
    pub fn new(width: usize, height: usize, x_lines: Vec<i32>, y_lines: Vec<i32>) -> Self {
        Grid {
            min_x: x_lines[0],
            min_y: y_lines[0],
            max_x: x_lines[width - 1],
            max_y: y_lines[height - 1],
            width,
            height,
            size: width * height,
            num_segments: (width - 1) * height + (height - 1) * width,
            x_lines,
            y_lines,
        }
    }

    pub fn from_edges_and_nodes(
        edges: &Vec<(Point, Point)>,
        nodes: &Vec<PlacedRectangularNode>,
    ) -> Self {
        // First we generate a grid from all start and end point projections and midpoints.

        // Instead of pushing into BinaryHeap repeatedly,
        // accumulate unique x and y coordinates in HashSets.
        let mut x_set = HashSet::new();
        let mut y_set = HashSet::new();

        for (start, end) in edges {
            x_set.insert(start.x);
            x_set.insert(end.x);
            y_set.insert(start.y);
            y_set.insert(end.y);
        }

        // Replace the original binary heaps with ones built from unique values.
        let mut x_coords: Vec<i32> = x_set.into_iter().collect();
        let mut y_coords: Vec<i32> = y_set.into_iter().collect();

        // Sort the coordinates
        // TODO we could do this more rust idiomatically
        x_coords.sort_unstable();
        y_coords.sort_unstable();
        x_coords.reverse();
        y_coords.reverse();

        // For each pair of consecutive coordinates, we add their midpoint.
        let mut x_lines = Vec::new();
        let mut y_lines = Vec::new();

        let mut last_x = None;

        while let Some(x) = x_coords.pop() {
            if let Some(last_x) = last_x {
                if last_x < x - 5 {
                    x_lines.push(last_x + 2);
                }
                if last_x < x - 1 {
                    x_lines.push((last_x + x) / 2);
                }
                if last_x < x - 5 {
                    x_lines.push(x - 2);
                }
            }
            x_lines.push(x);
            last_x = Some(x);
        }
        let mut last_y = None;
        while let Some(y) = y_coords.pop() {
            if let Some(last_y) = last_y {
                if last_y < y - 5 {
                    y_lines.push(last_y + 2);
                }
                if last_y < y - 1 {
                    y_lines.push((last_y + y) / 2);
                }
                if last_y < y - 5 {
                    y_lines.push(y - 2);
                }
            }
            y_lines.push(y);
            last_y = Some(y);
        }

        // Get the bounding box of all nodes
        let mut min_nodes_x = i32::MAX;
        let mut max_nodes_x = i32::MIN;
        let mut min_nodes_y = i32::MAX;
        let mut max_nodes_y = i32::MIN;

        nodes.iter().for_each(|node| {
            let tl = node.top_left();
            let br = node.bottom_right();
            min_nodes_x = min(min_nodes_x, tl.x);
            max_nodes_x = max(max_nodes_x, br.x);
            min_nodes_y = min(min_nodes_y, tl.y);
            max_nodes_y = max(max_nodes_y, br.y);
        });

        // We add some padding to the bounding box or use the min/max coordinates of the edges also padded.
        let padding = 3;
        let min_x = min(min_nodes_x - padding, x_lines[0] - padding);
        let max_x = max(max_nodes_x + padding, x_lines[x_lines.len() - 1] + padding);
        let min_y = min(min_nodes_y - padding, y_lines[0] - padding);
        let max_y = max(max_nodes_y + padding, y_lines[y_lines.len() - 1] + padding);

        // We add these to the grid keeping it sorted and unique.
        if !x_lines.contains(&min_x) {
            x_lines.insert(0, min_x);
        }
        if !x_lines.contains(&max_x) {
            x_lines.push(max_x);
        }
        if !y_lines.contains(&min_y) {
            y_lines.insert(0, min_y);
        }
        if !y_lines.contains(&max_y) {
            y_lines.push(max_y);
        }

        Grid::new(x_lines.len(), y_lines.len(), x_lines, y_lines)
    }

    fn raw_area(&self) -> RawArea {
        RawArea {
            top_left: Point {
                x: self.x_lines[0],
                y: self.y_lines[0],
            },
            bottom_right: Point {
                x: self.x_lines[self.width - 1],
                y: self.y_lines[self.height - 1],
            },
        }
    }

    fn is_valid_point(&self, point: GridPoint) -> bool {
        point.0 < self.size as u32
    }

    fn is_valid_segment(&self, segment: GridSegment) -> bool {
        segment.0 < self.num_segments as u32
    }

    fn grid_coords_to_segment_index(
        &self,
        grid_a: (usize, usize),
        grid_b: (usize, usize),
    ) -> usize {
        assert!(grid_a.0 < self.width);
        assert!(grid_a.1 < self.height);
        assert!(grid_b.0 < self.width);
        assert!(grid_b.1 < self.height);
        if grid_a.0 == grid_b.0 {
            // Vertical segment
            // If y differs by more than one, this is not a grid segment
            assert!(grid_a.1 + 1 == grid_b.1 || grid_b.1 + 1 == grid_a.1);
            let min_y = min(grid_a.1, grid_b.1);
            let x = grid_a.0;
            assert!(min_y < self.height - 1);
            (self.width - 1) * self.height + x * (self.height - 1) + min_y
        } else if grid_a.1 == grid_b.1 {
            // Horizontal segment
            let y = grid_a.1;
            // If x differs by more than one, this is not a grid segment
            assert!(grid_a.0 + 1 == grid_b.0 || grid_b.0 + 1 == grid_a.0);
            let min_x = min(grid_a.0, grid_b.0);
            assert!(min_x < self.width - 1);
            y * (self.width - 1) + min_x
        } else {
            panic!("Grid coordinates are not adjacent");
        }
    }

    fn grid_point_to_raw_point(&self, point: GridPoint) -> Option<RawPoint> {
        if !self.is_valid_point(point) {
            return None;
        }

        let grid_x = (point.0 % self.width as u32) as usize;
        let grid_y = (point.0 / self.width as u32) as usize;
        let x = self.x_lines[grid_x] as i32;
        let y = self.y_lines[grid_y] as i32;
        let raw_width = self.max_x - self.min_x + 1;
        Some(RawPoint(
            ((x - self.min_x) + (y - self.min_y) * raw_width) as u32,
        ))
    }

    fn grid_point_to_raw_coords(&self, point: GridPoint) -> Option<(i32, i32)> {
        if !self.is_valid_point(point) {
            return None;
        }
        let grid_x = (point.0 % self.width as u32) as usize;
        let grid_y = (point.0 / self.width as u32) as usize;
        let x = self.x_lines[grid_x];
        let y = self.y_lines[grid_y];
        Some((x, y))
    }

    fn grid_point_to_grid_coords(&self, point: GridPoint) -> Option<(usize, usize)> {
        if !self.is_valid_point(point) {
            return None;
        }
        let grid_x = (point.0 % self.width as u32) as usize;
        let grid_y = (point.0 / self.width as u32) as usize;
        Some((grid_x, grid_y))
    }

    fn grid_coords_to_grid_point(&self, grid_x: usize, grid_y: usize) -> Option<GridPoint> {
        if grid_x >= self.width || grid_y >= self.height {
            return None;
        }
        Some(GridPoint((grid_y * self.width + grid_x) as u32))
    }

    fn point_to_grid_point(&self, point: &Point) -> Option<GridPoint> {
        let grid_x = self.x_lines.binary_search(&point.x).ok()?;
        let grid_y = self.y_lines.binary_search(&point.y).ok()?;
        self.grid_coords_to_grid_point(grid_x, grid_y)
    }

    fn grid_point_to_point(&self, point: GridPoint) -> Option<Point> {
        let (grid_x, grid_y) = self.grid_point_to_grid_coords(point)?;
        Some(Point {
            x: self.x_lines[grid_x],
            y: self.y_lines[grid_y],
        })
    }

    fn raw_point_to_closest_grid_point(&self, point: RawPoint) -> Option<GridPoint> {
        let min_x = self.min_x;
        let min_y = self.min_y;
        let max_x = self.max_x;

        let raw_x = (point.0 % (max_x - min_x + 1) as u32) as i32 + min_x;
        let raw_y = (point.0 / (max_x - min_x + 1) as u32) as i32 + min_y;

        // Find the closest grid line for x and y
        let grid_x = match self.x_lines.binary_search(&(raw_x as i32)) {
            Ok(idx) => idx,
            Err(idx) => {
                if idx == 0 || idx >= self.width {
                    return None;
                }
                idx - 1
            }
        };
        let grid_y = match self.y_lines.binary_search(&(raw_y as i32)) {
            Ok(idx) => idx,
            Err(idx) => {
                if idx == 0 || idx >= self.height {
                    return None;
                }
                idx - 1
            }
        };

        Some(GridPoint((grid_y * self.width + grid_x) as u32))
    }
}

#[derive(Clone)]
struct MaskedGrid<'a> {
    grid: &'a Grid,
    point_mask: Vec<bool>,
    segment_mask: Vec<bool>,
}

impl<'a> MaskedGrid<'a> {
    fn node_grid_bounds(
        grid: &Grid,
        top_left: Point,
        bottom_right: Point,
    ) -> (usize, usize, usize, usize) {
        // Inclusive grid ranges that stay on/inside the node bounds.
        let min_grid_x = grid
            .x_lines
            .binary_search(&top_left.x)
            .unwrap_or_else(|idx| idx)
            .min(grid.width.saturating_sub(1));
        let max_grid_x = grid
            .x_lines
            .binary_search(&bottom_right.x)
            .map(|idx| idx)
            .unwrap_or_else(|idx| idx.saturating_sub(1))
            .min(grid.width.saturating_sub(1));
        let min_grid_y = grid
            .y_lines
            .binary_search(&top_left.y)
            .unwrap_or_else(|idx| idx)
            .min(grid.height.saturating_sub(1));
        let max_grid_y = grid
            .y_lines
            .binary_search(&bottom_right.y)
            .map(|idx| idx)
            .unwrap_or_else(|idx| idx.saturating_sub(1))
            .min(grid.height.saturating_sub(1));

        // If the node lies strictly between two grid lines, ensure we still mask the nearest inside line.
        let min_grid_x = min_grid_x.min(max_grid_x);
        let min_grid_y = min_grid_y.min(max_grid_y);

        (min_grid_x, max_grid_x, min_grid_y, max_grid_y)
    }

    fn mask_points_in_bounds(
        grid: &Grid,
        point_mask: &mut [bool],
        unremovable: &HashSet<GridPoint>,
        min_grid_x: usize,
        max_grid_x: usize,
        min_grid_y: usize,
        max_grid_y: usize,
    ) {
        if min_grid_x > max_grid_x || min_grid_y > max_grid_y {
            return;
        }
        for grid_y in min_grid_y..=max_grid_y {
            for grid_x in min_grid_x..=max_grid_x {
                if let Some(grid_point) = grid.grid_coords_to_grid_point(grid_x, grid_y) {
                    if unremovable.contains(&grid_point) {
                        continue;
                    }
                    point_mask[grid_point.0 as usize] = false;
                }
            }
        }
    }

    fn mask_vertical_segments_at_x(
        grid: &Grid,
        segment_mask: &mut [bool],
        grid_x: usize,
        min_grid_y: usize,
        max_grid_y: usize,
    ) {
        if grid.height < 2 {
            return;
        }
        let start_y = min_grid_y.saturating_sub(1);
        let end_y = min(grid.height - 2, max_grid_y);
        for grid_y in start_y..=end_y {
            let segment_index =
                grid.grid_coords_to_segment_index((grid_x, grid_y), (grid_x, grid_y + 1));
            segment_mask[segment_index] = false;
        }
    }

    fn mask_horizontal_segments_at_y(
        grid: &Grid,
        segment_mask: &mut [bool],
        grid_y: usize,
        min_grid_x: usize,
        max_grid_x: usize,
    ) {
        if grid.width < 2 {
            return;
        }
        let start_x = min_grid_x.saturating_sub(1);
        let end_x = min(grid.width - 2, max_grid_x);
        for grid_x in start_x..=end_x {
            let segment_index =
                grid.grid_coords_to_segment_index((grid_x, grid_y), (grid_x + 1, grid_y));
            segment_mask[segment_index] = false;
        }
    }

    pub fn from_nodes(
        grid: &'a Grid,
        placed_nodes: &'a Vec<PlacedRectangularNode>,
        unremovable_points: &'a Vec<GridPoint>,
    ) -> Self {
        let mut grid_point_mask = vec![true; grid.size];
        let mut visibility_segment_mask = vec![true; grid.num_segments];
        let unremovable: HashSet<GridPoint> = unremovable_points.iter().copied().collect();

        for node in placed_nodes {
            let tl = node.top_left();
            let br = node.bottom_right();

            let (min_grid_x, max_grid_x, min_grid_y, max_grid_y) =
                Self::node_grid_bounds(grid, tl, br);

            // Mask all grid points that lie within the inclusive ranges (also if only a single grid line fits).
            Self::mask_points_in_bounds(
                grid,
                &mut grid_point_mask,
                &unremovable,
                min_grid_x,
                max_grid_x,
                min_grid_y,
                max_grid_y,
            );

            let tl_x_extruded = tl.x - 1;
            let tl_y_extruded = tl.y - 1;
            let br_x_extruded = br.x + 1;
            let br_y_extruded = br.y + 1;

            // Check if the extruded coordinates are exactly on grid lines
            let min_extruded_grid_x = grid.x_lines.binary_search(&tl_x_extruded);
            let max_extruded_grid_x = grid.x_lines.binary_search(&br_x_extruded);
            let min_extruded_grid_y = grid.y_lines.binary_search(&tl_y_extruded);
            let max_extruded_grid_y = grid.y_lines.binary_search(&br_y_extruded);

            if let Ok(grid_x) = min_extruded_grid_x {
                // Remove the segments along the y grid coordinates with this grid_x.
                Self::mask_vertical_segments_at_x(
                    grid,
                    &mut visibility_segment_mask,
                    grid_x,
                    min_grid_y,
                    max_grid_y,
                );
            }

            if let Ok(grid_x) = max_extruded_grid_x {
                // Remove the segments along the y grid coordinates with this grid_x.
                Self::mask_vertical_segments_at_x(
                    grid,
                    &mut visibility_segment_mask,
                    grid_x,
                    min_grid_y,
                    max_grid_y,
                );
            }

            if let Ok(grid_y) = min_extruded_grid_y {
                // Remove the segments along the x grid coordinates with this grid_y.
                Self::mask_horizontal_segments_at_y(
                    grid,
                    &mut visibility_segment_mask,
                    grid_y,
                    min_grid_x,
                    max_grid_x,
                );
            }

            if let Ok(grid_y) = max_extruded_grid_y {
                // Remove the segments along the x grid coordinates with this grid_y.
                Self::mask_horizontal_segments_at_y(
                    grid,
                    &mut visibility_segment_mask,
                    grid_y,
                    min_grid_x,
                    max_grid_x,
                );
            }
        }
        MaskedGrid {
            grid: &grid,
            point_mask: grid_point_mask,
            segment_mask: visibility_segment_mask,
        }
    }

    fn neighbors(
        &self,
        grid_point: GridPoint,
        orientation: Orientation,
    ) -> Vec<(GridPoint, Orientation)> {
        let Some((x, y)) = self.grid.grid_point_to_grid_coords(grid_point) else {
            return Vec::new();
        };

        let mut neighbors = Vec::new();

        let mut maybe_push = |nx: usize, ny: usize, orientation: Orientation| {
            let Some(neighbor_index) = self.grid.grid_coords_to_grid_point(nx, ny) else {
                return;
            };
            let segment_index = self.grid.grid_coords_to_segment_index((x, y), (nx, ny));
            if self.segment_mask[segment_index] {
                neighbors.push((neighbor_index, orientation));
            }
        };

        match orientation {
            Orientation::Horizontal => {
                if x > 0 {
                    maybe_push(x - 1, y, Orientation::Horizontal);
                }
                if x + 1 < self.grid.width {
                    maybe_push(x + 1, y, Orientation::Horizontal);
                }
            }
            Orientation::Vertical => {
                if y > 0 {
                    maybe_push(x, y - 1, Orientation::Vertical);
                }
                if y + 1 < self.grid.height {
                    maybe_push(x, y + 1, Orientation::Vertical);
                }
            }
        }

        let new_orientation = match orientation {
            Orientation::Horizontal => Orientation::Vertical,
            Orientation::Vertical => Orientation::Horizontal,
        };
        neighbors.push((grid_point, new_orientation));

        neighbors
    }
}

fn routing_seed(
    edges: &Vec<(
        Bound<'_, PyAny>,
        Bound<'_, PyAny>,
        DirectedPoint,
        DirectedPoint,
        RoutingConfig,
    )>,
    nodes: &Vec<PlacedRectangularNode>,
) -> u64 {
    let mut hasher = DefaultHasher::new();
    edges.len().hash(&mut hasher);
    for (_, _, start, end, _) in edges {
        start.x.hash(&mut hasher);
        start.y.hash(&mut hasher);
        start.direction.hash(&mut hasher);
        end.x.hash(&mut hasher);
        end.y.hash(&mut hasher);
        end.direction.hash(&mut hasher);
    }
    nodes.len().hash(&mut hasher);
    for node in nodes {
        node.center.x.hash(&mut hasher);
        node.center.y.hash(&mut hasher);
        node.node.size.width.hash(&mut hasher);
        node.node.size.height.hash(&mut hasher);
    }
    hasher.finish()
}

fn start_end_grid_points(
    grid: &Grid,
    edges: &Vec<(
        Bound<'_, PyAny>,
        Bound<'_, PyAny>,
        DirectedPoint,
        DirectedPoint,
        RoutingConfig,
    )>,
) -> HashSet<GridPoint> {
    let mut start_end_grid_points: HashSet<GridPoint> = HashSet::new();
    for (_, _, start, end, _) in edges {
        if let Some(start_index) = grid.point_to_grid_point(&start.as_point()) {
            start_end_grid_points.insert(start_index);
        }
        if let Some(end_index) = grid.point_to_grid_point(&end.as_point()) {
            start_end_grid_points.insert(end_index);
        }
    }
    start_end_grid_points
}

fn build_trace_layout_data(
    grid: &Grid,
    masked_grid: &MaskedGrid,
    placed_nodes: &HashMap<usize, PlacedRectangularNode>,
) -> (Vec<serde_json::Value>, Vec<serde_json::Value>) {
    // Track which grid points touch a masked segment to visualize masked edges.
    let mut masked_adjacent: Vec<bool> = vec![false; grid.size];

    // Horizontal segments
    for y in 0..grid.height {
        for x in 0..(grid.width - 1) {
            let seg_idx = y * (grid.width - 1) + x;
            if !masked_grid.segment_mask[seg_idx] {
                if let Some(gp_a) = grid.grid_coords_to_grid_point(x, y) {
                    masked_adjacent[gp_a.0 as usize] = true;
                }
                if let Some(gp_b) = grid.grid_coords_to_grid_point(x + 1, y) {
                    masked_adjacent[gp_b.0 as usize] = true;
                }
            }
        }
    }
    // Vertical segments
    let vertical_offset = (grid.width - 1) * grid.height;
    for x in 0..grid.width {
        for y in 0..(grid.height - 1) {
            let seg_idx = vertical_offset + x * (grid.height - 1) + y;
            if !masked_grid.segment_mask[seg_idx] {
                if let Some(gp_a) = grid.grid_coords_to_grid_point(x, y) {
                    masked_adjacent[gp_a.0 as usize] = true;
                }
                if let Some(gp_b) = grid.grid_coords_to_grid_point(x, y + 1) {
                    masked_adjacent[gp_b.0 as usize] = true;
                }
            }
        }
    }

    let mut grid_points_trace = Vec::new();
    for idx in 0..grid.size {
        let gp = GridPoint(idx as u32);
        if let Some((gx, gy)) = grid.grid_point_to_raw_coords(gp) {
            let blocked = !masked_grid.point_mask[gp];
            grid_points_trace.push(json!({
                "index": idx,
                "raw": { "x": gx, "y": gy },
                "blocked": blocked,
                "masked_adjacent": masked_adjacent[idx]
            }));
        }
    }

    let mut layout_nodes = Vec::new();
    for (id, node) in placed_nodes {
        let tl = node.top_left();
        let br = node.bottom_right();
        layout_nodes.push(json!({
            "id": id,
            "center": { "x": node.center.x, "y": node.center.y },
            "size": { "width": node.node.size.width, "height": node.node.size.height },
            "top_left": { "x": tl.x, "y": tl.y },
            "bottom_right": { "x": br.x, "y": br.y },
        }));
    }

    (grid_points_trace, layout_nodes)
}

fn order_edges_by_difficulty<'py, R: Rng + ?Sized>(
    edges: &Vec<(
        Bound<'py, PyAny>,
        Bound<'py, PyAny>,
        DirectedPoint,
        DirectedPoint,
        RoutingConfig,
    )>,
    nodes: &Vec<PlacedRectangularNode>,
    rng: &mut R,
) -> Vec<(
    Bound<'py, PyAny>,
    Bound<'py, PyAny>,
    DirectedPoint,
    DirectedPoint,
    RoutingConfig,
)> {
    let mut edges_with_score: Vec<(
        i32,
        (
            Bound<'_, PyAny>,
            Bound<'_, PyAny>,
            DirectedPoint,
            DirectedPoint,
            RoutingConfig,
        ),
    )> = Vec::new();

    for (u, v, start, end, config) in edges {
        let difficulty = |start: &DirectedPoint, end: &DirectedPoint| -> i32 {
            let span = (start.as_point().x - end.as_point().x).abs()
                + (start.as_point().y - end.as_point().y).abs();
            let min_x = min(start.as_point().x, end.as_point().x);
            let max_x = max(start.as_point().x, end.as_point().x);
            let min_y = min(start.as_point().y, end.as_point().y);
            let max_y = max(start.as_point().y, end.as_point().y);
            let mut obstacle_area = 0;
            let total_area = (max_x - min_x) * (max_y - min_y);
            for node in nodes {
                let node_tl = node.top_left();
                let node_br = node.bottom_right();
                if node_tl.x <= max_x
                    && node_br.x >= min_x
                    && node_tl.y <= max_y
                    && node_br.y >= min_y
                {
                    obstacle_area += (min(node_br.x, max_x) - max(node_tl.x, min_x)).max(0)
                        * (min(node_br.y, max_y) - max(node_tl.y, min_y)).max(0);
                }
            }
            -(span + ((200.0 * obstacle_area as f32 / (total_area as f32)).round()) as i32)
        };
        // Add small reproducible noise to avoid fully deterministic ordering for similar edges.
        let noise: i32 = rng.gen_range(0..=10);
        let score = difficulty(start, end) + noise;
        edges_with_score.push((score, (u.clone(), v.clone(), *start, *end, config.clone())));
    }
    edges_with_score.sort_by_key(|(score, _)| *score);
    edges_with_score.into_iter().map(|(_, edge)| edge).collect()
}

fn compute_overflow(
    raw_usage: &[i32],
    raw_corner_usage: &[i32],
    capacity: i32,
    corner_capacity: i32,
) -> (i32, i32, i32) {
    let mut total_overflow = 0;
    let mut edge_overflow = 0;
    let mut corner_overflow = 0;

    for usage in raw_usage {
        if *usage > capacity {
            let over = *usage - capacity;
            total_overflow += over;
            edge_overflow += over;
        }
    }
    for usage in raw_corner_usage {
        if *usage > corner_capacity {
            let over = *usage - corner_capacity;
            total_overflow += over;
            corner_overflow += over;
        }
    }
    (total_overflow, edge_overflow, corner_overflow)
}

fn update_edge_history_cost(raw_usage: &[i32], raw_history_cost: &mut [f64], capacity: i32) {
    for (i, usage) in raw_usage.iter().enumerate() {
        if *usage > capacity {
            raw_history_cost[i] += (*usage - capacity) as f64;
        }
    }
}

fn update_corner_history_cost(
    raw_corner_usage: &[i32],
    raw_corner_history: &mut [f64],
    corner_capacity: i32,
) {
    for (i, usage) in raw_corner_usage.iter().enumerate() {
        if *usage > corner_capacity {
            raw_corner_history[i] += (*usage - corner_capacity) as f64;
        }
    }
}

fn route_single_edge<R: Rng + ?Sized>(
    grid: &Grid,
    raw_area: &RawArea,
    masked_grid: &MaskedGrid,
    start: DirectedPoint,
    end: DirectedPoint,
    rng: &mut R,
    raw_cost_prefix_x: &[f64],
    raw_cost_prefix_y: &[f64],
    raw_history_cost_prefix_x: &[f64],
    raw_history_cost_prefix_y: &[f64],
    raw_usage: &mut [i32],
    raw_corner_usage: &mut [i32],
    raw_corner_history: &[f64],
    base_cost: f64,
    mu: f64,
    corner_lambda: f64,
    corner_capacity: i32,
    trace_enabled: bool,
) -> PyResult<(
    (RawPoint, RawPoint),
    PathWithEndpoints,
    Option<(
        (RawPoint, RawPoint),
        serde_json::Map<String, serde_json::Value>,
    )>,
)> {
    let start_raw_point = raw_area
        .point_to_raw_point(&start.as_point())
        .ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>("Start or end point is out of bounds")
        })?;
    let end_raw_point = raw_area
        .point_to_raw_point(&end.as_point())
        .ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>("Start or end point is out of bounds")
        })?;

    let start_grid_point: GridPoint =
        grid.point_to_grid_point(&start.as_point()).ok_or_else(|| {
            PyErr::new::<pyo3::exceptions::PyValueError, _>("Start point is not on a grid point")
        })?;
    let end_grid_point: GridPoint = grid.point_to_grid_point(&end.as_point()).ok_or_else(|| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>("End point is not on a grid point")
    })?;

    let start_orientation: Orientation = start.direction.to_orientation();
    let end_orientation: Orientation = end.direction.to_orientation();

    let grid_path = route_visibility_astar(
        masked_grid,
        start_grid_point,
        end_grid_point,
        start_orientation,
        end_orientation,
        rng,
        |from_idx, to_idx, from_orientation, to_orientation| {
            let from_point = grid.grid_point_to_point(from_idx).unwrap();
            let to_point = grid.grid_point_to_point(to_idx).unwrap();

            let turn_cost = if from_orientation != to_orientation {
                1
            } else {
                0
            };

            let current_cost = segment_cost_from_prefix_sums(
                grid,
                raw_cost_prefix_x,
                raw_cost_prefix_y,
                from_idx,
                to_idx,
                from_point,
                to_point,
            );
            let history_cost = segment_cost_from_prefix_sums(
                grid,
                raw_history_cost_prefix_x,
                raw_history_cost_prefix_y,
                from_idx,
                to_idx,
                from_point,
                to_point,
            );

            let corner_penalty = if from_orientation != to_orientation {
                let corner_idx = raw_area.point_to_raw_point(&from_point).unwrap().0 as usize;
                let usage = raw_corner_usage[corner_idx];
                let overflow = if usage > corner_capacity {
                    usage - corner_capacity
                } else {
                    0
                };
                let history = raw_corner_history[corner_idx];
                let reuse_penalty = if usage > 0 { base_cost } else { 0.0 };
                reuse_penalty + corner_lambda * (overflow as f64) + mu * history
            } else {
                0.0
            };

            (turn_cost as f64 + current_cost + mu * history_cost + corner_penalty) as i32
        },
    )?;

    let grid_points: Vec<Point> = grid_path
        .iter()
        .map(|(grid_index, _)| {
            let (grid_x, grid_y) = grid.grid_point_to_raw_coords(*grid_index).unwrap();
            Point {
                x: grid_x,
                y: grid_y,
            }
        })
        .collect();

    let path = Path::new(grid_points);
    let path_with_endpoints = PathWithEndpoints::new(path, start, end);

    for segment_index in path_with_endpoints.segments(raw_area) {
        raw_usage[segment_index] += 1;
    }
    for corner_index in path_with_endpoints.corners(raw_area) {
        raw_corner_usage[corner_index] += 1;
    }

    let trace_entry = if trace_enabled {
        let grid_path_trace: Vec<serde_json::Value> = grid_path
            .iter()
            .map(|(grid_idx, orientation)| {
                let (gx, gy) = grid.grid_point_to_raw_coords(*grid_idx).unwrap_or((0, 0));
                json!({
                    "grid_index": grid_idx.0,
                    "raw": { "x": gx, "y": gy },
                    "orientation": format!("{:?}", orientation)
                })
            })
            .collect();

        let raw_path_trace: Vec<serde_json::Value> = path_with_endpoints
            .path
            .points
            .iter()
            .map(|p| json!({ "x": p.x, "y": p.y }))
            .collect();

        let directed_trace: Vec<serde_json::Value> = path_with_endpoints
            .to_directed_points()
            .into_iter()
            .map(|dp| {
                json!({
                    "x": dp.x,
                    "y": dp.y,
                    "direction": format!("{:?}", dp.direction)
                })
            })
            .collect();

        let mut entry = serde_json::Map::new();
        entry.insert(
            "start".to_string(),
            json!({"x": start.x, "y": start.y, "direction": format!("{:?}", start.direction)}),
        );
        entry.insert(
            "end".to_string(),
            json!({"x": end.x, "y": end.y, "direction": format!("{:?}", end.direction)}),
        );
        entry.insert(
            "grid_path".to_string(),
            serde_json::Value::Array(grid_path_trace),
        );
        entry.insert(
            "raw_path".to_string(),
            serde_json::Value::Array(raw_path_trace),
        );
        entry.insert(
            "directed_path".to_string(),
            serde_json::Value::Array(directed_trace),
        );
        Some(((start_raw_point, end_raw_point), entry))
    } else {
        None
    };

    Ok((
        (start_raw_point, end_raw_point),
        path_with_endpoints,
        trace_entry,
    ))
}

fn edge_path_has_overflow(
    path: &PathWithEndpoints,
    raw_area: &RawArea,
    raw_usage: &[i32],
    raw_corner_usage: &[i32],
    capacity: i32,
    corner_capacity: i32,
) -> bool {
    for segment_index in path.segments(raw_area) {
        if raw_usage[segment_index] > capacity {
            return true;
        }
    }
    for corner_index in path.corners(raw_area) {
        if raw_corner_usage[corner_index] > corner_capacity {
            return true;
        }
    }
    false
}

fn select_edges_to_rip<'py>(
    sorted_edges: &Vec<(
        Bound<'py, PyAny>,
        Bound<'py, PyAny>,
        DirectedPoint,
        DirectedPoint,
        RoutingConfig,
    )>,
    result_paths: &HashMap<(RawPoint, RawPoint), PathWithEndpoints>,
    raw_area: &RawArea,
    raw_usage: &[i32],
    raw_corner_usage: &[i32],
    capacity: i32,
    corner_capacity: i32,
    trace_enabled: bool,
    overflow_map: &mut HashMap<(RawPoint, RawPoint), bool>,
) -> Vec<(
    Bound<'py, PyAny>,
    Bound<'py, PyAny>,
    DirectedPoint,
    DirectedPoint,
    RoutingConfig,
)> {
    let mut to_rip = Vec::new();

    for (u, v, start, end, config) in sorted_edges {
        let start_raw_point = raw_area.point_to_raw_point(&start.as_point()).unwrap();
        let end_raw_point = raw_area.point_to_raw_point(&end.as_point()).unwrap();

        let key = (start_raw_point, end_raw_point);
        let Some(routed_path) = result_paths.get(&key) else {
            continue;
        };

        if edge_path_has_overflow(
            routed_path,
            raw_area,
            raw_usage,
            raw_corner_usage,
            capacity,
            corner_capacity,
        ) {
            if trace_enabled {
                overflow_map.insert(key, true);
            }
            to_rip.push((u.clone(), v.clone(), *start, *end, config.clone()));
        }
    }

    to_rip
}

fn rip_up_and_queue<'py>(
    to_rip: &Vec<(
        Bound<'py, PyAny>,
        Bound<'py, PyAny>,
        DirectedPoint,
        DirectedPoint,
        RoutingConfig,
    )>,
    result_paths: &HashMap<(RawPoint, RawPoint), PathWithEndpoints>,
    raw_area: &RawArea,
    raw_usage: &mut [i32],
    raw_corner_usage: &mut [i32],
) -> Vec<(
    Bound<'py, PyAny>,
    Bound<'py, PyAny>,
    DirectedPoint,
    DirectedPoint,
    RoutingConfig,
)> {
    let mut op_edges = Vec::new();

    for (u, v, start, end, config) in to_rip {
        let start_raw_point = raw_area.point_to_raw_point(&start.as_point()).unwrap();
        let end_raw_point = raw_area.point_to_raw_point(&end.as_point()).unwrap();
        if let Some(routed_path) = result_paths.get(&(start_raw_point, end_raw_point)) {
            for segment_index in routed_path.segments(raw_area) {
                raw_usage[segment_index] -= 1;
            }
            for corner_index in routed_path.corners(raw_area) {
                raw_corner_usage[corner_index] -= 1;
            }
        }
        op_edges.push((u.clone(), v.clone(), *start, *end, config.clone()));
    }

    op_edges
}

fn record_iteration_trace<'py>(
    iteration_logs: &mut Vec<serde_json::Value>,
    iteration: usize,
    routed_edges_trace: Vec<(
        (RawPoint, RawPoint),
        serde_json::Map<String, serde_json::Value>,
    )>,
    overflow_map: &HashMap<(RawPoint, RawPoint), bool>,
    result_paths: &HashMap<(RawPoint, RawPoint), PathWithEndpoints>,
    op_edges: &Vec<(
        Bound<'py, PyAny>,
        Bound<'py, PyAny>,
        DirectedPoint,
        DirectedPoint,
        RoutingConfig,
    )>,
    raw_area: &RawArea,
    raw_usage: &[i32],
    raw_corner_usage: &[i32],
    total_overflow: i32,
    edge_overflow: i32,
    corner_overflow: i32,
) {
    let mut routed_edges_output: Vec<serde_json::Value> = Vec::new();
    for (key, mut entry) in routed_edges_trace.into_iter() {
        let overflow = *overflow_map.get(&key).unwrap_or(&false);
        entry.insert("overflow".to_string(), json!(overflow));
        routed_edges_output.push(serde_json::Value::Object(entry));
    }

    let all_paths_snapshot: Vec<serde_json::Value> = result_paths
        .iter()
        .map(|(key, path_with_endpoints)| {
            let start_point = raw_area.raw_index_to_point(key.0 .0 as usize);
            let end_point = raw_area.raw_index_to_point(key.1 .0 as usize);
            let directed_trace: Vec<serde_json::Value> = path_with_endpoints
                .to_directed_points()
                .into_iter()
                .map(|dp| {
                    json!({
                        "x": dp.x,
                        "y": dp.y,
                        "direction": format!("{:?}", dp.direction)
                    })
                })
                .collect();
            json!({
                "start_raw_index": key.0 .0,
                "end_raw_index": key.1 .0,
                "start_raw_point": { "x": start_point.x, "y": start_point.y },
                "end_raw_point": { "x": end_point.x, "y": end_point.y },
                "directed_path": directed_trace
            })
        })
        .collect();

    let ripped_up_next: Vec<serde_json::Value> = op_edges
        .iter()
        .map(|(_, _, start, end, _)| {
            json!({
                "start": { "x": start.x, "y": start.y, "direction": format!("{:?}", start.direction) },
                "end": { "x": end.x, "y": end.y, "direction": format!("{:?}", end.direction) }
            })
        })
        .collect();

    iteration_logs.push(json!({
        "iteration": iteration,
        "routed_edges": routed_edges_output,
        "all_paths": all_paths_snapshot,
        "ripped_up_next": ripped_up_next,
        "raw_usage": raw_usage.to_vec(),
        "raw_corner_usage": raw_corner_usage.to_vec(),
        "overflow": {
            "total": total_overflow,
            "edges": edge_overflow,
            "corners": corner_overflow
        }
    }));
}

impl Direction {
    fn to_orientation(&self) -> Orientation {
        match self {
            Direction::Up | Direction::Down => Orientation::Vertical,
            Direction::Left | Direction::Right => Orientation::Horizontal,
            Direction::UpLeft | Direction::DownRight | Direction::Center => Orientation::Vertical,
            Direction::UpRight | Direction::DownLeft => Orientation::Horizontal,
        }
    }
}

#[pyclass]
pub struct EdgeRouter {
    pub placed_nodes: HashMap<usize, PlacedRectangularNode>,
    pub object_map: PyIndexSet,
    pub existing_edges: HashMap<(usize, usize), Vec<Point>>,
    pub placed_node_tree: rstar::RTree<PlacedRectangularNode>,
}

#[pymethods]
impl EdgeRouter {
    #[new]
    pub fn new() -> Self {
        EdgeRouter {
            placed_nodes: HashMap::default(),
            placed_node_tree: rstar::RTree::new(),
            object_map: PyIndexSet::default(),
            existing_edges: HashMap::default(),
        }
    }

    fn add_node(
        &mut self,
        node: &Bound<PyAny>,
        placed_node: PlacedRectangularNode,
    ) -> PyResult<()> {
        // TODO check for inserting twice
        let node_index = self.object_map.insert_full(node)?.0;
        self.placed_nodes.insert(node_index, placed_node);
        self.placed_node_tree.insert(placed_node);
        Ok(())
    }

    fn add_edge(
        &mut self,
        start: &Bound<'_, PyAny>,
        end: &Bound<'_, PyAny>,
        line: Vec<Point>,
    ) -> PyResult<()> {
        let start_index = self.object_map.insert_full(start)?.0;
        let end_index = self.object_map.insert_full(end)?.0;

        self.existing_edges
            .insert((start_index, end_index), line.clone());

        Ok(())
    }

    fn remove_node(&mut self, node: &Bound<PyAny>) -> PyResult<()> {
        let index = self.object_map.get_full(node)?.map(|(index, _)| index);
        if let Some(index) = index {
            self.placed_nodes.remove(&index);
            self.placed_node_tree.remove(&self.placed_nodes[&index]);
        }
        // TODO: Needs some cleanup of the object map at some point.
        Ok(())
    }

    fn remove_edge(
        &mut self,
        _py: Python<'_>,
        start: &Bound<'_, PyAny>,
        end: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let start_index = self.object_map.insert_full(start)?.0;
        let end_index = self.object_map.insert_full(end)?.0;

        if let Some(line) = self.existing_edges.get(&(start_index, end_index)) {
            self.existing_edges.remove(&(start_index, end_index));
        }

        // TODO: Needs some cleanup of the object map at some point.
        Ok(())
    }

    fn route_edges(
        &mut self,
        edges: Vec<(
            Bound<'_, PyAny>,
            Bound<'_, PyAny>,
            DirectedPoint,
            DirectedPoint,
            RoutingConfig,
        )>,
    ) -> PyResult<EdgeRoutingsResult> {
        let max_iterations = 20;
        let trace_path = std::env::var("NETEXT_ROUTING_TRACE_JSON").ok();
        let trace_enabled = trace_path.is_some();
        let mut iteration_logs = Vec::new();
        let mut layout_nodes = Vec::new();
        let mut grid_points_trace = Vec::new();

        // First we generate a grid from all start and end point projections and midpoints.
        let grid = Grid::from_edges_and_nodes(
            &edges
                .iter()
                .map(|(_, _, start, end, _)| (start.as_point(), end.as_point()))
                .collect(),
            &self.placed_nodes.values().cloned().collect(),
        );

        let raw_area = grid.raw_area();
        let raw_num_segments = raw_area.num_segments();

        // Then we remove all grid points that are inside any placed node and all edges that intersect
        // any placed node or are directly adjacent to a placed node.

        // We use a mask to remove these points and edges.

        // Convert all start and end points to grid points
        let start_end_grid_points: HashSet<GridPoint> = start_end_grid_points(&grid, &edges);

        let placed_nodes_vector = self.placed_nodes.values().cloned().collect();
        let start_end_grid_points_vector: Vec<GridPoint> =
            start_end_grid_points.iter().cloned().collect();

        let seed = routing_seed(&edges, &placed_nodes_vector);
        let mut rng: StdRng = StdRng::seed_from_u64(seed);

        let masked_grid =
            MaskedGrid::from_nodes(&grid, &placed_nodes_vector, &start_end_grid_points_vector);

        if trace_enabled {
            let (grid_points, nodes) =
                build_trace_layout_data(&grid, &masked_grid, &self.placed_nodes);
            grid_points_trace = grid_points;
            layout_nodes = nodes;
        }

        // We also need to maintain usage and capacity on the raw grid, initialized with usage from
        // existing edges. We could also use capacity to change how edges are routed here.
        let mut raw_usage = vec![0; raw_num_segments as usize];
        let mut raw_cost = vec![0.0; raw_num_segments as usize];
        let mut raw_history_cost = vec![0.0; raw_num_segments as usize];
        let mut raw_corner_usage = vec![0; raw_area.size()];
        let mut raw_corner_history = vec![0.0; raw_area.size()];

        let mut raw_cost_prefix_x = vec![0.0; ((raw_area.width()) * raw_area.height()) as usize];
        let mut raw_cost_prefix_y = vec![0.0; (raw_area.width() * (raw_area.height())) as usize];

        let mut raw_history_cost_prefix_x =
            vec![0.0; ((raw_area.width()) * raw_area.height()) as usize];
        let mut raw_history_cost_prefix_y =
            vec![0.0; (raw_area.width() * (raw_area.height())) as usize];

        // With the prefix sums, we can also compute usage and capacity on the grid edges.
        // for the initial routing, the usage is zero everywhere and the cose is just the length of the edge.
        // hence we can pass a simplified cost function to the A*

        let mut result_paths: HashMap<(RawPoint, RawPoint), PathWithEndpoints> = HashMap::new();

        // Now we iterate up to some maximum number of iterations
        let lambda = 2.0;
        let mu: f64 = 0.5;
        let base_cost = 1.0;
        let capacity = 1;
        let corner_lambda = 5.0;
        let corner_capacity = 1;
        let mut op_edges = edges.clone();

        for i in 0..max_iterations {
            // 1) Compute present costs from current usage
            for i in 0..raw_num_segments as usize {
                // Cost is base + lambda * max(0, usage - capacity)
                let usage = raw_usage[i];
                let overflow = if usage > capacity {
                    usage - capacity
                } else {
                    0
                };
                raw_cost[i] = 1.0 + lambda * (overflow as f64);
            }

            // Update prefix sums as the per edge costs have now all changed.
            raw_area.edge_prefix_sums(&raw_cost, &mut raw_cost_prefix_x, &mut raw_cost_prefix_y);
            raw_area.edge_prefix_sums(
                &raw_history_cost,
                &mut raw_history_cost_prefix_x,
                &mut raw_history_cost_prefix_y,
            );

            // 2) Order nets by difficulty (span, channel width, past failures, etc.)
            // We want to route all edges, starting with the most difficult ones.
            // Difficulty is the span (Manhattan distance) between start and end point
            // plus the obstacle density in the bounding box of start and end point
            let sorted_edges = order_edges_by_difficulty(&op_edges, &placed_nodes_vector, &mut rng);

            // 3) For each net in order, find the cheapest path using A* or Dijkstra

            // Now we route all edges once, storing their paths and updating usage.
            let mut routed_edges_trace: Vec<(
                (RawPoint, RawPoint),
                serde_json::Map<String, serde_json::Value>,
            )> = Vec::new();
            let mut overflow_map: HashMap<(RawPoint, RawPoint), bool> = HashMap::new();
            for (_u, _v, start, end, _) in &sorted_edges {
                let (key, path_with_endpoints, trace_entry) = route_single_edge(
                    &grid,
                    &raw_area,
                    &masked_grid,
                    *start,
                    *end,
                    &mut rng,
                    &raw_cost_prefix_x,
                    &raw_cost_prefix_y,
                    &raw_history_cost_prefix_x,
                    &raw_history_cost_prefix_y,
                    &mut raw_usage,
                    &mut raw_corner_usage,
                    &raw_corner_history,
                    base_cost,
                    mu,
                    corner_lambda,
                    corner_capacity,
                    trace_enabled,
                )?;

                result_paths.insert(key, path_with_endpoints);
                if let Some((trace_key, entry)) = trace_entry {
                    routed_edges_trace.push((trace_key, entry));
                    overflow_map.entry(trace_key).or_insert(false);
                }
            }

            // 4) Compute overflow
            let (total_overflow, edge_overflow, corner_overflow) =
                compute_overflow(&raw_usage, &raw_corner_usage, capacity, corner_capacity);
            let finished = total_overflow == 0;

            if !finished {
                // 5) Update history cost based on overflow
                update_edge_history_cost(&raw_usage, &mut raw_history_cost, capacity);
                update_corner_history_cost(
                    &raw_corner_usage,
                    &mut raw_corner_history,
                    corner_capacity,
                );

                // 6) Select edges to rip up based on some criteria
                op_edges.clear();

                // For simplicity, we rip up all edges that have any overflow on their paths.
                // Random tie-breaks in routing order already added above; selection here is based on current usage.
                let to_rip = select_edges_to_rip(
                    &sorted_edges,
                    &result_paths,
                    &raw_area,
                    &raw_usage,
                    &raw_corner_usage,
                    capacity,
                    corner_capacity,
                    trace_enabled,
                    &mut overflow_map,
                );

                op_edges = rip_up_and_queue(
                    &to_rip,
                    &result_paths,
                    &raw_area,
                    &mut raw_usage,
                    &mut raw_corner_usage,
                );
            } else {
                op_edges.clear();
            }

            if trace_enabled {
                record_iteration_trace(
                    &mut iteration_logs,
                    i,
                    routed_edges_trace,
                    &overflow_map,
                    &result_paths,
                    &op_edges,
                    &raw_area,
                    &raw_usage,
                    &raw_corner_usage,
                    total_overflow,
                    edge_overflow,
                    corner_overflow,
                );
            }

            if finished {
                break;
            }
        }

        let mut directed_paths: Vec<Vec<DirectedPoint>> = Vec::new();
        for (_, path_with_endpoints) in result_paths.iter() {
            directed_paths.push(path_with_endpoints.to_directed_points());
        }

        if let Some(path) = trace_path {
            let raw_area_json = json!({
                "top_left": { "x": raw_area.top_left.x, "y": raw_area.top_left.y },
                "bottom_right": { "x": raw_area.bottom_right.x, "y": raw_area.bottom_right.y },
                "width": raw_area.width(),
                "height": raw_area.height(),
            });
            let trace_json = json!({
                "layout": {
                    "nodes": layout_nodes,
                    "grid_points": grid_points_trace,
                    "raw_area": raw_area_json
                },
                "iterations": iteration_logs
            });
            let serialized = serde_json::to_string_pretty(&trace_json).map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                    "Failed to serialize routing trace: {}",
                    e
                ))
            })?;
            fs::write(&path, serialized).map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyIOError, _>(format!(
                    "Failed to write routing trace to {}: {}",
                    path, e
                ))
            })?;
        }

        Ok(EdgeRoutingsResult::new(directed_paths))
    }

    fn route_edge(
        &self,
        u: &Bound<'_, PyAny>,
        v: &Bound<'_, PyAny>,
        start: DirectedPoint,
        end: DirectedPoint,
        global_start: DirectedPoint,
        global_end: DirectedPoint,
        config: RoutingConfig,
    ) -> PyResult<EdgeRoutingResult> {
        let result_path = Vec::new();
        Ok(EdgeRoutingResult::new(result_path))
    }
}

fn segment_cost_from_prefix_sums(
    grid: &Grid,
    raw_cost_prefix_x: &[f64],
    raw_cost_prefix_y: &[f64],
    from_idx: GridPoint,
    to_idx: GridPoint,
    from_point: Point,
    to_point: Point,
) -> f64 {
    let current_cost = if from_point == to_point {
        0.0
    } else {
        if from_point.x == to_point.x {
            // Vertical move
            let to_upper = to_point.y > from_point.y;

            let upper_raw_point = if to_upper {
                grid.grid_point_to_raw_point(to_idx).unwrap()
            } else {
                grid.grid_point_to_raw_point(from_idx).unwrap()
            };
            let lower_raw_point = if to_upper {
                grid.grid_point_to_raw_point(from_idx).unwrap()
            } else {
                grid.grid_point_to_raw_point(to_idx).unwrap()
            };

            raw_cost_prefix_y[upper_raw_point.0 as usize]
                - raw_cost_prefix_y[lower_raw_point.0 as usize]
        } else {
            // Horizontal move
            let to_left = to_point.x < from_point.x;

            let left_raw_point = if to_left {
                grid.grid_point_to_raw_point(to_idx).unwrap()
            } else {
                grid.grid_point_to_raw_point(from_idx).unwrap()
            };
            let right_raw_point = if to_left {
                grid.grid_point_to_raw_point(from_idx).unwrap()
            } else {
                grid.grid_point_to_raw_point(to_idx).unwrap()
            };

            raw_cost_prefix_x[right_raw_point.0 as usize]
                - raw_cost_prefix_x[left_raw_point.0 as usize]
        }
    };
    current_cost
}

fn closest_node_name(nodes: &Vec<PlacedRectangularNode>, point: Point) -> Option<(i32, Point)> {
    nodes
        .iter()
        .map(|n| {
            let tl = n.top_left();
            let br = n.bottom_right();
            let center = Point {
                x: (tl.x + br.x) / 2,
                y: (tl.y + br.y) / 2,
            };
            let dist = (center.x - point.x).abs() + (center.y - point.y).abs();
            (dist, center)
        })
        .min_by_key(|(d, _)| *d)
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
struct GridState {
    index: GridPoint,
    orientation: Orientation,
}

fn route_visibility_astar<CostFn, R>(
    masked_grid: &MaskedGrid,
    start_grid_point: GridPoint,
    end_grid_point: GridPoint,
    start_orientation: Orientation,
    end_orientation: Orientation,
    rng: &mut R,
    mut cost_fn: CostFn,
) -> PyResult<Vec<(GridPoint, Orientation)>>
where
    CostFn: FnMut(GridPoint, GridPoint, Orientation, Orientation) -> i32,
    R: Rng + ?Sized,
{
    if start_grid_point.0 as usize >= masked_grid.point_mask.len()
        || end_grid_point.0 as usize >= masked_grid.point_mask.len()
    {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Start or end grid index out of bounds",
        ));
    }

    if !masked_grid.point_mask[start_grid_point] || !masked_grid.point_mask[end_grid_point] {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Start or end grid point is blocked",
        ));
    }

    let start_state = GridState {
        index: start_grid_point,
        orientation: start_orientation,
    };
    let goal_state = GridState {
        index: end_grid_point,
        orientation: end_orientation,
    };

    if start_state == goal_state {
        return Ok(vec![(start_state.index, start_state.orientation)]);
    }

    let goal_coords = masked_grid.grid.grid_point_to_grid_coords(end_grid_point);

    if goal_coords.is_none() {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "End grid point is out of bounds",
        ));
    }

    let goal_coords = goal_coords.unwrap();

    let heuristic = |state: GridState| -> i32 {
        let (sx, sy) = masked_grid
            .grid
            .grid_point_to_grid_coords(state.index)
            .unwrap();
        (sx as i32 - goal_coords.0 as i32).abs() + (sy as i32 - goal_coords.1 as i32).abs()
    };

    let mut open_set: BinaryHeap<(Reverse<i32>, u64, GridState)> = BinaryHeap::new();
    let mut came_from: HashMap<GridState, GridState> = HashMap::new();
    let mut g_score: HashMap<GridState, i32> = HashMap::new();

    const MAX_SCORE: i32 = i32::MAX / 4;
    let mut insert_counter: u64 = 0;

    g_score.insert(start_state, 0);
    let start_f = heuristic(start_state);
    open_set.push((Reverse(start_f), insert_counter, start_state));
    insert_counter += 1;

    while let Some((Reverse(_f_score), _order, current_state)) = open_set.pop() {
        if current_state == goal_state {
            let mut path = Vec::new();
            let mut cursor = current_state;
            path.push((cursor.index, cursor.orientation));
            while let Some(prev) = came_from.get(&cursor).copied() {
                cursor = prev;
                path.push((cursor.index, cursor.orientation));
            }
            path.reverse();
            return Ok(path);
        }

        let current_g = *g_score.get(&current_state).unwrap_or(&MAX_SCORE);

        let mut neighbors = masked_grid.neighbors(current_state.index, current_state.orientation);
        neighbors.shuffle(rng);
        for (neighbor_index, neighbor_orientation) in neighbors {
            // Do not allow in-place orientation flips at the start or end grid point.
            if neighbor_index == current_state.index
                && (current_state.index == start_grid_point
                    || current_state.index == end_grid_point)
            {
                continue;
            }

            if !masked_grid.point_mask[neighbor_index] {
                continue;
            }

            let neighbor_state = GridState {
                index: neighbor_index,
                orientation: neighbor_orientation,
            };

            let step_cost = cost_fn(
                current_state.index,
                neighbor_state.index,
                current_state.orientation,
                neighbor_state.orientation,
            );

            if step_cost >= MAX_SCORE {
                continue;
            }

            let tentative_g = match current_g.checked_add(step_cost) {
                Some(sum) => sum,
                None => continue,
            };

            if tentative_g >= *g_score.get(&neighbor_state).unwrap_or(&MAX_SCORE) {
                continue;
            }

            came_from.insert(neighbor_state, current_state);
            g_score.insert(neighbor_state, tentative_g);
            let heuristic_cost = heuristic(neighbor_state);
            let f_score = match tentative_g.checked_add(heuristic_cost) {
                Some(value) => value,
                None => continue,
            };
            open_set.push((Reverse(f_score), insert_counter, neighbor_state));
            insert_counter += 1;
        }
    }

    Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
        "Goal not found.",
    ))
}
