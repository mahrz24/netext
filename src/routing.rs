use priority_queue::PriorityQueue;
use rstar::PointDistance;
use rstar::RTreeObject;
use std::cmp::min;
use std::cmp::Reverse;
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
}


#[pymethods]
impl EdgeRouter {
    #[new]
    pub fn new() -> Self {
        EdgeRouter {
            placed_nodes: HashMap::default(),
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
        // The midpoints are to create lanes between nodes.

        // Then we remove all points that are inside any placed node and all edges that intersect
        // any placed node or are directly adjacent to a placed node.

        // We also need to maintain usage on the original grid, initialized with usage from
        // existing edges.

        // Now we route all nets once, storing their paths and updating usage.

        // Now we iterate up to some maximum number of iterations

        for _ in 0..MAX_ITERATIONS {
            // 1) Compute present costs from current usage

            // 2) Order nets by difficulty (span, channel width, past failures, etc.)

            // 3) For each net in order, find the cheapest path using A* or Dijkstra

            // Skip locked nets (no overflow)

            // Rip-up old path
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
