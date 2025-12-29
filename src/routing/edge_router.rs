use std::collections::{HashMap, HashSet};
use std::fs;

use pyo3::prelude::*;
use rand::rngs::StdRng;
use rand::SeedableRng;
use serde_json::json;

use rstar::RTreeObject;

use crate::geometry::{BoundingBox, DirectedPoint, Direction, Orientation, PlacedRectangularNode, Point, PointLike};
use crate::pyindexset::PyIndexSet;

use super::grid::{Grid, GridPoint, RawPoint};
use super::masked_grid::MaskedGrid;
use super::ripup::{
    compute_overflow, order_edges_by_difficulty, rip_up_and_queue, routing_seed, select_edges_to_rip,
    start_end_grid_points, update_corner_history_cost, update_edge_history_cost,
};
use super::route_single::route_single_edge;
use super::trace::{build_trace_layout_data, record_iteration_trace};
use super::types::{EdgeRoutingResult, EdgeRoutingsResult, RoutingConfig};

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

impl Direction {
    pub(crate) fn to_orientation(&self) -> Orientation {
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

    fn add_node(&mut self, node: &Bound<PyAny>, placed_node: PlacedRectangularNode) -> PyResult<()> {
        // TODO check for inserting twice
        let node_index = self.object_map.insert_full(node)?.0;
        self.placed_nodes.insert(node_index, placed_node);
        self.placed_node_tree.insert(placed_node);
        Ok(())
    }

    fn add_edge(&mut self, start: &Bound<'_, PyAny>, end: &Bound<'_, PyAny>, line: Vec<Point>) -> PyResult<()> {
        let start_index = self.object_map.insert_full(start)?.0;
        let end_index = self.object_map.insert_full(end)?.0;

        self.existing_edges.insert((start_index, end_index), line.clone());

        Ok(())
    }

    fn remove_node(&mut self, node: &Bound<PyAny>) -> PyResult<()> {
        let index = self.object_map.get_full(node)?.map(|(index, _)| index);
        if let Some(index) = index {
            if let Some(placed_node) = self.placed_nodes.remove(&index) {
                self.placed_node_tree.remove(&placed_node);
            }
        }
        // TODO: Needs some cleanup of the object map at some point.
        Ok(())
    }

    fn remove_edge(&mut self, _py: Python<'_>, start: &Bound<'_, PyAny>, end: &Bound<'_, PyAny>) -> PyResult<()> {
        let start_index = self.object_map.insert_full(start)?.0;
        let end_index = self.object_map.insert_full(end)?.0;

        self.existing_edges.remove(&(start_index, end_index));

        // TODO: Needs some cleanup of the object map at some point.
        Ok(())
    }

    fn route_edges(
        &mut self,
        edges: Vec<(Bound<'_, PyAny>, Bound<'_, PyAny>, DirectedPoint, DirectedPoint, RoutingConfig)>,
    ) -> PyResult<EdgeRoutingsResult> {
        if edges.is_empty() {
            return Ok(EdgeRoutingsResult::new(Vec::new()));
        }

        let max_iterations = 10;
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

        // Convert all start and end points to grid points
        let start_end_grid_points: HashSet<GridPoint> = start_end_grid_points(&grid, &edges);

        let placed_nodes_vector = self.placed_nodes.values().cloned().collect();
        let start_end_grid_points_vector: Vec<GridPoint> = start_end_grid_points.iter().cloned().collect();

        let seed = routing_seed(&edges, &placed_nodes_vector);
        let mut rng: StdRng = StdRng::seed_from_u64(seed);

        let masked_grid = MaskedGrid::from_nodes(&grid, &placed_nodes_vector, &start_end_grid_points_vector);

        if trace_enabled {
            let (grid_points, nodes) = build_trace_layout_data(&grid, &masked_grid, &self.placed_nodes);
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

        let mut raw_history_cost_prefix_x = vec![0.0; ((raw_area.width()) * raw_area.height()) as usize];
        let mut raw_history_cost_prefix_y = vec![0.0; (raw_area.width() * (raw_area.height())) as usize];

        let mut result_paths: HashMap<(RawPoint, RawPoint), super::types::PathWithEndpoints> = HashMap::new();

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
                let overflow = if usage > capacity { usage - capacity } else { 0 };
                raw_cost[i] = 1.0 + lambda * (overflow as f64);
            }

            // Update prefix sums as the per edge costs have now all changed.
            raw_area.edge_prefix_sums(&raw_cost, &mut raw_cost_prefix_x, &mut raw_cost_prefix_y);
            raw_area.edge_prefix_sums(
                &raw_history_cost,
                &mut raw_history_cost_prefix_x,
                &mut raw_history_cost_prefix_y,
            );

            let sorted_edges = order_edges_by_difficulty(&op_edges, &placed_nodes_vector, &mut rng);

            let mut routed_edges_trace: Vec<((RawPoint, RawPoint), serde_json::Map<String, serde_json::Value>)> =
                Vec::new();
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
                update_corner_history_cost(&raw_corner_usage, &mut raw_corner_history, corner_capacity);

                // 6) Select edges to rip up
                op_edges.clear();

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

                op_edges =
                    rip_up_and_queue(&to_rip, &result_paths, &raw_area, &mut raw_usage, &mut raw_corner_usage);
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

        let mut directed_paths: Vec<Vec<DirectedPoint>> = Vec::with_capacity(edges.len());
        for (_u, _v, start, end, _config) in edges.iter() {
            let Some(start_raw_point) = raw_area.point_to_raw_point(&start.as_point()) else {
                directed_paths.push(Vec::new());
                continue;
            };
            let Some(end_raw_point) = raw_area.point_to_raw_point(&end.as_point()) else {
                directed_paths.push(Vec::new());
                continue;
            };
            let key = (start_raw_point, end_raw_point);
            let Some(path_with_endpoints) = result_paths.get(&key) else {
                directed_paths.push(Vec::new());
                continue;
            };
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
                PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Failed to serialize routing trace: {}", e))
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
        &mut self,
        u: &Bound<'_, PyAny>,
        v: &Bound<'_, PyAny>,
        start: DirectedPoint,
        end: DirectedPoint,
        _global_start: DirectedPoint,
        _global_end: DirectedPoint,
        config: RoutingConfig,
    ) -> PyResult<EdgeRoutingResult> {
        let edges = vec![(u.clone(), v.clone(), start, end, config)];
        let routed = self.route_edges(edges)?;
        let result_path = routed.paths.into_iter().next().unwrap_or_default();
        Ok(EdgeRoutingResult::new(result_path))
    }
}
