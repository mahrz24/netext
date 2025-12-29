use pyo3::prelude::*;
use rand::Rng;
use serde_json::json;

use crate::geometry::{DirectedPoint, Orientation, Point, PointLike};

use super::astar::route_visibility_astar;
use super::grid::{Grid, GridPoint, RawPoint};
use super::masked_grid::MaskedGrid;
use super::raw_area::RawArea;
use super::types::{Path, PathWithEndpoints};

pub(crate) fn route_single_edge<R: Rng + ?Sized>(
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
    Option<((RawPoint, RawPoint), serde_json::Map<String, serde_json::Value>)>,
)> {
    let start_raw_point = raw_area
        .point_to_raw_point(&start.as_point())
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Start or end point is out of bounds"))?;
    let end_raw_point = raw_area
        .point_to_raw_point(&end.as_point())
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Start or end point is out of bounds"))?;

    let start_grid_point: GridPoint = grid
        .point_to_grid_point(&start.as_point())
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("Start point is not on a grid point"))?;
    let end_grid_point: GridPoint = grid
        .point_to_grid_point(&end.as_point())
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>("End point is not on a grid point"))?;

    let start_orientation: Orientation = start.direction.to_orientation();
    let end_orientation: Orientation = end.direction.to_orientation();

    let grid_path = match route_visibility_astar(
        masked_grid,
        start_grid_point,
        end_grid_point,
        start_orientation,
        end_orientation,
        rng,
        |from_idx, to_idx, from_orientation, to_orientation| {
            let from_point = grid.grid_point_to_point(from_idx).unwrap();
            let to_point = grid.grid_point_to_point(to_idx).unwrap();

            let turn_cost = if from_orientation != to_orientation { 1 } else { 0 };

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
    ) {
        Ok(path) => path,
        Err(_) => {
            // Fallback: build a simple L-shaped Manhattan path. This keeps rendering stable
            // in cases where the visibility graph is fully disconnected due to masking.
            let (sx, sy) = grid.grid_point_to_grid_coords(start_grid_point).unwrap_or((0, 0));
            let (ex, ey) = grid.grid_point_to_grid_coords(end_grid_point).unwrap_or((0, 0));

            let build = |mid_x: usize, mid_y: usize, first: Orientation, second: Orientation| {
                let mut out: Vec<(GridPoint, Orientation)> = Vec::new();
                out.push((start_grid_point, first));
                if let Some(mid) = grid.grid_coords_to_grid_point(mid_x, mid_y) {
                    if mid != start_grid_point {
                        out.push((mid, second));
                    }
                }
                if end_grid_point != start_grid_point {
                    out.push((end_grid_point, end_orientation));
                }
                out
            };

            let segment_clear = |mut ax: usize, mut ay: usize, bx: usize, by: usize| -> bool {
                if ax == bx && ay == by {
                    return true;
                }
                if ax != bx && ay != by {
                    return false;
                }
                if ax != bx {
                    let step = if bx > ax { 1isize } else { -1isize };
                    while ax != bx {
                        let next_x = (ax as isize + step) as usize;
                        let seg_idx = grid.grid_coords_to_segment_index((ax, ay), (next_x, ay));
                        if !masked_grid.segment_mask[seg_idx] {
                            return false;
                        }
                        ax = next_x;
                    }
                } else {
                    let step = if by > ay { 1isize } else { -1isize };
                    while ay != by {
                        let next_y = (ay as isize + step) as usize;
                        let seg_idx = grid.grid_coords_to_segment_index((ax, ay), (ax, next_y));
                        if !masked_grid.segment_mask[seg_idx] {
                            return false;
                        }
                        ay = next_y;
                    }
                }
                true
            };

            // Prefer the L-shape that stays within unmasked visibility segments (if possible).
            let horizontal_then_vertical_ok = segment_clear(sx, sy, ex, sy) && segment_clear(ex, sy, ex, ey);
            let vertical_then_horizontal_ok = segment_clear(sx, sy, sx, ey) && segment_clear(sx, ey, ex, ey);

            if horizontal_then_vertical_ok || !vertical_then_horizontal_ok {
                build(ex, sy, Orientation::Horizontal, Orientation::Vertical)
            } else {
                build(sx, ey, Orientation::Vertical, Orientation::Horizontal)
            }
        }
    };

    let grid_points: Vec<Point> = grid_path
        .iter()
        .map(|(grid_index, _)| {
            let (grid_x, grid_y) = grid.grid_point_to_raw_coords(*grid_index).unwrap();
            Point { x: grid_x, y: grid_y }
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
            .map(|dp| json!({ "x": dp.x, "y": dp.y, "direction": format!("{:?}", dp.direction) }))
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
        entry.insert("grid_path".to_string(), serde_json::Value::Array(grid_path_trace));
        entry.insert("raw_path".to_string(), serde_json::Value::Array(raw_path_trace));
        entry.insert(
            "directed_path".to_string(),
            serde_json::Value::Array(directed_trace),
        );
        Some(((start_raw_point, end_raw_point), entry))
    } else {
        None
    };

    Ok(((start_raw_point, end_raw_point), path_with_endpoints, trace_entry))
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
    if from_point == to_point {
        return 0.0;
    }

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

        raw_cost_prefix_y[upper_raw_point.0 as usize] - raw_cost_prefix_y[lower_raw_point.0 as usize]
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

        raw_cost_prefix_x[right_raw_point.0 as usize] - raw_cost_prefix_x[left_raw_point.0 as usize]
    }
}
