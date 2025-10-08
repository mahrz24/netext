use hashbrown::hash_map::Keys;
use petgraph::algo::k_shortest_path;
use priority_queue::PriorityQueue;
use rstar::PointDistance;
use rstar::RTreeObject;
use std::cmp::max;
use std::cmp::min;
use std::cmp::Reverse;
use std::collections::BinaryHeap;
use std::collections::HashMap;
use std::f64::INFINITY;
use std::hash::Hash;
use std::result;
use std::sync::Arc;

use pyo3::prelude::*;

use crate::geometry::Orientation;
use crate::geometry::PointLike;
use crate::{
    geometry::{BoundingBox, DirectedPoint, Direction, Neighborhood, PlacedRectangularNode, Point},
    pyindexset::PyIndexSet,
};
use std::collections::HashSet;

#[pyclass]
#[derive(Clone, PartialEq, Debug, Copy)]
pub struct RoutingConfig {
    neighborhood: Neighborhood,
    generate_trace: bool,
}

#[pymethods]
impl RoutingConfig {
    #[new]
    fn new(neighborhood: Neighborhood, generate_trace: Option<bool>) -> Self {
        RoutingConfig {
            neighborhood,
            generate_trace: generate_trace.unwrap_or(false),
        }
    }

    #[getter]
    fn get_generate_trace(&self) -> bool {
        self.generate_trace
    }

    #[setter]
    fn set_generate_trace(&mut self, value: bool) {
        self.generate_trace = value;
    }
}

