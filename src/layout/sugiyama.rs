use std::collections::HashMap;

use petgraph::algo::greedy_feedback_arc_set;
use petgraph::graph::NodeIndex;
use petgraph::graphmap::DiGraphMap;
use petgraph::unionfind::UnionFind;
use petgraph::visit::IntoEdgeReferences;
use petgraph::visit::{NodeIndexable, Topo};
use pyo3::prelude::*;

use crate::geometry::Size;
use crate::{geometry::Point, graph::CoreGraph};

use super::{LayoutDirection, LayoutEngine};

#[pyclass(extends=LayoutEngine, subclass)]
pub struct SugiyamaLayout {
    direction: LayoutDirection,
}

#[pymethods]
impl SugiyamaLayout {
    #[new]
    fn new(direction: LayoutDirection) -> (Self, LayoutEngine) {
        (
            SugiyamaLayout {
                direction: direction,
            },
            LayoutEngine {},
        )
    }

    #[getter]
    fn get_layout_direction(&self) -> Option<LayoutDirection> {
        Some(self.direction)
    }

    fn layout(&self, py: Python<'_>, graph: &CoreGraph) -> PyResult<Vec<(PyObject, Point)>> {
        let mut raw_graph = graph.graph.clone();

        self.remove_cycles(&mut raw_graph, &graph.graph);
        let layer_map = self.layer_disconnected_components(&raw_graph);

        // Convert layers from a node to layer index mapping to a list of nodes per layer
        let mut int_layers: Vec<(usize, Vec<usize>)> = layer_map
            .into_iter()
            .fold(HashMap::new(), |mut acc, (node, layer)| {
                acc.entry(layer).or_insert_with(Vec::new).push(node);
                acc
            })
            .into_iter()
            .collect();

        int_layers.sort_by_key(|(k, _v)| *k);

        let layers = int_layers
            .into_iter()
            .map(|(_, mut v)| {
                v.sort_by_key(|&x| x);
                v
            })
            .collect();

        let ordered_layers = self.barycenter_ordering(&raw_graph, &layers);
        let coordinates = self.brandes_koepf_coordinates(&ordered_layers, graph);

        // In case of left right layout, we need to rotate the coordinates
        let final_coordinates: HashMap<usize, Point> =
            if self.direction == LayoutDirection::LeftRight {
                coordinates
                    .into_iter()
                    .map(|(node, point)| {
                        let new_point = Point::new(point.y, point.x);
                        (node, new_point)
                    })
                    .collect()
            } else {
                coordinates
            };

        Ok(final_coordinates
            .into_iter()
            .filter_map(|(node, point)| {
                let object = graph
                    .object_map
                    .get_index(graph.graph.from_index(node).index());
                object.map(|object| (object.clone_ref(py), point))
            })
            .collect())
    }
}

fn width_in_direction(direction: LayoutDirection, size: &Size) -> i32 {
    match direction {
        LayoutDirection::TopDown => size.width(),
        LayoutDirection::LeftRight => size.height(),
    }
}

fn height_in_direction(direction: LayoutDirection, size: &Size) -> i32 {
    match direction {
        LayoutDirection::TopDown => size.height(),
        LayoutDirection::LeftRight => size.width(),
    }
}

impl SugiyamaLayout {
    // Function to assign coordinates using the Brandes-Köpf algorithm
    fn brandes_koepf_coordinates(
        &self,
        layers: &Vec<Vec<usize>>,
        graph: &CoreGraph,
    ) -> HashMap<usize, Point> {
        let mut positions = HashMap::new();
        let mut max_width = 0.0;
        let mut layer_widths = HashMap::new();

        for (layer_index, layer) in layers.iter().enumerate() {
            let node_sizes: Vec<Option<&Size>> = layer
                .into_iter()
                .map(|&node|
                // TODO Access pattern is not nice here, this should be private for the core graph
                graph.size_map.get(&graph.graph.from_index(node)))
                .collect();

            let layer_height = node_sizes.iter().fold(0, |acc, size| {
                acc.max(height_in_direction(
                    self.direction,
                    size.unwrap_or(&Size::new(0, 0)),
                ))
            });

            let y = layer_index as f32 * (layer_height as f32 + 1.0);
            let mut x = 0.0;

            for (&node, size) in layer.into_iter().zip(node_sizes) {
                positions.insert(node, (x, y));
                x += width_in_direction(self.direction, size.unwrap_or(&Size::new(0, 0))) as f32;
            }

            if x > max_width {
                max_width = x;
            }

            layer_widths.insert(layer_index, x);
        }

        // Adjust nodes to center layers (TODO we should make sure to align the nodes to some kind of grid, not just center them)
        for (layer_index, layer) in layers.iter().enumerate() {
            let layer_width = layer_widths[&layer_index];
            let offset = (max_width - layer_width) / 2.0;

            for &node in layer {
                if let Some((x, _y)) = positions.get_mut(&node) {
                    *x += offset;
                }
            }
        }

        // Convert float tuples to Points
        positions
            .into_iter()
            .map(|(node, (x, y))| (node, Point::new(x as i32, y as i32)))
            .collect()
    }

