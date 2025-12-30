use std::cmp::{max, min};
use std::collections::HashSet;
use std::ops::{Index, IndexMut};

use crate::geometry::{BoundingBox, PlacedRectangularNode, Point};

use super::raw_area::RawArea;

#[derive(Clone, Hash, Default)]
pub(crate) struct Grid {
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
pub(crate) struct RawPoint(pub u32);

#[repr(transparent)]
#[derive(Copy, Clone, Eq, PartialEq, Ord, PartialOrd, Hash, Default, Debug)]
pub(crate) struct GridPoint(pub u32);

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
pub(crate) struct GridSegment(pub u32);

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

    fn build_lines_from_coords(mut coords: Vec<i32>) -> Vec<i32> {
        coords.sort_unstable();
        coords.dedup();

        let mut lines = Vec::new();
        let mut last: Option<i32> = None;

        for value in coords {
            if let Some(last_value) = last {
                if last_value < value - 5 {
                    lines.push(last_value + 2);
                }
                if last_value < value - 1 {
                    lines.push((last_value + value) / 2);
                }
                if last_value < value - 5 {
                    lines.push(value - 2);
                }
            }
            lines.push(value);
            last = Some(value);
        }

        lines
    }

    fn ensure_min_max(lines: &mut Vec<i32>, min_value: i32, max_value: i32) {
        if lines.is_empty() {
            lines.push(min_value);
            if max_value != min_value {
                lines.push(max_value);
            }
            return;
        }

        if lines.binary_search(&min_value).is_err() {
            lines.insert(0, min_value);
        }
        if lines.binary_search(&max_value).is_err() {
            lines.push(max_value);
        }
    }

    pub fn from_edges_and_nodes(edges: &Vec<(Point, Point)>, nodes: &Vec<PlacedRectangularNode>) -> Self {
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

        let mut x_lines = Self::build_lines_from_coords(x_set.into_iter().collect());
        let mut y_lines = Self::build_lines_from_coords(y_set.into_iter().collect());

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
        Self::ensure_min_max(&mut x_lines, min_x, max_x);
        Self::ensure_min_max(&mut y_lines, min_y, max_y);

        Grid::new(x_lines.len(), y_lines.len(), x_lines, y_lines)
    }

    pub(crate) fn raw_area(&self) -> RawArea {
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

    pub(crate) fn grid_coords_to_segment_index(&self, grid_a: (usize, usize), grid_b: (usize, usize)) -> usize {
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

    pub(crate) fn grid_point_to_raw_point(&self, point: GridPoint) -> Option<RawPoint> {
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

    pub(crate) fn grid_point_to_raw_coords(&self, point: GridPoint) -> Option<(i32, i32)> {
        if !self.is_valid_point(point) {
            return None;
        }
        let grid_x = (point.0 % self.width as u32) as usize;
        let grid_y = (point.0 / self.width as u32) as usize;
        let x = self.x_lines[grid_x];
        let y = self.y_lines[grid_y];
        Some((x, y))
    }

    pub(crate) fn grid_point_to_grid_coords(&self, point: GridPoint) -> Option<(usize, usize)> {
        if !self.is_valid_point(point) {
            return None;
        }
        let grid_x = (point.0 % self.width as u32) as usize;
        let grid_y = (point.0 / self.width as u32) as usize;
        Some((grid_x, grid_y))
    }

    pub(crate) fn grid_coords_to_grid_point(&self, grid_x: usize, grid_y: usize) -> Option<GridPoint> {
        if grid_x >= self.width || grid_y >= self.height {
            return None;
        }
        Some(GridPoint((grid_y * self.width + grid_x) as u32))
    }

    pub(crate) fn point_to_grid_point(&self, point: &Point) -> Option<GridPoint> {
        let grid_x = self.x_lines.binary_search(&point.x).ok()?;
        let grid_y = self.y_lines.binary_search(&point.y).ok()?;
        self.grid_coords_to_grid_point(grid_x, grid_y)
    }

    pub(crate) fn grid_point_to_point(&self, point: GridPoint) -> Option<Point> {
        let (grid_x, grid_y) = self.grid_point_to_grid_coords(point)?;
        Some(Point {
            x: self.x_lines[grid_x],
            y: self.y_lines[grid_y],
        })
    }
}
