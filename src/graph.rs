use petgraph::graph::NodeIndex;
use petgraph::graphmap::DiGraphMap;
use pyo3::types::PyAny;
use pyo3::{prelude::*, IntoPyObjectExt};
use std::collections::HashMap;

use crate::geometry::{PlacedRectangularNode, Point, Size};
use crate::pyindexset::PyIndexSet;
use crate::routing::EdgeRouter;

#[pyclass]
pub struct CoreGraph {
    pub graph: DiGraphMap<NodeIndex, ()>,
    pub object_map: PyIndexSet,
    data_map: HashMap<NodeIndex, PyObject>,
    pub size_map: HashMap<NodeIndex, Size>,
    edge_data_map: HashMap<(NodeIndex, NodeIndex), PyObject>,
    position_map: HashMap<NodeIndex, (f64, f64)>,
    router: Option<EdgeRouter>,
}

#[pymethods]
impl CoreGraph {
    #[new]
    fn new() -> Self {
        CoreGraph {
            graph: DiGraphMap::default(),
            object_map: PyIndexSet::default(),
            data_map: HashMap::default(),
            edge_data_map: HashMap::default(),
            size_map: HashMap::default(),
            position_map: HashMap::default(),
            router: None,
        }
    }

    #[staticmethod]
    fn from_edges(
        py: Python<'_>,
        edges: Vec<(Bound<'_, PyAny>, Bound<'_, PyAny>)>,
    ) -> PyResult<Self> {
        let mut graph = CoreGraph::new();
        for (a, b) in edges {
            graph.add_node(py, &a, None, None)?;
            graph.add_node(py, &b, None, None)?;
            graph.add_edge(py, &a, &b, None)?;
        }
        Ok(graph)
    }

    // Str representation of the graph
    fn __str__(&self) -> String {
        format!("{:?}", self.graph)
    }

    fn add_node(
        &mut self,
        py: Python<'_>,
        obj: &Bound<'_, PyAny>,
        data: Option<&Bound<'_, PyAny>>,
        size: Option<Size>,
    ) -> PyResult<()> {
        let (index, is_new) = self.object_map.insert_full(obj)?;
        let index = NodeIndex::new(index);

        if is_new {
            self.graph.add_node(index);
            if let Some(data) = data {
                self.data_map.insert(index, data.into_py_any(py).unwrap());
            }
            if let Some(size) = size {
                self.size_map.insert(index, size);
            }
        }
        Ok(())
    }

