use std::cmp::{max, min};
use std::collections::hash_map::DefaultHasher;
use std::collections::{HashMap, HashSet};
use std::hash::{Hash, Hasher};

use pyo3::prelude::*;
use rand::Rng;

use crate::geometry::{BoundingBox, DirectedPoint, PlacedRectangularNode, PointLike};

use super::grid::{Grid, GridPoint, RawPoint};
use super::raw_area::RawArea;
use super::types::{PathWithEndpoints, RoutingConfig};

pub(crate) fn routing_seed(
    edges: &Vec<(Bound<'_, PyAny>, Bound<'_, PyAny>, DirectedPoint, DirectedPoint, RoutingConfig)>,
    nodes: &Vec<PlacedRectangularNode>,
) -> u64 {
    let mut hasher = DefaultHasher::new();
    edges.len().hash(&mut hasher);
    let mut edge_keys: Vec<(i32, i32, i32, i32, i32, i32)> = edges
        .iter()
        .map(|(_, _, start, end, _)| {
            (
                start.x,
                start.y,
                start.direction as i32,
                end.x,
                end.y,
                end.direction as i32,
            )
        })
        .collect();
    edge_keys.sort();
    for (sx, sy, sd, ex, ey, ed) in edge_keys {
        sx.hash(&mut hasher);
        sy.hash(&mut hasher);
        sd.hash(&mut hasher);
        ex.hash(&mut hasher);
        ey.hash(&mut hasher);
        ed.hash(&mut hasher);
    }

    nodes.len().hash(&mut hasher);
    let mut node_keys: Vec<(i32, i32, i32, i32)> = nodes
        .iter()
        .map(|node| (node.center.x, node.center.y, node.node.size.width, node.node.size.height))
        .collect();
    node_keys.sort();
    for (cx, cy, w, h) in node_keys {
        cx.hash(&mut hasher);
        cy.hash(&mut hasher);
        w.hash(&mut hasher);
        h.hash(&mut hasher);
    }
    hasher.finish()
}

pub(crate) fn start_end_grid_points(
    grid: &Grid,
    edges: &Vec<(Bound<'_, PyAny>, Bound<'_, PyAny>, DirectedPoint, DirectedPoint, RoutingConfig)>,
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

pub(crate) fn order_edges_by_difficulty<'py, R: Rng + ?Sized>(
    edges: &Vec<(Bound<'py, PyAny>, Bound<'py, PyAny>, DirectedPoint, DirectedPoint, RoutingConfig)>,
    nodes: &Vec<PlacedRectangularNode>,
    rng: &mut R,
) -> Vec<(Bound<'py, PyAny>, Bound<'py, PyAny>, DirectedPoint, DirectedPoint, RoutingConfig)> {
    let mut edges_with_score: Vec<(
        i32,
        (Bound<'_, PyAny>, Bound<'_, PyAny>, DirectedPoint, DirectedPoint, RoutingConfig),
    )> = Vec::new();

    for (u, v, start, end, config) in edges {
        // Add small reproducible noise to avoid fully deterministic ordering for similar edges.
        let noise: i32 = rng.gen_range(0..=10);
        let score = edge_difficulty(start, end, nodes) + noise;
        edges_with_score.push((score, (u.clone(), v.clone(), *start, *end, config.clone())));
    }
    edges_with_score.sort_by_key(|(score, _)| *score);
    edges_with_score.into_iter().map(|(_, edge)| edge).collect()
}

fn edge_difficulty(start: &DirectedPoint, end: &DirectedPoint, nodes: &Vec<PlacedRectangularNode>) -> i32 {
    let start_point = start.as_point();
    let end_point = end.as_point();

    let span = (start_point.x - end_point.x).abs() + (start_point.y - end_point.y).abs();
    let min_x = min(start_point.x, end_point.x);
    let max_x = max(start_point.x, end_point.x);
    let min_y = min(start_point.y, end_point.y);
    let max_y = max(start_point.y, end_point.y);

    let mut obstacle_area = 0;
    let total_area = (max_x - min_x) * (max_y - min_y);
    for node in nodes {
        let node_tl = node.top_left();
        let node_br = node.bottom_right();
        if node_tl.x <= max_x && node_br.x >= min_x && node_tl.y <= max_y && node_br.y >= min_y {
            obstacle_area += (min(node_br.x, max_x) - max(node_tl.x, min_x)).max(0)
                * (min(node_br.y, max_y) - max(node_tl.y, min_y)).max(0);
        }
    }

    -(span + ((200.0 * obstacle_area as f32 / (total_area as f32)).round()) as i32)
}

pub(crate) fn compute_overflow(
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

pub(crate) fn update_edge_history_cost(raw_usage: &[i32], raw_history_cost: &mut [f64], capacity: i32) {
    for (i, usage) in raw_usage.iter().enumerate() {
        if *usage > capacity {
            raw_history_cost[i] += (*usage - capacity) as f64;
        }
    }
}

pub(crate) fn update_corner_history_cost(
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

pub(crate) fn select_edges_to_rip<'py>(
    sorted_edges: &Vec<(Bound<'py, PyAny>, Bound<'py, PyAny>, DirectedPoint, DirectedPoint, RoutingConfig)>,
    result_paths: &HashMap<(RawPoint, RawPoint), PathWithEndpoints>,
    raw_area: &RawArea,
    raw_usage: &[i32],
    raw_corner_usage: &[i32],
    capacity: i32,
    corner_capacity: i32,
    trace_enabled: bool,
    overflow_map: &mut HashMap<(RawPoint, RawPoint), bool>,
) -> Vec<(Bound<'py, PyAny>, Bound<'py, PyAny>, DirectedPoint, DirectedPoint, RoutingConfig)> {
    let mut to_rip = Vec::new();

    for (u, v, start, end, config) in sorted_edges {
        let start_raw_point = raw_area.point_to_raw_point(&start.as_point()).unwrap();
        let end_raw_point = raw_area.point_to_raw_point(&end.as_point()).unwrap();

        let key = (start_raw_point, end_raw_point);
        let Some(routed_path) = result_paths.get(&key) else {
            continue;
        };

        if edge_path_has_overflow(routed_path, raw_area, raw_usage, raw_corner_usage, capacity, corner_capacity) {
            if trace_enabled {
                overflow_map.insert(key, true);
            }
            to_rip.push((u.clone(), v.clone(), *start, *end, config.clone()));
        }
    }

    to_rip
}

pub(crate) fn rip_up_and_queue<'py>(
    to_rip: &Vec<(Bound<'py, PyAny>, Bound<'py, PyAny>, DirectedPoint, DirectedPoint, RoutingConfig)>,
    result_paths: &HashMap<(RawPoint, RawPoint), PathWithEndpoints>,
    raw_area: &RawArea,
    raw_usage: &mut [i32],
    raw_corner_usage: &mut [i32],
) -> Vec<(Bound<'py, PyAny>, Bound<'py, PyAny>, DirectedPoint, DirectedPoint, RoutingConfig)> {
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
