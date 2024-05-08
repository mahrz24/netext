use std::collections::HashMap;

use petgraph::graphmap::DiGraphMap;
use petgraph::visit::{NodeIndexable, Topo};
use pyo3::prelude::*;

use crate::{geometry::Point, graph::CoreGraph};

use super::LayoutEngine;

#[pyclass(extends=LayoutEngine, subclass)]
pub struct SugiyamaLayout {}

#[pymethods]
impl SugiyamaLayout {
    #[new]
    fn new() -> (Self, LayoutEngine) {
        (SugiyamaLayout {}, LayoutEngine {})
    }

    fn layout(&self, py: Python<'_>, graph: &CoreGraph) -> PyResult<Vec<(PyObject, Point)>> {
        Ok(vec![])
    }
}

impl SugiyamaLayout {
    fn longest_path_layering(&self, graph: &DiGraphMap<usize, ()>) -> HashMap<usize, usize> {
        let mut layers = HashMap::new();
        let mut topo = Topo::new(graph);

        // Initialize layering from the source nodes
        for node in graph.nodes() {
            if graph.edges_directed(node, petgraph::Incoming).count() == 0 {
                layers.insert(graph.to_index(node), 0);
            }
        }

        // Process nodes in topological order
        while let Some(node_idx) = topo.next(graph) {
            let node_layer = graph
                .edges_directed(node_idx, petgraph::Incoming)
                .filter_map(|edge| layers.get(&graph.to_index(edge.0)).map(|l| l + 1))
                .max()
                .unwrap_or(0); // Use 0 if no predecessors (source node)

            layers.insert(graph.to_index(node_idx), node_layer);
        }

        layers
    }
}