    fn add_edge(
        &mut self,
        _py: Python<'_>,
        obj_a: &Bound<'_, PyAny>,
        obj_b: &Bound<'_, PyAny>,
        data: Option<&Bound<'_, PyAny>>,
    ) -> PyResult<()> {
        let index_a = self.object_map.get_full(obj_a)?;
        let index_b = self.object_map.get_full(obj_b)?;

        if let (Some((index_a, _)), Some((index_b, _))) = (index_a, index_b) {
            let index_a = NodeIndex::new(index_a);
            let index_b = NodeIndex::new(index_b);
            self.graph.add_edge(index_a, index_b, ());
            if let Some(data) = data {
                self.edge_data_map
                    .insert((index_a, index_b), data.into_py_any(_py).unwrap());
            }
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "Both nodes must exist.",
            ));
        }
        Ok(())
    }

    fn remove_node(&mut self, obj: &Bound<'_, PyAny>) -> PyResult<()> {
        let index = self.object_map.get_full(obj)?;

        match index {
            Some((index, _)) => {
                let index: NodeIndex = NodeIndex::new(index);

                // Remove edges referencing this node from edge_data_map
                self.edge_data_map
                    .retain(|&(a, b), _| a != index && b != index);

                self.graph.remove_node(index);
                self.data_map.remove(&index);
                self.size_map.remove(&index);
                self.position_map.remove(&index);
                self.object_map.remove(obj)
            }
            None => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "Node does not exist.",
            )),
        }
    }

    fn remove_edge(&mut self, obj_a: &Bound<'_, PyAny>, obj_b: &Bound<'_, PyAny>) -> PyResult<()> {
        let index_a = self.object_map.get_full(obj_a)?;
        let index_b = self.object_map.get_full(obj_b)?;

        if let (Some((index_a, _)), Some((index_b, _))) = (index_a, index_b) {
            let index_a = NodeIndex::new(index_a);
            let index_b = NodeIndex::new(index_b);
            self.graph.remove_edge(index_a, index_b);
            self.edge_data_map.remove(&(index_a, index_b));
        }

        Ok(())
    }

    fn contains_node(&self, obj: &Bound<'_, PyAny>) -> PyResult<bool> {
        let index_a = self.object_map.get_full(obj)?;
        Ok(index_a.is_some())
    }

    fn contains_edge(&self, obj_a: &Bound<'_, PyAny>, obj_b: &Bound<'_, PyAny>) -> PyResult<bool> {
        let index_a = self.object_map.get_full(obj_a)?;
        let index_b = self.object_map.get_full(obj_b)?;

        if let (Some((index_a, _)), Some((index_b, _))) = (index_a, index_b) {
            let index_a = NodeIndex::new(index_a);
            let index_b = NodeIndex::new(index_b);
            return Ok(self.graph.contains_edge(index_a, index_b));
        }

        return Ok(false);
    }

    fn node_data_or_default(
        &self,
        py: Python<'_>,
        obj: &Bound<'_, PyAny>,
        default: &Bound<'_, PyAny>,
    ) -> PyResult<PyObject> {
        let index = self.object_map.get_full(obj)?;
        match index {
            Some((index, _)) => {
                let index = NodeIndex::new(index);
                match self.data_map.get(&index) {
                    Some(data) => Ok(data.clone_ref(py)),
                    None => Ok(default.clone().unbind()),
                }
            }
            None => Ok(default.clone().unbind()),
        }
    }

    pub fn node_data(&self, obj: &Bound<'_, PyAny>) -> PyResult<Option<&PyObject>> {
        let index = self.object_map.get_full(obj)?;
        match index {
            Some((index, _)) => {
                let index = NodeIndex::new(index);
                match self.data_map.get(&index) {
                    Some(data) => Ok(Some(data)),
                    None => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                        "Node does {:?} not contain any data.",
                        obj
                    ))),
                }
            }
            None => Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>(format!(
                "Node does {:?} not exist.",
                obj
            ))),
        }
    }

    fn edge_data(
        &self,
        obj_a: &Bound<'_, PyAny>,
        obj_b: &Bound<'_, PyAny>,
    ) -> PyResult<Option<&PyObject>> {
        let index_a = self.object_map.get_full(obj_a)?;
        let index_b = self.object_map.get_full(obj_b)?;

        if let (Some((index_a, _)), Some((index_b, _))) = (index_a, index_b) {
            let index_a = NodeIndex::new(index_a);
            let index_b = NodeIndex::new(index_b);
            match self.edge_data_map.get(&(index_a, index_b)) {
                Some(data) => Ok(Some(data)),
                None => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "Edge does not contain any data.",
                )),
            }
        } else {
            Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>(
                "Edge does not exist.",
            ))
        }
    }

    fn edge_data_or_default(
        &self,
        py: Python<'_>,
        obj_a: &Bound<'_, PyAny>,
        obj_b: &Bound<'_, PyAny>,
        default: &Bound<'_, PyAny>,
    ) -> PyResult<PyObject> {
        let index_a = self.object_map.get_full(obj_a)?;
        let index_b = self.object_map.get_full(obj_b)?;

        if let (Some((index_a, _)), Some((index_b, _))) = (index_a, index_b) {
            let index_a = NodeIndex::new(index_a);
            let index_b = NodeIndex::new(index_b);
            match self.edge_data_map.get(&(index_a, index_b)) {
                Some(data) => Ok(data.clone_ref(py)),
                None => Ok(default.clone().unbind()),
            }
        } else {
            Ok(default.clone().unbind())
        }
    }

    fn update_node_data(
        &mut self,
        py: Python<'_>,
        obj: &Bound<'_, PyAny>,
        data: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let index = self.object_map.get_full(obj)?;
        match index {
            Some((index, _)) => {
                let index = NodeIndex::new(index);
                self.data_map.insert(index, data.into_py_any(py).unwrap());
                Ok(())
            }
            None => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Node does {:?} not exist.",
                obj
            ))),
        }
    }

    pub fn update_edge_data(
        &mut self,
        py: Python<'_>,
        obj_a: &Bound<'_, PyAny>,
        obj_b: &Bound<'_, PyAny>,
        data: &Bound<'_, PyAny>,
    ) -> PyResult<()> {
        let index_a = self.object_map.get_full(obj_a)?;
        let index_b = self.object_map.get_full(obj_b)?;

        if let (Some((index_a, _)), Some((index_b, _))) = (index_a, index_b) {
            let index_a = NodeIndex::new(index_a);
            let index_b = NodeIndex::new(index_b);

            if self.graph.contains_edge(index_a, index_b) {
                self.edge_data_map
                    .insert((index_a, index_b), data.into_py_any(py).unwrap());
            } else {
                return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                    "Edge does not exist.",
                ));
            }
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "Both nodes must exist.",
            ));
        }
        Ok(())
    }

    pub fn node_size_or_default(&self, obj: &Bound<'_, PyAny>, default: &Size) -> PyResult<Size> {
        let index = self.object_map.get_full(obj)?;
        match index {
            Some((index, _)) => {
                let index = NodeIndex::new(index);
                match self.size_map.get(&index) {
                    Some(shape) => Ok(shape.clone()),
                    None => Ok(default.clone()),
                }
            }
            None => Ok(default.clone()),
        }
    }

    pub fn node_size(&self, obj: &Bound<'_, PyAny>) -> PyResult<Option<Size>> {
        let index = self.object_map.get_full(obj)?;
        match index {
            Some((index, _)) => {
                let index = NodeIndex::new(index);
                match self.size_map.get(&index) {
                    Some(size) => Ok(Some(size.clone())),
                    None => Ok(None),
                }
            }
            None => Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>(format!(
                "Node does {:?} not exist.",
                obj
            ))),
        }
    }

    pub fn update_node_size(&mut self, obj: &Bound<'_, PyAny>, size: &Size) -> PyResult<()> {
        let index = self.object_map.get_full(obj)?;
        match index {
            Some((index, _)) => {
                let index = NodeIndex::new(index);
                self.size_map.insert(index, size.clone());
                Ok(())
            }
            None => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Node does {:?} not exist.",
                obj
            ))),
        }
    }

    // --- Node position methods ---

    fn set_node_position(&mut self, obj: &Bound<'_, PyAny>, x: f64, y: f64) -> PyResult<()> {
        let index = self.object_map.get_full(obj)?;
        match index {
            Some((index, _)) => {
                let index = NodeIndex::new(index);
                self.position_map.insert(index, (x, y));
                Ok(())
            }
            None => Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>(format!(
                "Node {:?} does not exist.",
                obj
            ))),
        }
    }

    fn get_node_position(&self, obj: &Bound<'_, PyAny>) -> PyResult<(f64, f64)> {
        let index = self.object_map.get_full(obj)?;
        match index {
            Some((index, _)) => {
                let index = NodeIndex::new(index);
                match self.position_map.get(&index) {
                    Some(&(x, y)) => Ok((x, y)),
                    None => Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>(format!(
                        "Node {:?} has no position.",
                        obj
                    ))),
                }
            }
            None => Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>(format!(
                "Node {:?} does not exist.",
                obj
            ))),
        }
    }

    fn has_node_position(&self, obj: &Bound<'_, PyAny>) -> PyResult<bool> {
        let index = self.object_map.get_full(obj)?;
        match index {
            Some((index, _)) => {
                let index = NodeIndex::new(index);
                Ok(self.position_map.contains_key(&index))
            }
            None => Ok(false),
        }
    }

    fn remove_node_position(&mut self, obj: &Bound<'_, PyAny>) -> PyResult<()> {
        let index = self.object_map.get_full(obj)?;
        if let Some((index, _)) = index {
            let index = NodeIndex::new(index);
            self.position_map.remove(&index);
        }
        Ok(())
    }

    fn all_node_positions(&self) -> Vec<(&PyObject, (f64, f64))> {
        self.position_map
            .iter()
            .filter_map(|(index, &(x, y))| {
                self.object_map
                    .get_index(index.index())
                    .map(|obj| (obj, (x, y)))
            })
            .collect()
    }

    // --- Embedded router methods ---

    fn init_router(&mut self) {
        self.router = Some(EdgeRouter::new());
    }

    fn router_add_node(&mut self, node: &Bound<PyAny>, placed_node: PlacedRectangularNode) -> PyResult<()> {
        match &mut self.router {
            Some(router) => router.add_node(node, placed_node),
            None => Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Router not initialized. Call init_router() first.",
            )),
        }
    }

    fn router_add_edge(&mut self, start: &Bound<'_, PyAny>, end: &Bound<'_, PyAny>, line: Vec<Point>) -> PyResult<()> {
        match &mut self.router {
            Some(router) => router.add_edge(start, end, line),
            None => Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Router not initialized. Call init_router() first.",
            )),
        }
    }

    fn router_remove_node(&mut self, node: &Bound<PyAny>) -> PyResult<()> {
        match &mut self.router {
            Some(router) => router.remove_node(node),
            None => Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Router not initialized. Call init_router() first.",
            )),
        }
    }

    fn router_remove_edge(&mut self, py: Python<'_>, start: &Bound<'_, PyAny>, end: &Bound<'_, PyAny>) -> PyResult<()> {
        match &mut self.router {
            Some(router) => router.remove_edge(py, start, end),
            None => Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Router not initialized. Call init_router() first.",
            )),
        }
    }

    fn router_route_edges(
        &mut self,
        edges: Vec<(Bound<'_, PyAny>, Bound<'_, PyAny>, crate::geometry::DirectedPoint, crate::geometry::DirectedPoint, crate::routing::RoutingConfig)>,
    ) -> PyResult<crate::routing::EdgeRoutingsResult> {
        match &mut self.router {
            Some(router) => router.route_edges(edges),
            None => Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Router not initialized. Call init_router() first.",
            )),
        }
    }

    fn router_route_edge(
        &mut self,
        u: &Bound<'_, PyAny>,
        v: &Bound<'_, PyAny>,
        start: crate::geometry::DirectedPoint,
        end: crate::geometry::DirectedPoint,
        global_start: crate::geometry::DirectedPoint,
        global_end: crate::geometry::DirectedPoint,
        config: crate::routing::RoutingConfig,
    ) -> PyResult<crate::routing::EdgeRoutingResult> {
        match &mut self.router {
            Some(router) => router.route_edge(u, v, start, end, global_start, global_end, config),
            None => Err(PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                "Router not initialized. Call init_router() first.",
            )),
        }
    }

    // --- Existing methods ---

    pub fn all_nodes(&self) -> Vec<&PyObject> {
        // Would be more efficient to directly use the objects field of the PyIndexSet struct
        self.graph
            .nodes()
            .map(|n| self.object_map.get_index(n.index()).unwrap())
            .collect()
    }

    fn all_edges(&self) -> Vec<(&PyObject, &PyObject)> {
        let edges: Vec<(&PyObject, &PyObject)> = self
            .graph
            .all_edges()
            .filter_map(|(a, b, _)| {
                let obj_a = self.object_map.get_index(a.index());
                let obj_b = self.object_map.get_index(b.index());
                match (obj_a, obj_b) {
                    (Some(obj_a), Some(obj_b)) => Some((obj_a, obj_b)),
                    _ => None,
                }
            })
            .collect();
        edges
    }

    fn neighbors(&self, obj: &Bound<'_, PyAny>) -> PyResult<Vec<&PyObject>> {
        let index = self.object_map.get_full(obj)?;
        match index {
            Some((index, _)) => {
                let index = NodeIndex::new(index);
                let neighbors: Vec<&PyObject> = self
                    .graph
                    .neighbors_directed(index, petgraph::Direction::Incoming)
                    .chain(
                        self.graph
                            .neighbors_directed(index, petgraph::Direction::Outgoing),
                    )
                    .filter_map(|neighbour| self.object_map.get_index(neighbour.index()))
                    .collect();
                Ok(neighbors)
            }
            None => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Node does {:?} not exist.",
                obj
            ))),
        }
    }

    fn neighbors_outgoing(&self, obj: &Bound<'_, PyAny>) -> PyResult<Vec<&PyObject>> {
        let index = self.object_map.get_full(obj)?;
        match index {
            Some((index, _)) => {
                let index = NodeIndex::new(index);
                let neighbors: Vec<&PyObject> = self
                    .graph
                    .neighbors_directed(index, petgraph::Direction::Outgoing)
                    .filter_map(|neighbour| self.object_map.get_index(neighbour.index()))
                    .collect();
                Ok(neighbors)
            }
            None => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Node does {:?} not exist.",
                obj
            ))),
        }
    }

    fn neighbors_incoming(&self, obj: &Bound<'_, PyAny>) -> PyResult<Vec<&PyObject>> {
        let index = self.object_map.get_full(obj)?;
        match index {
            Some((index, _)) => {
                let index = NodeIndex::new(index);
                let neighbors: Vec<&PyObject> = self
                    .graph
                    .neighbors_directed(index, petgraph::Direction::Incoming)
                    .filter_map(|neighbour| self.object_map.get_index(neighbour.index()))
                    .collect();
                Ok(neighbors)
            }
            None => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Node does {:?} not exist.",
                obj
            ))),
        }
    }
}
