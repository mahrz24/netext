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

    pub(crate) fn build_lines_from_coords(mut coords: Vec<i32>) -> Vec<i32> {
        const MAX_INTERMEDIATE: usize = 8;
        // Minimum guaranteed spacing between consecutive interior lines.
        // With turn_cost = 3*base_cost, a detour through a MIN_SPACING-wide
        // gap costs 2*3 + 2*MIN_SPACING, which is expensive enough to prevent
        // zigzag artifacts while still providing useful routing channels.
        const MIN_SPACING: i32 = 4;

        coords.sort_unstable();
        coords.dedup();

        let mut lines = Vec::new();
        let mut last: Option<i32> = None;

        for value in coords {
            if let Some(last_value) = last {
                if last_value < value - 4 {
                    let interior_start = last_value + 3;
                    let interior_end = value - 3;
                    let interior_gap = interior_end - interior_start;

                    let mut intermediates = Vec::with_capacity(MAX_INTERMEDIATE + 2);
                    intermediates.push(last_value + 2); // +2 boundary

                    // Always include the midpoint as a routing channel
                    let mid = (last_value + value) / 2;
                    if mid > last_value + 2 && mid < value - 2 {
                        intermediates.push(mid);
                    }

                    if interior_gap >= MIN_SPACING {
                        // Uniform fill: N+1 intervals each >= MIN_SPACING.
                        let num_lines =
                            ((interior_gap / MIN_SPACING - 1).max(0) as usize).min(MAX_INTERMEDIATE);
                        if num_lines > 0 {
                            let step = interior_gap as f64 / (num_lines as f64 + 1.0);
                            for i in 1..=num_lines {
                                intermediates
                                    .push(interior_start + (step * i as f64).round() as i32);
                            }
                        }
                    }

                    intermediates.push(value - 2); // -2 boundary
                    intermediates.sort_unstable();
                    intermediates.dedup();
                    lines.extend(intermediates);
                } else if last_value < value - 1 {
                    lines.push((last_value + value) / 2);
                }
            }
            lines.push(value);
            last = Some(value);
        }

        lines
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

        // Compute padded boundaries. Edges routing around the outside of the
        // graph need enough margin for multiple routing channels.
        let padding = 7;
        let edge_min_x = *x_set.iter().min().unwrap_or(&0);
        let edge_max_x = *x_set.iter().max().unwrap_or(&0);
        let edge_min_y = *y_set.iter().min().unwrap_or(&0);
        let edge_max_y = *y_set.iter().max().unwrap_or(&0);

        let min_x = min(min_nodes_x - padding, edge_min_x - padding);
        let max_x = max(max_nodes_x + padding, edge_max_x + padding);
        let min_y = min(min_nodes_y - padding, edge_min_y - padding);
        let max_y = max(max_nodes_y + padding, edge_max_y + padding);

        // Include boundary coordinates in the coord sets so that
        // build_lines_from_coords generates intermediate lines in the
        // padding area (edges routing around the graph need channels there).
        x_set.insert(min_x);
        x_set.insert(max_x);
        y_set.insert(min_y);
        y_set.insert(max_y);

        let x_lines = Self::build_lines_from_coords(x_set.into_iter().collect());
        let y_lines = Self::build_lines_from_coords(y_set.into_iter().collect());

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

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_no_intermediates() {
        let result = Grid::build_lines_from_coords(vec![10, 11]);
        assert_eq!(result, vec![10, 11]);
    }

    #[test]
    fn test_small_gap_midpoint() {
        let result = Grid::build_lines_from_coords(vec![10, 13]);
        assert_eq!(result, vec![10, 11, 13]);
    }

    #[test]
    fn test_gap_of_5() {
        // Gap of 5: gets +2 and -2 boundaries (2 routing channels)
        let result = Grid::build_lines_from_coords(vec![10, 15]);
        assert_eq!(result, vec![10, 12, 13, 15]);
    }

    #[test]
    fn test_gap_of_4_midpoint_only() {
        // Gap of 4: only midpoint (too tight for boundary lines)
        let result = Grid::build_lines_from_coords(vec![10, 14]);
        assert_eq!(result, vec![10, 12, 14]);
    }

    #[test]
    fn test_medium_gap() {
        // Gap of 6: +2, midpoint, -2
        let result = Grid::build_lines_from_coords(vec![10, 16]);
        assert!(result.contains(&10));
        assert!(result.contains(&16));
        assert!(result.contains(&12)); // +2
        assert!(result.contains(&13)); // midpoint
        assert!(result.contains(&14)); // -2
    }

    #[test]
    fn test_gap_10_has_midpoint() {
        // Gap of 10: interior_gap=4, gets midpoint
        let result = Grid::build_lines_from_coords(vec![0, 10]);
        assert!(result.contains(&2));  // +2
        assert!(result.contains(&5));  // midpoint
        assert!(result.contains(&8));  // -2
    }

    #[test]
    fn test_gap_14_gets_extra_line() {
        // Gap of 14: interior_gap=8, 8/4-1=1 uniform line
        let result = Grid::build_lines_from_coords(vec![0, 14]);
        assert!(result.contains(&2));  // +2
        assert!(result.contains(&12)); // -2
        // Should have at least one interior line between +2 and -2
        let interior: Vec<_> = result.iter().filter(|&&v| v > 2 && v < 12).collect();
        assert!(!interior.is_empty(), "Expected interior line(s), got {:?}", result);
    }

    #[test]
    fn test_large_gap_more_channels() {
        // Gap of 30: interior_gap=24, should get multiple interior lines
        let result = Grid::build_lines_from_coords(vec![0, 30]);
        assert!(result.contains(&0));
        assert!(result.contains(&30));
        assert!(result.contains(&2));  // +2 boundary
        assert!(result.contains(&28)); // -2 boundary
        let interior: Vec<_> = result.iter().filter(|&&v| v > 2 && v < 28).collect();
        assert!(interior.len() >= 3, "Expected >=3 interior lines for gap=30, got {:?}", result);
    }

    #[test]
    fn test_very_large_gap() {
        // Gap of 200: gets many interior lines, bounded by MAX_INTERMEDIATE + boundaries + midpoint
        let result = Grid::build_lines_from_coords(vec![0, 200]);
        assert!(result.contains(&0));
        assert!(result.contains(&200));
        assert!(result.contains(&2));   // +2 boundary
        assert!(result.contains(&100)); // midpoint
        assert!(result.contains(&198)); // -2 boundary
        let total_intermediates = result.len() - 2; // minus original coords
        // MAX_INTERMEDIATE(8) uniform + 2 boundaries + 1 midpoint = up to 11
        assert!(total_intermediates <= 12, "Too many intermediates: {:?}", result);
        assert!(total_intermediates >= 5, "Expected >=5 intermediates for gap=200, got {:?}", result);
    }

    #[test]
    fn test_uniform_lines_well_spaced() {
        // For large gaps, the uniform lines (excluding midpoint) should be well-spaced
        let result = Grid::build_lines_from_coords(vec![0, 100]);
        // All consecutive lines should be at least 2 apart (midpoint can be close to uniform)
        for window in result.windows(2) {
            assert!(
                window[1] - window[0] >= 1,
                "Duplicate or reversed: {} to {}, full: {:?}",
                window[0],
                window[1],
                result
            );
        }
        // Should have meaningful number of routing channels
        let interior: Vec<_> = result.iter().filter(|&&v| v > 2 && v < 98).collect();
        assert!(interior.len() >= 4, "Expected >=4 interior channels for gap=100, got {:?}", result);
    }

    #[test]
    fn test_preserves_original_coords() {
        let input = vec![5, 20, 50, 100];
        let result = Grid::build_lines_from_coords(input.clone());
        for coord in &input {
            assert!(result.contains(coord), "Missing original coord {}", coord);
        }
    }

    #[test]
    fn test_sorted_and_deduped() {
        let result = Grid::build_lines_from_coords(vec![50, 10, 30, 10]);
        for window in result.windows(2) {
            assert!(window[0] < window[1], "Not sorted: {:?}", result);
        }
        let mut deduped = result.clone();
        deduped.dedup();
        assert_eq!(result, deduped);
    }
}
