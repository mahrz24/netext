use hashbrown::hash_map::Keys;
use priority_queue::PriorityQueue;
use rstar::PointDistance;
use rstar::RTreeObject;
use std::cmp::max;
use std::cmp::min;
use std::cmp::Reverse;
use std::collections::BinaryHeap;
use std::collections::HashMap;
use std::hash::Hash;
use std::result;
use std::sync::Arc;

use pyo3::prelude::*;

use crate::geometry::PointLike;
use crate::{
    geometry::{BoundingBox, DirectedPoint, Direction, Neighborhood, PlacedRectangularNode, Point},
    pyindexset::PyIndexSet,
};

#[pyclass]
#[derive(Clone, PartialEq, Debug, Copy)]
pub struct RoutingConfig {
    neighborhood: Neighborhood,
    generate_trace: bool,
}

#[pymethods]
impl RoutingConfig {
    #[new]
    fn new(
        neighborhood: Neighborhood,
        generate_trace: Option<bool>,
    ) -> Self {
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
pub struct RoutingTrace {

}

#[pymethods]
impl RoutingTrace {
    #[new]
    fn new(
        cost_map: Option<HashMap<(i32, i32), f64>>,
        edge_cost_maps: Option<HashMap<(usize, usize), HashMap<(i32, i32), f64>>>,
    ) -> Self {
        RoutingTrace {

        }
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
        let MAX_ITERATIONS = 10;
        // First we generate a grid from all start and end point projections and midpoints.
        let mut x_coords = BinaryHeap::new();
        let mut y_coords = BinaryHeap::new();

        for (_, _, start, end, _) in &edges {
            x_coords.push(start.x);
            x_coords.push(end.x);
            y_coords.push(start.y);
            y_coords.push(end.y);
        }

        // For each pair of consecutive coordinates, we add their midpoint.
        let mut x_lines = Vec::new();
        let mut y_lines = Vec::new();

        let mut last_x = None;
        while let Some(x) = x_coords.pop() {
            if let Some(last_x) = last_x {
                if last_x < x - 1 {
                    x_lines.push((last_x + x) / 2);
                }
            }
            x_lines.push(x);
            last_x = Some(x);
        }
        let mut last_y = None;
        while let Some(y) = y_coords.pop() {
            if let Some(last_y) = last_y {
                if last_y < y - 1 {
                    y_lines.push((last_y + y) / 2);
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
        x_lines.insert(0,min_x);
        x_lines.push(max_x);
        y_lines.insert(0,min_y);
        y_lines.push(max_y);

        let grid_width = x_lines.len();
        let grid_height = y_lines.len();

        // Now all gridpoints are enumerated as integers from 0 to width * height - 1 and all possible
        // segments are also enumerated as integers from 0 to (width - 2) + (height - 2).

        // Then we remove all points that are inside any placed node and all edges that intersect
        // any placed node or are directly adjacent to a placed node.

        // We use a mask to remove

        // We also need to maintain usage on the original grid, initialized with usage from
        // existing edges.

        // Now we route all nets once, storing their paths and updating usage.

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


        let mut result_paths = Vec::new();
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