    fn barycenter_ordering(
        &self,
        graph: &DiGraphMap<NodeIndex, ()>,
        layers: &Vec<Vec<usize>>,
    ) -> Vec<Vec<usize>> {
        let mut ordered_layers = layers.clone();

        for i in 1..layers.len() {
            let layer = layers[i].clone();
            let mut barycenters = Vec::new();

            for &node in &layer {
                let neighbors =
                    graph.neighbors_directed(graph.from_index(node), petgraph::Incoming);
                let neighbor_positions: Vec<_> = neighbors
                    .map(|n| {
                        layers[i - 1]
                            .iter()
                            .position(|&x| x == graph.to_index(n))
                            .unwrap_or(0)
                    })
                    .collect();

                let barycenter = if neighbor_positions.is_empty() {
                    0.0
                } else {
                    neighbor_positions.iter().sum::<usize>() as f32
                        / neighbor_positions.len() as f32
                };

                barycenters.push((node, barycenter));
            }

            barycenters.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap());
            ordered_layers[i] = barycenters.into_iter().map(|(node, _)| node).collect();
        }

        ordered_layers
    }

    fn remove_cycles(
        &self,
        tgt_graph: &mut DiGraphMap<NodeIndex, ()>,
        src_graph: &DiGraphMap<NodeIndex, ()>,
    ) {
        let edges_to_remove = greedy_feedback_arc_set(src_graph);
        for edge in edges_to_remove {
            tgt_graph.remove_edge(edge.0, edge.1);
            if edge.0 != edge.1 {
                tgt_graph.add_edge(edge.1, edge.0, ());
            }
        }
    }

    fn layer_disconnected_components(
        &self,
        graph: &DiGraphMap<NodeIndex, ()>,
    ) -> HashMap<usize, usize> {
        let mut layers = HashMap::new();
        let mut vertex_sets = UnionFind::new(graph.node_bound());

        for edge in graph.edge_references() {
            let (a, b) = (edge.0, edge.1);

            // union the two vertices of the edge
            vertex_sets.union(graph.to_index(a), graph.to_index(b));
        }

        let labels = vertex_sets.into_labeling();

        let mut subgraphs = HashMap::<usize, DiGraphMap<NodeIndex, ()>>::new();

        // Add nodes to subgraphs
        for node in graph.nodes() {
            subgraphs
                .entry(labels[graph.to_index(node)])
                .or_insert_with(|| DiGraphMap::new())
                .add_node(node);
        }

        // Add edges to subgraphs
        for edge in graph.edge_references() {
            let (a, b) = (edge.0, edge.1);
            let a_label = labels[graph.to_index(a)];
            let b_label = labels[graph.to_index(b)];

            // This should always be the case.
            if a_label == b_label {
                subgraphs.get_mut(&a_label).unwrap().add_edge(a, b, ());
            }
        }

        for (_, subgraph) in subgraphs {
            let component_layers = self.longest_path_layering(&subgraph); // Assuming a function that can handle a subgraph
            layers.extend(
                component_layers
                    .into_iter()
                    .map(|(node, layer)| (graph.to_index(subgraph.from_index(node)), layer)),
            );
        }

        layers
    }

    fn longest_path_layering(&self, graph: &DiGraphMap<NodeIndex, ()>) -> HashMap<usize, usize> {
        let mut layers = HashMap::new();
        let mut topo = Topo::new(graph);

        if graph.node_count() == 0 {
            return layers;
        }

        if graph.node_count() == 1 {
            layers.insert(graph.to_index(graph.nodes().next().unwrap()), 0);
            return layers;
        }

        // Initialize layering from the source nodes
        for node in graph.nodes().filter(|n| {
            graph
                .neighbors_directed(*n, petgraph::Incoming)
                .next()
                .is_none()
        }) {
            layers.insert(graph.to_index(node), 0);
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
