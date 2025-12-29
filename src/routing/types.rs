use std::marker::PhantomData;

use pyo3::prelude::*;

use crate::geometry::{DirectedPoint, Direction, Neighborhood, Point};

use super::raw_area::RawArea;

#[pyclass]
#[derive(Clone, PartialEq, Debug, Copy)]
pub struct RoutingConfig {
    pub(crate) neighborhood: Neighborhood,
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

#[pyclass]
#[derive(Clone, PartialEq, Debug)]
pub struct EdgeRoutingResult {
    pub path: Vec<DirectedPoint>,
}

#[pymethods]
impl EdgeRoutingResult {
    #[new]
    pub(crate) fn new(path: Vec<DirectedPoint>) -> Self {
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

#[pymethods]
impl EdgeRoutingsResult {
    #[new]
    pub(crate) fn new(paths: Vec<Vec<DirectedPoint>>) -> Self {
        EdgeRoutingsResult { paths }
    }

    #[getter]
    fn get_paths(&self) -> Vec<Vec<DirectedPoint>> {
        self.paths.clone()
    }
}

/// Wrapper around a routed path of grid points that provides helper iteration methods.
#[allow(dead_code)]
#[derive(Clone, PartialEq, Debug)]
pub(crate) struct Path {
    pub points: Vec<Point>,
}

#[derive(Clone, PartialEq, Debug)]
pub(crate) struct PathWithEndpoints {
    pub path: Path,
    pub start: DirectedPoint,
    pub end: DirectedPoint,
}

impl Path {
    pub fn new(points: Vec<Point>) -> Self {
        Path { points }
    }

    #[allow(dead_code)]
    pub fn as_slice(&self) -> &[Point] {
        &self.points
    }

    #[allow(dead_code)]
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

            if let Some(segment) = manhattan_segment(window_start, window_end) {
                let first_segment = result_path.is_empty();
                push_directed_segment(
                    &mut result_path,
                    segment,
                    if first_segment {
                        Some(self.start.direction)
                    } else {
                        None
                    },
                );
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

#[derive(Copy, Clone, Debug, Eq, PartialEq)]
struct ManhattanSegment {
    from: Point,
    to: Point,
}

fn manhattan_segment(from: Point, to: Point) -> Option<ManhattanSegment> {
    if from == to {
        return None;
    }
    if from.x != to.x && from.y != to.y {
        return None;
    }
    Some(ManhattanSegment { from, to })
}

fn walk_manhattan_steps(mut from: Point, to: Point, mut visit: impl FnMut(Point, Point)) {
    let Some(segment) = manhattan_segment(from, to) else {
        return;
    };
    let step_x = (segment.to.x - segment.from.x).signum();
    let step_y = (segment.to.y - segment.from.y).signum();
    let steps = (segment.to.x - segment.from.x)
        .abs()
        .max((segment.to.y - segment.from.y).abs());

    for _ in 0..steps {
        let next = Point {
            x: from.x + step_x,
            y: from.y + step_y,
        };
        visit(from, next);
        from = next;
    }
}

fn push_directed_segment(
    out: &mut Vec<DirectedPoint>,
    segment: ManhattanSegment,
    first_direction_override: Option<Direction>,
) {
    if segment.from.x == segment.to.x {
        let direction = if segment.to.y < segment.from.y {
            Direction::Up
        } else {
            Direction::Down
        };
        let direction_offset = if direction == Direction::Up { -1 } else { 1 };

        out.push(DirectedPoint {
            x: segment.from.x,
            y: segment.from.y,
            direction: first_direction_override.unwrap_or(direction),
            debug: false,
        });

        for y in 1..=(segment.to.y - segment.from.y).abs() {
            out.push(DirectedPoint {
                x: segment.from.x,
                y: segment.from.y + y * direction_offset,
                direction: direction.opposite(),
                debug: false,
            });
        }
    } else if segment.from.y == segment.to.y {
        let direction = if segment.to.x > segment.from.x {
            Direction::Right
        } else {
            Direction::Left
        };

        out.push(DirectedPoint {
            x: segment.from.x,
            y: segment.from.y,
            direction: first_direction_override.unwrap_or(direction),
            debug: false,
        });

        let direction_offset = if direction == Direction::Left { -1 } else { 1 };
        for x in 1..=(segment.to.x - segment.from.x).abs() {
            out.push(DirectedPoint {
                x: segment.from.x + x * direction_offset,
                y: segment.from.y,
                direction: direction.opposite(),
                debug: false,
            });
        }
    }
}

pub(crate) struct PathSegments<'a> {
    indices: Vec<usize>,
    position: usize,
    _phantom: PhantomData<&'a ()>,
}

impl<'a> PathSegments<'a> {
    fn new(path: &'a Path, raw_area: &'a RawArea) -> Self {
        let mut indices = Vec::new();

        for window in path.points.windows(2) {
            walk_manhattan_steps(window[0], window[1], |from, to| {
                if let Some(idx) = raw_area.segment_index_between(&from, &to) {
                    if indices.last().copied() != Some(idx) {
                        indices.push(idx);
                    }
                }
            });
        }

        PathSegments {
            indices,
            position: 0,
            _phantom: PhantomData,
        }
    }
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

pub(crate) struct PathCorners<'a> {
    indices: Vec<usize>,
    position: usize,
    _phantom: PhantomData<&'a ()>,
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
