use std::collections::HashMap;

use pyo3::prelude::*;
use serde_json::json;

use crate::geometry::{BoundingBox, DirectedPoint, PlacedRectangularNode};

use super::grid::{Grid, GridPoint, RawPoint};
use super::masked_grid::MaskedGrid;
use super::raw_area::RawArea;
use super::types::{PathWithEndpoints, RoutingConfig};

pub(crate) fn build_trace_layout_data(
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

pub(crate) fn record_iteration_trace<'py>(
    iteration_logs: &mut Vec<serde_json::Value>,
    iteration: usize,
    routed_edges_trace: Vec<((RawPoint, RawPoint), serde_json::Map<String, serde_json::Value>)>,
    overflow_map: &HashMap<(RawPoint, RawPoint), bool>,
    result_paths: &HashMap<(RawPoint, RawPoint), PathWithEndpoints>,
    op_edges: &Vec<(Bound<'py, PyAny>, Bound<'py, PyAny>, DirectedPoint, DirectedPoint, RoutingConfig)>,
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
                .map(|dp| json!({ "x": dp.x, "y": dp.y, "direction": format!("{:?}", dp.direction) }))
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
