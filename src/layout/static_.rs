use pyo3::prelude::*;

use crate::{geometry::Point, graph::CoreGraph};

use super::LayoutEngine;

#[pyclass(extends=LayoutEngine, subclass)]
pub struct StaticLayout {
}

#[pymethods]
impl StaticLayout {
    #[new]
    fn new() -> (Self, LayoutEngine) {
        (StaticLayout {}, LayoutEngine {})
    }

    fn layout(&self, graph: &CoreGraph) -> PyResult<Vec<(PyObject, Point)>> {
        let mut node_data = Vec::new();
        for node in graph.all_nodes() {
            let node_data = graph.node_data(node)?;
            let x = node_data.get("$x").unwrap_or(&0.0);
            let y = node_data.get("$y").unwrap_or(&0.0);
            let point = Point::new(*x, *y);
            node_data.push((node, point));
        }
        Ok(node_data)
    }
}
