use std::collections::HashMap;

use petgraph::algo::tarjan_scc;
use petgraph::graphmap::{DiGraphMap, GraphMap};
use petgraph::visit::VisitMap;
use petgraph::visit::{Dfs, Visitable, Walker};
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
        let mut raw_graph = graph.graph.clone();
        self.remove_cycles(&mut raw_graph);
        let layer_map = self.layer_disconnected_components(&raw_graph);

        // Convert layers from a node to layer index mapping to a list of nodes per layer
        let layers: Vec<Vec<usize>> = layer_map
            .into_iter()
            .fold(HashMap::new(), |mut acc, (node, layer)| {
                acc.entry(layer).or_insert_with(Vec::new).push(node);
                acc
            })
            .into_iter()
            .map(|(_, nodes)| nodes)
            .collect();

        let ordered_layers = self.barycenter_ordering(&raw_graph, &layers);
        let coordinates = self.brandes_koepf_coordinates(&ordered_layers, 100.0, 100.0);


        Ok(coordinates
            .into_iter()
            .map(|(node, point)| (graph.object_map[&node].clone_ref(py), point))
            .collect())
    }
}

impl SugiyamaLayout {
    // Function to assign coordinates using the Brandes-Köpf algorithm
    fn brandes_koepf_coordinates(
        &self,
        layers: &Vec<Vec<usize>>,
        node_width: f32,
        layer_height: f32,
    ) -> HashMap<usize, Point> {
        let mut positions = HashMap::new();
        let mut max_width = 0.0;

        for (layer_index, layer) in layers.iter().enumerate() {
            let y = layer_index as f32 * layer_height;
            let mut x = 0.0;

            for &node in layer {
                positions.insert(node, (x, y));
                x += node_width;
            }

            if x > max_width {
                max_width = x;
            }
        }

        // Adjust nodes to center layers
        for layer in layers {
            let layer_width = layer.len() as f32 * node_width;
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
        graph: &DiGraphMap<usize, ()>,
        layers: &Vec<Vec<usize>>,
    ) -> Vec<Vec<usize>> {
        let mut ordered_layers = layers.clone();

        for i in 1..layers.len() {
            let layer = layers[i].clone();
            let mut barycenters = Vec::new();

            for &node in &layer {
                let neighbors = graph.neighbors_directed(node, petgraph::Incoming);
                let neighbor_positions: Vec<_> = neighbors
                    .map(|n| layers[i - 1].iter().position(|&x| x == n).unwrap())
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

    fn remove_cycles(&self, graph: &mut DiGraphMap<usize, ()>) {
        let sccs = tarjan_scc(&*graph);
        for scc in sccs {
            if scc.len() > 1 {
                // It's a cycle
                // Remove an edge or handle the cycle
                // Example: remove the first edge that completes the cycle
                for window in scc.windows(2) {
                    graph.remove_edge(window[0], window[1]);
                }
            }
        }
    }

    fn layer_disconnected_components(
        &self,
        graph: &DiGraphMap<usize, ()>,
    ) -> HashMap<usize, usize> {
        let visited = graph.visit_map();
        let mut dfs = Dfs::empty(graph);
        let mut layers = HashMap::new();

        for node in graph.nodes() {
            if !visited.is_visited(&node) {
                let dfs_ref = &mut dfs;
                dfs_ref.move_to(node);
                let subgraph_nodes = dfs_ref.iter(graph).collect::<Vec<_>>();
                // Now layer this subgraph
                let mut subgraph = DiGraphMap::new();

                for sub_node in &subgraph_nodes {
                    subgraph.add_node(*sub_node);
                    for edge in graph.edges(*sub_node) {
                        subgraph.add_edge(edge.0, edge.1, ());
                    }
                }

                let component_layers = self.longest_path_layering(&subgraph); // Assuming a function that can handle a subgraph
                layers.extend(component_layers);
            }
        }
        layers
    }

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
