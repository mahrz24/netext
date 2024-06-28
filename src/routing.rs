use priority_queue::PriorityQueue;
use rstar::RTreeObject;
use std::{cmp::Reverse, hash::Hash};
use std::collections::{HashMap, HashSet};

use pyo3::prelude::*;

use crate::{
    geometry::{
        BoundingBox, DirectedPoint, Direction, Neighborhood, PlacedNode, PlacedRectangularNode,
        Point,
    },
    pyindexset::PyIndexSet,
};

#[pyclass]
#[derive(Clone, PartialEq, Debug)]
pub struct RoutingConfig {
    neighborhood: Neighborhood,
    corner_cost: i32,
    diagonal_cost: i32,
    line_cost: i32,
    shape_cost: i32,
}

#[pymethods]
impl RoutingConfig {
    #[new]
    fn new(
        neighborhood: Neighborhood,
        corner_cost: i32,
        diagonal_cost: i32,
        line_cost: i32,
        shape_cost: i32,
    ) -> Self {
        RoutingConfig {
            neighborhood,
            corner_cost,
            diagonal_cost,
            line_cost,
            shape_cost,
        }
    }
}

impl Default for RoutingConfig {
    fn default() -> Self {
        RoutingConfig {
            neighborhood: Neighborhood::Orthogonal,
            corner_cost: 1,
            diagonal_cost: 1,
            line_cost: 1,
            shape_cost: 1,
        }
    }
}

fn heuristic(a: &DirectedPoint, b: &DirectedPoint) -> i32 {
    ((((a.x - b.x).pow(2) + (a.y - b.y).pow(2)) as f64).sqrt() as i32) * 10
}

fn get_neighbors(node: &DirectedPoint, neighborhood: Neighborhood) -> Vec<DirectedPoint> {
    let mut neighbors = vec![];
    let x = node.x;
    let y = node.y;

    // Moving to another point in the current direction
    match node.direction {
        Direction::Up => neighbors.push(DirectedPoint::new(x, y - 1, Direction::Down)),
        Direction::UpRight => neighbors.push(DirectedPoint::new(x + 1, y - 1, Direction::DownLeft)),
        Direction::Right => neighbors.push(DirectedPoint::new(x + 1, y, Direction::Left)),
        Direction::DownRight => neighbors.push(DirectedPoint::new(x + 1, y + 1, Direction::UpLeft)),
        Direction::Down => neighbors.push(DirectedPoint::new(x, y + 1, Direction::Up)),
        Direction::DownLeft => neighbors.push(DirectedPoint::new(x - 1, y + 1, Direction::UpRight)),
        Direction::Left => neighbors.push(DirectedPoint::new(x - 1, y, Direction::Right)),
        Direction::UpLeft => neighbors.push(DirectedPoint::new(x - 1, y - 1, Direction::DownRight)),
        Direction::Center => neighbors.push(DirectedPoint::new(x, y, Direction::Center)),
    }

    // Changing direction
    for d in node.direction.other_directions(neighborhood) {
        match d {
            Direction::Up => neighbors.push(DirectedPoint::new(x, y, Direction::Up)),
            Direction::UpRight => neighbors.push(DirectedPoint::new(x, y, Direction::UpRight)),
            Direction::Right => neighbors.push(DirectedPoint::new(x, y, Direction::Right)),
            Direction::DownRight => neighbors.push(DirectedPoint::new(x, y, Direction::DownRight)),
            Direction::Down => neighbors.push(DirectedPoint::new(x, y, Direction::Down)),
            Direction::DownLeft => neighbors.push(DirectedPoint::new(x, y, Direction::DownLeft)),
            Direction::Left => neighbors.push(DirectedPoint::new(x, y, Direction::Left)),
            Direction::UpLeft => neighbors.push(DirectedPoint::new(x, y, Direction::UpLeft)),
            Direction::Center => neighbors.push(DirectedPoint::new(x, y, Direction::Center)),
        }
    }
    neighbors
}

fn reconstruct_path(
    came_from: &HashMap<DirectedPoint, DirectedPoint>,
    current: DirectedPoint,
) -> Vec<DirectedPoint> {
    let mut total_path = vec![current];
    let mut current = current;
    while let Some(&parent) = came_from.get(&current) {
        current = parent;
        total_path.push(current);
    }
    total_path.reverse();
    total_path
}

#[pyclass]
pub struct EdgeRouter {
    pub placed_nodes: HashMap<usize, PlacedRectangularNode>,
    pub placed_node_tree: rstar::RTree<PlacedRectangularNode>,
    pub object_map: PyIndexSet,
    pub shape_occlusion: HashMap<(i32, i32), i32>,
    pub line_occlusion: HashMap<(i32, i32), i32>,
    pub existing_edges: HashMap<(usize, usize), Vec<Point>>
}

impl RTreeObject for PlacedRectangularNode {
    type Envelope = rstar::AABB<[f32; 2]>;

    fn envelope(&self) -> Self::Envelope {
        let top_left = self.top_left();
        let bottom_right = self.bottom_right();
        rstar::AABB::from_corners(
            [top_left.x as f32, top_left.y as f32],
            [bottom_right.x as f32, bottom_right.y as f32],
        )
    }
}

impl RTreeObject for DirectedPoint {
    type Envelope = rstar::AABB<[f32; 2]>;