impl Default for RoutingConfig {
    fn default() -> Self {
        RoutingConfig {
            neighborhood: Neighborhood::Orthogonal,
            generate_trace: false,
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
pub struct RoutingTrace {}

#[pymethods]
impl RoutingTrace {
    #[new]
    fn new(
        cost_map: Option<HashMap<(i32, i32), f64>>,
        edge_cost_maps: Option<HashMap<(usize, usize), HashMap<(i32, i32), f64>>>,
    ) -> Self {
        RoutingTrace {}
    }
}

#[pyclass]
#[derive(Clone, PartialEq, Debug)]
pub struct EdgeRoutingResult {
    pub path: Vec<DirectedPoint>,
    pub trace: Option<RoutingTrace>,
}

#[pymethods]
impl EdgeRoutingResult {
    #[new]
    fn new(path: Vec<DirectedPoint>, trace: Option<RoutingTrace>) -> Self {
        EdgeRoutingResult { path, trace }
    }

    #[getter]
    fn get_path(&self) -> Vec<DirectedPoint> {
        self.path.clone()
    }

    #[getter]
    fn get_trace(&self) -> Option<RoutingTrace> {
        self.trace.clone()
    }
}

#[pyclass]
#[derive(Clone, PartialEq, Debug)]
pub struct EdgeRoutingsResult {
    pub paths: Vec<Vec<DirectedPoint>>,
    pub trace: Option<RoutingTrace>,
}

#[pymethods]
impl EdgeRoutingsResult {
    #[new]
    fn new(paths: Vec<Vec<DirectedPoint>>, trace: Option<RoutingTrace>) -> Self {
        EdgeRoutingsResult { paths, trace }
    }

    #[getter]
    fn get_paths(&self) -> Vec<Vec<DirectedPoint>> {
        self.paths.clone()
    }

    #[getter]
    fn get_trace(&self) -> Option<RoutingTrace> {
        self.trace.clone()
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
        // Print all edges to be routed
        for (u, v, start, end, config) in &edges {
            println!(
                "Routing edge from {:?} to {:?} with start {:?} and end {:?} and config {:?}",
                u, v, start, end, config
            );
        }

        let MAX_ITERATIONS = 10;
        // First we generate a grid from all start and end point projections and midpoints.
        let mut x_coords = Vec::new();
        let mut y_coords = Vec::new();
        // Instead of pushing into BinaryHeap repeatedly,
        // accumulate unique x and y coordinates in HashSets.
        let mut x_set = HashSet::new();
        let mut y_set = HashSet::new();

        for (_, _, start, end, _) in &edges {
            x_set.insert(start.x);
            x_set.insert(end.x);
            y_set.insert(start.y);
            y_set.insert(end.y);
        }

        // Replace the original binary heaps with ones built from unique values.
        x_coords = x_set.into_iter().collect();
        y_coords = y_set.into_iter().collect();

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
                    x_lines.push(last_x + 2);
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

        print!("Initial y  lines: {:?}\n", y_lines);

        // Get the bounding box of all nodes
        let mut min_nodes_x = i32::MAX;
        let mut max_nodes_x = i32::MIN;
        let mut min_nodes_y = i32::MAX;
        let mut max_nodes_y = i32::MIN;

        self.placed_nodes.values().for_each(|node| {
            let tl = node.top_left();
            let br = node.bottom_right();
            min_nodes_x = min(min_nodes_x, tl.x);
            max_nodes_x = max(max_nodes_x, br.x);
            min_nodes_y = min(min_nodes_y, tl.y);
            max_nodes_y = max(max_nodes_y, br.y);
        });

        // We add some padding to the bounding box or use the min/max coordinates of the edges also padded.
        let padding = 10;
        let min_x = min(min_nodes_x - padding, x_lines[0] - padding);
        let max_x = max(max_nodes_x + padding, x_lines[x_lines.len() - 1] + padding);
        let min_y = min(min_nodes_y - padding, y_lines[0] - padding);
        let max_y = max(max_nodes_y + padding, y_lines[y_lines.len() - 1] + padding);

        // We add these to the grid keeping it sorted and unique.
        x_lines.insert(0, min_x);
        x_lines.push(max_x);
        y_lines.insert(0, min_y);
        y_lines.push(max_y);

        // Debug print x_lines and y_lines
        println!("x_lines: {:?}", x_lines);
        println!("y_lines: {:?}", y_lines);

        let raw_width = max_x - min_x + 1;
        let raw_height = max_y - min_y + 1;

        let grid_width = x_lines.len();
        let grid_height = y_lines.len();

        println!("Raw grid size: {} x {}", raw_width, raw_height);
        println!("Grid size: {} x {}", grid_width, grid_height);

        let grid_num_vertices = grid_width * grid_height;
        let grid_num_edges = (grid_width - 1) * grid_height + (grid_height - 1) * grid_width;

        let raw_num_vertices = raw_width * raw_height;
        let raw_num_edges = (raw_width - 1) * raw_height + (raw_height - 1) * raw_width;

        // Now all gridpoints are enumerated as integers from 0 to width * height - 1 and all possible
        // segments are also enumerated as integers from 0 to (width - 1) * height + (height - 1) * width - 1.

        // Then we remove all grid points that are inside any placed node and all edges that intersect
        // any placed node or are directly adjacent to a placed node.

        // We use a mask to remove these points and edges.
        let mut grid_point_mask = vec![true; grid_width * grid_height];
        let mut visibility_segment_mask = vec![true; grid_num_edges];

        for node in self.placed_nodes.values() {
            let tl = node.top_left();
            let br = node.bottom_right();

            println!(
                "Removing grid points and segments inside node {:?} spanning from {:?} to {:?}",
                node, tl, br
            );

            let min_grid_x = x_lines.binary_search(&tl.x).unwrap_or_else(|x| x);
            let max_grid_x = x_lines.binary_search(&br.x).unwrap_or_else(|x| x);
            let min_grid_y = y_lines.binary_search(&tl.y).unwrap_or_else(|y| y);
            let max_grid_y = y_lines.binary_search(&br.y).unwrap_or_else(|y| y);

            println!(
                "Node grid coords from ({}, {}) to ({}, {})",
                min_grid_x, min_grid_y, max_grid_x, max_grid_y
            );

            if min_grid_x == max_grid_x || min_grid_y == max_grid_y {
                // Node is too small to cover any grid points or segments
                continue;
            }

            for grid_y in min_grid_y..=max_grid_y {
                for grid_x in min_grid_x..=max_grid_x {
                    if let Some(grid_index) =
                        grid_coords_to_grid_index(grid_width, grid_height, grid_x, grid_y)
                    {
                        grid_point_mask[grid_index] = false;
                    }
                }
            }

            for grid_y in min_grid_y..=max_grid_y {
                for grid_x in min_grid_x..(max_grid_x) {
                    let segment_index = gridcoords_to_segment_index(
                        grid_width,
                        grid_height,
                        (grid_x, grid_y),
                        (grid_x + 1, grid_y),
                    );
                    visibility_segment_mask[segment_index] = false;
                }
            }

            for grid_y in min_grid_y..(max_grid_y) {
                for grid_x in min_grid_x..=max_grid_x {
                    let segment_index = gridcoords_to_segment_index(
                        grid_width,
                        grid_height,
                        (grid_x, grid_y),
                        (grid_x, grid_y + 1),
                    );
                    visibility_segment_mask[segment_index] = false;
                }
            }
        }

        debug_print_grid_buffer(
            raw_width,
            raw_height,
            grid_width,
            grid_height,
            &x_lines,
            &y_lines,
            &grid_point_mask,
        );

        // We also need to maintain usage and capacity on the raw grid, initialized with usage from
        // existing edges. We could also use capacity to change how edges are routed here.
        let mut raw_usage = vec![0; raw_num_edges as usize];
        let mut raw_capacity = vec![1; raw_num_edges as usize];

        // Create prefix sums along the x and y axes for fast capacity queries later.
        let mut raw_capacity_prefix_x = vec![0; ((raw_width - 1) * raw_height) as usize];
        let mut raw_capacity_prefix_y = vec![0; (raw_width * (raw_height - 1)) as usize];

        compute_raw_grid_edge_prefix_sums(
            raw_width,
            raw_height,
            raw_num_edges,
            &raw_capacity,
            &mut raw_capacity_prefix_x,
            &mut raw_capacity_prefix_y,
        );

        let mut raw_usage_prefix_x = vec![0; ((raw_width - 1) * raw_height) as usize];
        let mut raw_usage_prefix_y = vec![0; (raw_width * (raw_height - 1)) as usize];

        compute_raw_grid_edge_prefix_sums(
            raw_width,
            raw_height,
            raw_num_edges,
            &raw_usage,
            &mut raw_usage_prefix_x,
            &mut raw_usage_prefix_y,
        );

        debug_print_raw_edge_buffer(raw_width, raw_height, &raw_capacity);

        // With the prefix sums, we can also compute usage and capacity on the grid edges.
        // for the initial routing, the usage is zero everywhere and the cose is just the length of the edge.
        // hence we can pass a simplified cost function to the A*

        let mut initial_result_paths: Vec<Vec<DirectedPoint>> = Vec::new();

        // Now we route all edges once, storing their paths and updating usage.
        for (u, v, start, end, _) in edges {
            let start_raw_index =
                point_to_raw_index(min_x, min_y, raw_width, raw_height, &start.as_point());
            let end_raw_index =
                point_to_raw_index(min_x, min_y, raw_width, raw_height, &end.as_point());

            if start_raw_index.is_none() || end_raw_index.is_none() {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "Start or end point is out of bounds",
                ));
            }
            let start_raw_index = start_raw_index.unwrap();
            let end_raw_index = end_raw_index.unwrap();

            let start_orientation: Orientation = match start.direction {
                Direction::Up | Direction::Down => Orientation::Vertical,
                Direction::Left | Direction::Right => Orientation::Horizontal,
                Direction::UpLeft | Direction::DownRight | Direction::Center => Orientation::Vertical,
                Direction::UpRight | Direction::DownLeft => Orientation::Horizontal,

            };
            let end_orientation: Orientation = match end.direction {
                Direction::Up | Direction::Down => Orientation::Vertical,
                Direction::Left | Direction::Right => Orientation::Horizontal,
  Direction::UpLeft | Direction::DownRight | Direction::Center => Orientation::Vertical,
                Direction::UpRight | Direction::DownLeft => Orientation::Horizontal,
            };

            let start_grid_index: usize = point_to_grid_index(
                &x_lines,
                &y_lines,
                grid_width,
                grid_height,
                &start.as_point(),
            )
            .ok_or_else(|| {
                PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "Start point is not on a grid point",
                )
            })?;
            let end_grid_index: usize =
                point_to_grid_index(&x_lines, &y_lines, grid_width, grid_height, &end.as_point())
                    .ok_or_else(|| {
                    PyErr::new::<pyo3::exceptions::PyValueError, _>(
                        "End point is not on a grid point",
                    )
                })?;
            println!("Routing edge from {:?} to {:?} with start grid coords {:?} and end grid coords {:?}", u, v, start_grid_index, end_grid_index);

            let grid_path = route_visibility_astar(
                grid_width,
                grid_height,
                &grid_point_mask,
                &visibility_segment_mask,
                start_grid_index,
                end_grid_index,
                start_orientation,
                end_orientation,
                |idx, orientation| {
                    // Neighbors function
                    let (x, y) = grid_index_to_grid_coords(grid_width, grid_height, idx);
                    let mut neighbors = Vec::new();
                    // We can always only move in the direction of our orientation
                    match orientation {
                        Orientation::Horizontal => {
                            // Move left
                            if x > 0 {
                                if let Some(neighbor_index) =
                                    grid_coords_to_grid_index(grid_width, grid_height, x - 1, y)
                                {
                                    let segment_index = gridcoords_to_segment_index(
                                        grid_width,
                                        grid_height,
                                        (x - 1, y),
                                        (x, y),
                                    );
                                    if visibility_segment_mask[segment_index] {
                                        neighbors.push((neighbor_index, Orientation::Horizontal));
                                    }
                                }
                            }
                            // Move right
                            if x + 1 < grid_width {
                                if let Some(neighbor_index) =
                                    grid_coords_to_grid_index(grid_width, grid_height, x + 1, y)
                                {
                                    let segment_index = gridcoords_to_segment_index(
                                        grid_width,
                                        grid_height,
                                        (x, y),
                                        (x + 1, y),
                                    );
                                    if visibility_segment_mask[segment_index] {
                                        neighbors.push((neighbor_index, Orientation::Horizontal));
                                    }
                                }
                            }
                        }
                        Orientation::Vertical => {
                            // Move up
                            if y > 0 {
                                if let Some(neighbor_index) =
                                    grid_coords_to_grid_index(grid_width, grid_height, x, y - 1)
                                {
                                    let segment_index = gridcoords_to_segment_index(
                                        grid_width,
                                        grid_height,
                                        (x, y - 1),
                                        (x, y),
                                    );
                                    if visibility_segment_mask[segment_index] {
                                        neighbors.push((neighbor_index, Orientation::Vertical));
                                    }
                                }
                            }
                            // Move down
                            if y + 1 < grid_height {
                                if let Some(neighbor_index) =
                                    grid_coords_to_grid_index(grid_width, grid_height, x, y + 1)
                                {
                                    let segment_index = gridcoords_to_segment_index(
                                        grid_width,
                                        grid_height,
                                        (x, y),
                                        (x, y + 1),
                                    );
                                    if visibility_segment_mask[segment_index] {
                                        neighbors.push((neighbor_index, Orientation::Vertical));
                                    }
                                }
                            }
                        }
                    }
                    neighbors
                },
                |from_idx, to_idx, from_orientation, to_orientation| {
                    // Cost function
                    let (from_grid_x, from_grid_y) =
                        grid_index_to_grid_coords(grid_width, grid_height, from_idx);
                    let (to_grid_x, to_grid_y) =
                        grid_index_to_grid_coords(grid_width, grid_height, to_idx);

                    let from_actual_x = x_lines[from_grid_x];
                    let from_actual_y = y_lines[from_grid_y];
                    let to_actual_x = x_lines[to_grid_x];
                    let to_actual_y = y_lines[to_grid_y];

                    let distance =
                        (from_actual_x - to_actual_x).abs() + (from_actual_y - to_actual_y).abs();
                    let orientation_cost = if from_orientation != to_orientation {
                        10
                    } else {
                        0
                    };
                    distance + orientation_cost
                },
            )?;
            // Convert grid path to actual points with directions
            let mut result_path = Vec::new();
            for (grid_index, orientation) in grid_path {
                let (grid_x, grid_y) =
                    grid_index_to_grid_coords(grid_width, grid_height, grid_index);
                let point = grid_coords_to_point(&x_lines, &y_lines, grid_width, grid_height, grid_x, grid_y);
                let direction = match orientation {
                    Orientation::Horizontal => {
                        if result_path.last().map_or(false, |p: &DirectedPoint| p.x < point.x) {
                            Direction::Right
                        } else if result_path.last().map_or(false, |p: &DirectedPoint| p.x > point.x) {
                            Direction::Left
                        } else {
                            Direction::Center
                        }
                    }
                    Orientation::Vertical => {
                        if result_path.last().map_or(false, |p: &DirectedPoint| p.y < point.y) {
                            Direction::Up
                        } else if result_path.last().map_or(false, |p: &DirectedPoint| p.y > point.y) {
                            Direction::Down
                        } else {
                            Direction::Center
                        }
                    }
                };
                result_path.push(DirectedPoint { x: point.x, y: point.y, direction, debug: false });
            }
        }

        // Now we iterate up to some maximum number of iterations

        for _ in 0..MAX_ITERATIONS {
            // 1) Compute present costs from current usage

            // 2) Order nets by difficulty (span, channel width, past failures, etc.)

            // 3) For each net in order, find the cheapest path using A* or Dijkstra

            // a) Skip locked nets (no overflow)

            // b) Rip-up old path

            // c) Build avoid mask (edges that overflowed last iteration)

            // d) Try local repair or global reroute

            // e) If successful, update usage

            // 4) If no nets overflowed, we're done
        }


        Ok(EdgeRoutingsResult::new(result_paths, None))
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
        let mut result_path = Vec::new();
        Ok(EdgeRoutingResult::new(result_path, None))
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
struct GridState {
    index: usize,
    orientation: Orientation,
}

fn route_visibility_astar<NeighborFn, CostFn>(
    grid_width: usize,
    grid_height: usize,
    grid_point_mask: &[bool],
    _visibility_segment_mask: &[bool],
    start_grid_index: usize,
    end_grid_index: usize,
    start_orientation: Orientation,
    end_orientation: Orientation,
    mut neighbors_fn: NeighborFn,
    mut cost_fn: CostFn,
) -> PyResult<Vec<(usize, Orientation)>>
where
    NeighborFn: FnMut(usize, Orientation) -> Vec<(usize, Orientation)>,
    CostFn: FnMut(usize, usize, Orientation, Orientation) -> i32,
{
    if start_grid_index >= grid_point_mask.len() || end_grid_index >= grid_point_mask.len() {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Start or end grid index out of bounds",
        ));
    }

