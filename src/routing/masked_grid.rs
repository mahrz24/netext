use std::cmp::min;
use std::collections::HashSet;

use crate::geometry::{BoundingBox, Orientation, PlacedRectangularNode, Point};

use super::grid::{Grid, GridPoint};

#[derive(Clone)]
pub(crate) struct MaskedGrid<'a> {
    pub(crate) grid: &'a Grid,
    pub(crate) point_mask: Vec<bool>,
    pub(crate) segment_mask: Vec<bool>,
}

impl<'a> MaskedGrid<'a> {
    fn node_grid_bounds(grid: &Grid, top_left: Point, bottom_right: Point) -> (usize, usize, usize, usize) {
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
        unremovable: &HashSet<GridPoint>,
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
            if let (Some(a), Some(b)) = (
                grid.grid_coords_to_grid_point(grid_x, grid_y),
                grid.grid_coords_to_grid_point(grid_x, grid_y + 1),
            ) {
                if unremovable.contains(&a) || unremovable.contains(&b) {
                    continue;
                }
            }
            let segment_index = grid.grid_coords_to_segment_index((grid_x, grid_y), (grid_x, grid_y + 1));
            segment_mask[segment_index] = false;
        }
    }

    fn mask_horizontal_segments_at_y(
        grid: &Grid,
        segment_mask: &mut [bool],
        unremovable: &HashSet<GridPoint>,
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
            if let (Some(a), Some(b)) = (
                grid.grid_coords_to_grid_point(grid_x, grid_y),
                grid.grid_coords_to_grid_point(grid_x + 1, grid_y),
            ) {
                if unremovable.contains(&a) || unremovable.contains(&b) {
                    continue;
                }
            }
            let segment_index = grid.grid_coords_to_segment_index((grid_x, grid_y), (grid_x + 1, grid_y));
            segment_mask[segment_index] = false;
        }
    }

    pub fn from_nodes(grid: &'a Grid, placed_nodes: &'a Vec<PlacedRectangularNode>, unremovable_points: &'a Vec<GridPoint>) -> Self {
        let mut grid_point_mask = vec![true; grid.size];
        let mut visibility_segment_mask = vec![true; grid.num_segments];
        let unremovable: HashSet<GridPoint> = unremovable_points.iter().copied().collect();

        for node in placed_nodes {
            let tl = node.top_left();
            let br = node.bottom_right();

            let (min_grid_x, max_grid_x, min_grid_y, max_grid_y) = Self::node_grid_bounds(grid, tl, br);

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
                    &unremovable,
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
                    &unremovable,
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
                    &unremovable,
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
                    &unremovable,
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

    pub(crate) fn fill_neighbors(
        &self,
        grid_point: GridPoint,
        orientation: Orientation,
        neighbors: &mut Vec<(GridPoint, Orientation)>,
    ) {
        neighbors.clear();

        let Some((x, y)) = self.grid.grid_point_to_grid_coords(grid_point) else {
            return;
        };

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
    }
}