    fn envelope(&self) -> Self::Envelope {
        rstar::AABB::from_corners(
            [self.x as f32, self.y as f32],
            [self.x as f32, self.y as f32],
        )
    }
}

#[pymethods]
impl EdgeRouter {
    #[new]
    pub fn new() -> Self {
        EdgeRouter {
            placed_nodes: HashMap::default(),
            placed_node_tree: rstar::RTree::new(),
            object_map: PyIndexSet::default(),
            shape_occlusion: HashMap::default(),
            line_occlusion: HashMap::default(),
            existing_edges: HashMap::default()
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
        for x in placed_node.top_left().x..=placed_node.bottom_right().x {
            for y in placed_node.top_left().y..=placed_node.bottom_right().y {
                self.shape_occlusion.entry((x, y)).and_modify(|e| *e += 1).or_insert(1);
            }
        }

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

        for point in &line {
            self.line_occlusion.entry((point.x, point.y)).and_modify(|e| *e += 1).or_insert(1);
        }

        self.existing_edges.insert((start_index, end_index), line);

        Ok(())
    }

    fn remove_node(&mut self, node: &Bound<PyAny>) -> PyResult<()> {
        let index = self.object_map.get_full(node)?.map(|(index, _)| index);
        if let Some(index) = index {
            for x in self.placed_nodes[&index].top_left().x..=self.placed_nodes[&index].bottom_right().x {
                for y in self.placed_nodes[&index].top_left().y..=self.placed_nodes[&index].bottom_right().y {
                    self.shape_occlusion.entry((x, y)).and_modify(|e| *e -= 1);
                }
            }
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
            for point in line {
                self.line_occlusion.entry((point.x, point.y)).and_modify(|e| *e -= 1);
            }
            self.existing_edges.remove(&(start_index, end_index));
        }

        // TODO: Needs some cleanup of the object map at some point.
        Ok(())
    }

    fn transition_cost(
        &self,
        src: &DirectedPoint,
        dst: &DirectedPoint,
        config: &RoutingConfig,
    ) -> i32 {
        // TODO Use rtrees to find shapes
        let mut cost: i32 = 0;

        if src.x != dst.x || src.y != dst.y {
            if src.direction.is_diagonal() {
                cost += 14+config.diagonal_cost;
            } else {
                cost += 10;
            }
        }

        // Add corner cost if the direction turns (going from left to right is not a corner)
        if src.direction != dst.direction.opposite() {
            cost += config.corner_cost;
        }

        // Add shape cost if the edge intersects a shape
        if config.shape_cost > 0 {
            if *self.shape_occlusion.get(&(dst.x, dst.y)).unwrap_or(&0) > 0 {
                    cost += config.shape_cost;
            }
        }

        if config.line_cost > 0 {
            if *self.line_occlusion.get(&(dst.x, dst.y)).unwrap_or(&0) > 0  {
                cost += config.line_cost;
            }
        }

        cost
    }

    fn route_edge(
        &self,
        start: Point,
        end: Point,
        start_direction: Direction,
        end_direction: Direction,
        config: RoutingConfig,
    ) -> PyResult<Vec<DirectedPoint>> {
        // println!("Line occlusion:\n{:}", occlusion_map_as_string(&self.line_occlusion));
        // println!("Shape occlusion:\n{:}", occlusion_map_as_string(&self.shape_occlusion));

        let start = DirectedPoint::new(start.x, start.y, start_direction);
        let end = DirectedPoint::new(end.x, end.y, end_direction);

        let mut open_set = PriorityQueue::new();
        open_set.push(start, Reverse(0));

        let mut came_from = HashMap::new();
        let mut g_score = HashMap::new();
        g_score.insert(start, 0);

        let mut f_score = HashMap::new();
        f_score.insert(start, heuristic(&start, &end));

        while let Some((current, _)) = open_set.pop() {
            if current == end {
                return Ok(reconstruct_path(&came_from, current));
            }

            for neighbor in get_neighbors(&current, config.neighborhood) {
                let tentative_g_score = g_score.get(&current).unwrap_or(&(i32::MAX - 100))
                    + self.transition_cost(&current, &neighbor, &config);

                if tentative_g_score < *g_score.get(&neighbor).unwrap_or(&(i32::MAX - 100)) {
                    came_from.insert(neighbor, current);
                    g_score.insert(neighbor, tentative_g_score);
                    f_score.insert(neighbor, tentative_g_score + heuristic(&neighbor, &end));

                    open_set.push(neighbor, Reverse(*f_score.get(&neighbor).unwrap()));
                }
            }
        }

        Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Goal not found.",
        ))
    }
}

fn occlusion_map_as_string(occlusion_map: &HashMap<(i32, i32), i32>) -> String {
    let mut occlusion_map_string = String::new();
    let x_min = occlusion_map.keys().map(|(x, _)| x).min().unwrap_or(&0);
    let x_max = occlusion_map.keys().map(|(x, _)| x).max().unwrap_or(&0);
    let y_min = occlusion_map.keys().map(|(_, y)| y).min().unwrap_or(&0);
    let y_max = occlusion_map.keys().map(|(_, y)| y).max().unwrap_or(&0);
    for y in *y_min..=*y_max {
        for x in *x_min..=*x_max{
            occlusion_map_string.push_str(&occlusion_map.get(&(x, y)).unwrap_or(&0).to_string());
        }
        occlusion_map_string.push_str("\n");
    }
    occlusion_map_string
}