    if !grid_point_mask[start_grid_index] || !grid_point_mask[end_grid_index] {
        return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Start or end grid point is blocked",
        ));
    }

    let start_state = GridState {
        index: start_grid_index,
        orientation: start_orientation,
    };
    let goal_state = GridState {
        index: end_grid_index,
        orientation: end_orientation,
    };

    if start_state == goal_state {
        return Ok(vec![(start_state.index, start_state.orientation)]);
    }

    let goal_coords = grid_index_to_grid_coords(grid_width, grid_height, goal_state.index);

    let heuristic = |state: GridState| -> i32 {
        let (sx, sy) = grid_index_to_grid_coords(grid_width, grid_height, state.index);
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

        for (neighbor_index, neighbor_orientation) in
            neighbors_fn(current_state.index, current_state.orientation)
        {
            if neighbor_index >= grid_point_mask.len() {
                continue;
            }

            if !grid_point_mask[neighbor_index] {
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

fn grid_coords_to_point(
    x_lines: &Vec<i32>,
    y_lines: &Vec<i32>,
    grid_width: usize,
    grid_height: usize,
    grid_x: usize,
    grid_y: usize,
) -> Point {
    assert!(grid_x < grid_width);
    assert!(grid_y < grid_height);
    Point {
        x: x_lines[grid_x],
        y: y_lines[grid_y],
    }
}

fn point_to_grid_index(
    x_lines: &Vec<i32>,
    y_lines: &Vec<i32>,
    grid_width: usize,
    grid_height: usize,
    point: &Point,
) -> Option<usize> {
    let grid_x = x_lines.binary_search(&point.x).ok()?;
    let grid_y = y_lines.binary_search(&point.y).ok()?;
    grid_coords_to_grid_index(grid_width, grid_height, grid_x, grid_y)
}

fn grid_coords_to_grid_index(
    grid_width: usize,
    grid_height: usize,
    grid_x: usize,
    grid_y: usize,
) -> Option<usize> {
    if grid_x >= grid_width || grid_y >= grid_height {
        return None;
    }
    Some(grid_y * grid_width + grid_x)
}

fn grid_index_to_grid_coords(
    grid_width: usize,
    grid_height: usize,
    grid_index: usize,
) -> (usize, usize) {
    assert!(grid_index < grid_width * grid_height);
    let grid_y = grid_index / grid_width;
    let grid_x = grid_index % grid_width;
    (grid_x, grid_y)
}

fn point_to_raw_index(
    min_x: i32,
    min_y: i32,
    raw_width: i32,
    raw_height: i32,
    point: &Point,
) -> Option<usize> {
    if point.x < min_x
        || point.x >= min_x + raw_width
        || point.y < min_y
        || point.y >= min_y + raw_height
    {
        return None;
    }
    Some(((point.y - min_y) * raw_width + (point.x - min_x)) as usize)
}

fn raw_index_to_point(
    min_x: i32,
    min_y: i32,
    raw_width: i32,
    raw_height: i32,
    raw_index: usize,
) -> Point {
    assert!(raw_index < (raw_width * raw_height) as usize);
    let y = (raw_index as i32) / raw_width;
    let x = (raw_index as i32) % raw_width;
    Point {
        x: min_x + x,
        y: min_y + y,
    }
}

fn gridcoords_to_segment_index(
    grid_width: usize,
    grid_height: usize,
    grid_a: (usize, usize),
    grid_b: (usize, usize),
) -> usize {
    assert!(grid_a.0 < grid_width);
    assert!(grid_a.1 < grid_height);
    assert!(grid_b.0 < grid_width);
    assert!(grid_b.1 < grid_height);
    if grid_a.0 == grid_b.0 {
        // Vertical segment
        // If y differs by more than one, this is not a grid segment
        assert!(grid_a.1 + 1 == grid_b.1 || grid_b.1 + 1 == grid_a.1);
        let min_y = min(grid_a.1, grid_b.1);
        let x = grid_a.0;
        assert!(min_y < grid_height - 1);
        (grid_width - 1) * grid_height + x * (grid_height - 1) + min_y
    } else if grid_a.1 == grid_b.1 {
        // Horizontal segment
        let y = grid_a.1;
        // If x differs by more than one, this is not a grid segment
        assert!(grid_a.0 + 1 == grid_b.0 || grid_b.0 + 1 == grid_a.0);
        let min_x = min(grid_a.0, grid_b.0);
        assert!(min_x < grid_width - 1);
        y * (grid_width - 1) + min_x
    } else {
        panic!("Grid coordinates are not adjacent");
    }
}

fn segment_index_to_gridcoords(
    grid_width: usize,
    grid_height: usize,
    segment_index: usize,
) -> ((usize, usize), (usize, usize)) {
    assert!(segment_index < (grid_width - 1) * grid_height + (grid_height - 1) * grid_width);
    if segment_index < (grid_width - 1) * grid_height {
        // Horizontal segment
        let grid_y = segment_index / (grid_width - 1);
        let grid_x = segment_index % (grid_width - 1);
        ((grid_x, grid_y), (grid_x + 1, grid_y))
    } else {
        // Vertical segment
        let vertical_index = segment_index - (grid_width - 1) * grid_height;
        let grid_x = vertical_index / (grid_height - 1);
        let grid_y = vertical_index % (grid_height - 1);
        ((grid_x, grid_y), (grid_x, grid_y + 1))
    }
}

fn compute_raw_grid_edge_prefix_sums(
    raw_width: i32,
    raw_height: i32,
    raw_number_edges: i32,
    values: &Vec<i32>,
    prefix_x: &mut Vec<i32>,
    prefix_y: &mut Vec<i32>,
) {
    assert!(values.len() == raw_number_edges as usize);
    assert!(prefix_x.len() == ((raw_width - 1) * raw_height) as usize);
    assert!(prefix_y.len() == (raw_width * (raw_height - 1)) as usize);

    // Fill horizontal prefix sums
    for y in 0..raw_height {
        let mut sum = 0;
        for x in 0..(raw_width - 1) {
            let edge_index = (y * (raw_width - 1) + x) as usize;
            sum += values[edge_index];
            prefix_x[edge_index] = sum;
        }
    }

    // Fill vertical prefix sums
    let offset = ((raw_width - 1) * raw_height) as usize;
    for x in 0..raw_width {
        let mut sum = 0;
        for y in 0..(raw_height - 1) {
            let edge_index = ((raw_width - 1) * raw_height + x * (raw_height - 1) + y) as usize;
            sum += values[edge_index];
            prefix_y[edge_index - offset] = sum;
        }
    }
}

fn debug_print_raw_buffer<T: std::fmt::Display>(width: i32, height: i32, buffer: &Vec<T>) {
    for y in 0..height {
        for x in 0..width {
            let index = (y * width + x) as usize;
            print!(" {}  ", buffer[index]);
        }
        println!();
    }
    println!();
}

fn debug_print_grid_buffer<T: std::fmt::Display>(
    raw_width: i32,
    raw_height: i32,
    grid_width: usize,
    grid_height: usize,
    x_lines: &Vec<i32>,
    y_lines: &Vec<i32>,
    buffer: &Vec<T>,
) {
    for raw_y in 0..raw_height {
        print!("Y{:3} ", y_lines[0] + raw_y);
        for raw_x in 0..raw_width {
            let point = Point {
                x: x_lines[0] + raw_x as i32,
                y: y_lines[0] + raw_y as i32,
            };

            if let Some(grid_index) =
                point_to_grid_index(x_lines, y_lines, grid_width, grid_height, &point)
            {
                print!("{:5}", buffer[grid_index]);
            } else {
                print!("  .  ");
            }
        }
        println!();
    }
    println!();
}

fn debug_print_raw_edge_buffer<T: std::fmt::Display>(
    raw_width: i32,
    raw_height: i32,
    buffer: &Vec<T>,
) {
    // Print horizontal edges
    for y in 0..raw_height {
        // Print horizontal edge row
        print!("  .");
        for x in 0..(raw_width - 1) {
            let edge_index = (y * (raw_width - 1) + x) as usize;
            print!("{:3}  .", buffer[edge_index]);
        }
        println!();

        // Print vertical edge row
        if y < raw_height - 1 {
            for x in 0..raw_width {
                let edge_index = ((raw_width - 1) * raw_height + x * (raw_height - 1) + y) as usize;
                print!("{:3} ", buffer[edge_index]);
                if x < raw_width - 1 {
                    print!("  ");
                }
            }
            println!();
        }
    }
    println!();
}
