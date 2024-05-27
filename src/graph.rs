use petgraph::graph::NodeIndex;
use petgraph::graphmap::DiGraphMap;
use pyo3::prelude::*;
use pyo3::types::PyAny;
use std::collections::HashMap;

use crate::geometry::NodeShape;
use crate::pyindexset::PyIndexSet;

#[pyclass]
pub struct CoreGraph {
    pub graph: DiGraphMap<NodeIndex, ()>,
    pub object_map: PyIndexSet,
    data_map: HashMap<NodeIndex, PyObject>,
    pub node_shape_map: HashMap<NodeIndex, NodeShape>,
    edge_data_map: HashMap<(NodeIndex, NodeIndex), PyObject>,
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
            node_shape_map: HashMap::default(),
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
        node_shape: Option<&NodeShape>,
    ) -> PyResult<()> {
        let (index, is_new) = self.object_map.insert_full(obj)?;
        let index = NodeIndex::new(index);

        if is_new {
            self.graph.add_node(index);
            if let Some(data) = data {
                self.data_map.insert(index, data.into_py(py));
            }
            if let Some(node_shape) = node_shape {
                self.node_shape_map.insert(index, node_shape.clone());
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
                    .insert((index_a, index_b), data.as_unbound().clone());
            }
        } else {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "Both nodes must exist.",
            ));
        }
        Ok(())
    }

    // fn remove_node(&mut self, obj: &Bound<'_, PyAny>) -> PyResult<()> {
    //     let hash = obj.hash()? as usize;
    //     if self.graph.contains_node(hash) {
    //         self.graph.remove_node(hash);
    //         self.object_map.remove(&hash);
    //         self.data_map.remove(&hash);
    //         let edges_to_remove: Vec<(usize, usize)> = self
    //             .edge_data_map
    //             .keys()
    //             .filter(|(a, b)| *a == hash || *b == hash)
    //             .cloned()
    //             .collect();
    //         for edge in edges_to_remove {
    //             self.edge_data_map.remove(&edge);
    //         }
    //     } else {
    //         return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
    //             "Node does not exist.",
    //         ));
    //     }
    //     Ok(())
    // }

    // fn remove_edge(&mut self, obj_a: &Bound<'_, PyAny>, obj_b: &Bound<'_, PyAny>) -> PyResult<()> {
    //     let hash_a = obj_a.hash()? as usize;
    //     let hash_b = obj_b.hash()? as usize;
    //     if self.graph.contains_node(hash_a) && self.graph.contains_node(hash_b) {
    //         if self.graph.contains_edge(hash_a, hash_b) {
    //             self.graph.remove_edge(hash_a, hash_b);
    //             self.edge_data_map.remove(&(hash_a, hash_b));
    //         } else {
    //             return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
    //                 "Edge does not exist.",
    //             ));
    //         }
    //     } else {
    //         return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
    //             "Both nodes must exist.",
    //         ));
    //     }
    //     Ok(())
    // }

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
        obj: &Bound<'_, PyAny>,
        default: &Bound<'_, PyAny>,
    ) -> PyResult<PyObject> {
        let index = self.object_map.get_full(obj)?;
        match index {
            Some((index, _)) => {
                let index = NodeIndex::new(index);
                match self.data_map.get(&index) {
                    Some(data) => Ok(data.clone()),
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
                Some(data) => Ok(data.clone()),
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
                self.data_map.insert(index, data.into_py(py));
                Ok(())
            }
            None => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Node does {:?} not exist.",
                obj
            ))),
        }
    }

    fn update_edge_data(
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
                    .insert((index_a, index_b), data.into_py(py));
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

    pub fn node_shape_or_default(
        &self,
        obj: &Bound<'_, PyAny>,
        default: &NodeShape,
    ) -> PyResult<NodeShape> {
        let index = self.object_map.get_full(obj)?;
        match index {
            Some((index, _)) => {
                let index = NodeIndex::new(index);
                match self.node_shape_map.get(&index) {
                    Some(shape) => Ok(shape.clone()),
                    None => Ok(default.clone()),
                }
            }
            None => Ok(default.clone()),
        }
    }

    pub fn node_shape(&self, obj: &Bound<'_, PyAny>) -> PyResult<Option<NodeShape>> {
        let index = self.object_map.get_full(obj)?;
        match index {
            Some((index, _)) => {
                let index = NodeIndex::new(index);
                match self.node_shape_map.get(&index) {
                    Some(shape) => Ok(Some(shape.clone())),
                    None => Ok(None),
                }
            }
            None => Err(PyErr::new::<pyo3::exceptions::PyKeyError, _>(format!(
                "Node does {:?} not exist.",
                obj
            ))),
        }
    }

    pub fn update_node_shape(
        &mut self,
        obj: &Bound<'_, PyAny>,
        shape: &NodeShape,
    ) -> PyResult<()> {
        let index = self.object_map.get_full(obj)?;
        match index {
            Some((index, _)) => {
                let index = NodeIndex::new(index);
                self.node_shape_map.insert(index, shape.clone());
                Ok(())
            }
            None => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Node does {:?} not exist.",
                obj
            ))),
        }
    }

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
                let neighbours: Vec<&PyObject> = self
                    .graph
                    .neighbors(index)
                    .filter_map(|neighbour| self.object_map.get_index(neighbour.index()))
                    .collect();
                Ok(neighbours)
            }
            None => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Node does {:?} not exist.",
                obj
            ))),
        }
    }
}
