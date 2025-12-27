use petgraph::graph::NodeIndex;
use std::{cmp, collections::HashMap};

use pyo3::prelude::*;

use crate::{
    geometry::{Point, Size},
    graph::CoreGraph,
};

use super::LayoutEngine;

#[pyclass(extends=LayoutEngine, subclass)]
pub struct ForceDirectedLayout {
    width: i32,
    height: i32,
    iterations: i32,
    optimal_distance: i32,
    force_constant: f64,
}

#[pymethods]
impl ForceDirectedLayout {
    #[new]
    fn new() -> (Self, LayoutEngine) {
        (
            ForceDirectedLayout {
                width: 120,
                height: 40,
                iterations: 50,
                optimal_distance: 3,
                force_constant: 0.005,
            },
            LayoutEngine {},
        )
    }

    fn layout(&self, py: Python<'_>, graph: &CoreGraph) -> PyResult<Vec<(PyObject, Point)>> {
        let mut positions: HashMap<NodeIndex, Point> = graph
            .graph
            .nodes()
            .map(|node| {
                (
                    node,
                    Point {
                        x: (rand::random::<f64>() * self.width as f64).round() as i32,
                        y: (rand::random::<f64>() * self.height as f64).round() as i32,
                    },
                )
            })
            .collect();

        for _ in 0..self.iterations {
            let mut displacements: HashMap<NodeIndex, Point> = HashMap::new();

            // Calculate repulsive forces
            for u in graph.graph.nodes() {
                displacements.insert(u, Point { x: 0, y: 0 });
                for v in graph.graph.nodes() {
                    if u != v {
                        let delta = positions[&u] - positions[&v];
                        let distance = delta.length_as_vector();

                        let origin = Size::new(0, 0);
                        let size_u = graph.size_map.get(&u).unwrap_or(&origin);
                        let size_v = graph.size_map.get(&v).unwrap_or(&origin);

                        let min_distance =
                            cmp::max(size_u.height + size_v.height, size_u.width + size_v.width);

                        if distance > 0.0 {
                            let repulsive_force =
                                (self.optimal_distance.pow(2) as f64) / (distance as f64);
                            let adjustment =
                                delta * (repulsive_force / distance * self.force_constant);
                            let adjustment_min = delta * (repulsive_force / distance);
                            if distance < min_distance as f64 {
                                displacements.get_mut(&u).unwrap().x += adjustment_min.x;
                                displacements.get_mut(&u).unwrap().y += adjustment_min.y;
                            } else {
                                displacements.get_mut(&u).unwrap().x += adjustment.x;
                                displacements.get_mut(&u).unwrap().y += adjustment.y;
                            }
                        }
                    }
                }
            }

            for (u, v, _) in graph.graph.all_edges() {
                let delta = positions[&u] - positions[&v];
                let distance = delta.distance(&Point { x: 0, y: 0 });
                if distance > 0.0 {
                    let attractive_force =
                        ((distance.powi(2)) as f64) / (self.optimal_distance as f64);
                    let adjustment = delta * (attractive_force / distance * self.force_constant);
                    displacements.get_mut(&u).unwrap().x -= adjustment.x;
                    displacements.get_mut(&u).unwrap().y -= adjustment.y;
                    displacements.get_mut(&v).unwrap().x += adjustment.x;
                    displacements.get_mut(&v).unwrap().y += adjustment.y;
                }
            }

            // Update positions
            for node in graph.graph.nodes() {
                let displacement = displacements[&node];
                positions.get_mut(&node).unwrap().x += displacement.x;
                positions.get_mut(&node).unwrap().y += displacement.y;

                // Keep nodes within bounds
                positions.get_mut(&node).unwrap().x = positions[&node].x.clamp(0, self.width);
                positions.get_mut(&node).unwrap().y = positions[&node].y.clamp(0, self.height);
            }
        }

        Ok(positions
            .into_iter()
            .filter_map(|(node, point)| {
                let object = graph.object_map.get_index(node.index());
                object.map(|object| (object.clone_ref(py), point))
            })
            .collect())
    }
}
