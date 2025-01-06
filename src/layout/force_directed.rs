use petgraph::graph::NodeIndex;
use std::{cmp, collections::HashMap, ops::Sub};

use pyo3::{exceptions, prelude::*, types::PyDict};

use crate::{geometry::{Point, Size}, graph::CoreGraph};

use super::LayoutEngine;

#[pyclass(extends=LayoutEngine, subclass)]
pub struct ForceDirectedLayout {}

#[pymethods]
impl ForceDirectedLayout {
    #[new]
    fn new() -> (Self, LayoutEngine) {
        (ForceDirectedLayout {}, LayoutEngine {})
    }

    fn layout(&self, py: Python<'_>, graph: &CoreGraph) -> PyResult<Vec<(PyObject, Point)>> {
        let width = 100;
        let height = 100;
        let iterations = 50;
        let k: i32 = 3;

        let mut positions: HashMap<NodeIndex, Point> = graph
            .graph
            .nodes()
            .map(|node| {
                (
                    node,
                    Point {
                        x: (rand::random::<f64>() * width as f64).round() as i32,
                        y: (rand::random::<f64>() * height as f64).round() as i32,
                    },
                )
            })
            .collect();

        println!("{:?}", positions);

        for _ in 0..iterations {
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

                        let min_distance = cmp::max(size_u.height + size_v.height, size_u.width + size_v.width);

                        if distance > 0.0 {
                            let repulsive_force = (k.pow(2) as f64) / (distance as f64);
                            let adjustment = delta * (repulsive_force / distance * 0.01);
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

            // Calculate attractive forces
            for (u, v, _) in graph.graph.all_edges() {
                let delta = positions[&u] - positions[&v];
                let distance = delta.distance(&Point { x: 0, y: 0 });
                if distance > 0.0 {
                    let attractive_force = ((distance.powi(2)) as f64) / (k as f64);
                    let adjustment = delta * (attractive_force / distance * 0.01);
                    displacements.get_mut(&u).unwrap().x -= adjustment.x;
                    displacements.get_mut(&u).unwrap().y -= adjustment.y;
                    displacements.get_mut(&v).unwrap().x += adjustment.x;
                    displacements.get_mut(&v).unwrap().y += adjustment.y;
                }
            }

            println!("{:?}", displacements);

            // Update positions
            for node in graph.graph.nodes() {
                let displacement = displacements[&node];
                positions.get_mut(&node).unwrap().x += displacement.x;
                positions.get_mut(&node).unwrap().y += displacement.y;

                // Keep nodes within bounds
                positions.get_mut(&node).unwrap().x = positions[&node].x.clamp(0, width);
                positions.get_mut(&node).unwrap().y = positions[&node].y.clamp(0, height);
            }

            println!("{:?}", positions);
            println!("=====================");
        }

        Ok(positions
            .into_iter()
            .filter_map(|(node, point)| {
                let object = graph
                    .object_map
                    .get_index(node.index());
                object.map(|object| (object.clone_ref(py), point))
            })
            .collect())
    }
}
