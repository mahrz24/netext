use priority_queue::PriorityQueue;
use rstar::RTreeObject;
use std::cmp::min;
use std::cmp::Reverse;
use std::collections::HashMap;
use std::hash::Hash;

use pyo3::prelude::*;

use crate::{
    geometry::{BoundingBox, DirectedPoint, Direction, Neighborhood, PlacedRectangularNode, Point},
    pyindexset::PyIndexSet,
};

#[pyclass]
#[derive(Clone, PartialEq, Debug, Copy)]
pub struct RoutingConfig {
    neighborhood: Neighborhood,
    corner_cost: i32,
    diagonal_cost: i32,
    line_cost: i32,
    shape_cost: i32,
    direction_change_margin: i32,
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
        direction_change_margin: i32
    ) -> Self {
        RoutingConfig {
            neighborhood,
            corner_cost,
            diagonal_cost,
            line_cost,
            shape_cost,
            direction_change_margin
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
            direction_change_margin: 1
        }
    }
}

fn heuristic(a: &DirectedPoint, b: &DirectedPoint, config: RoutingConfig) -> i32 {
    let lowest_distance = if config.neighborhood == Neighborhood::Orthogonal {
        (a.x - b.x).abs() + (a.y - b.y).abs()
    } else {
        (a.x - b.x).abs().max((a.y - b.y).abs())
    };

    let diagonal_cost = if config.diagonal_cost > 0 && b.direction.is_diagonal() {
        config.diagonal_cost
    } else {
        0
    };

    if a.direction == b.direction {
        (lowest_distance + diagonal_cost)*12
    } else {
        (lowest_distance + diagonal_cost + config.corner_cost)*12
    }
}

fn get_neighbors(
    node: &DirectedPoint,
    neighborhood: Neighborhood,
    allow_direction_change: bool,
) -> Vec<DirectedPoint> {
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

    let allowed_directions = if !allow_direction_change && node.direction != Direction::Center {
        match node.direction {
            Direction::Up => vec![Direction::Up, Direction::Down],
            Direction::UpRight => vec![Direction::UpRight, Direction::DownLeft],
            Direction::Right => vec![Direction::Right, Direction::Left],
            Direction::DownRight => vec![Direction::DownRight, Direction::UpLeft],
            Direction::Down => vec![Direction::Down, Direction::Up],
            Direction::DownLeft => vec![Direction::DownLeft, Direction::UpRight],
            Direction::Left => vec![Direction::Left, Direction::Right],
            Direction::UpLeft => vec![Direction::UpLeft, Direction::DownRight],
            Direction::Center => vec![Direction::Center],
        }
    } else {
        node.direction.other_directions(neighborhood)
    };

    // Changing direction
    for d in allowed_directions {
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

fn reconstruct_path<T: Eq + Hash + Copy>(
    came_from: &HashMap<T, T>,
    current: T,
) -> Vec<T> {
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
    pub existing_edges: HashMap<(usize, usize), Vec<Point>>,
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

impl EdgeRouter {
    fn transition_cost(
        &self,
        src: &DirectedPoint,
        dst: &DirectedPoint,
        config: &RoutingConfig,
    ) -> i32 {
        let mut cost: i32 = 0;

        if src.x != dst.x || src.y != dst.y {
            if src.direction.is_diagonal() {
                cost += 14 + config.diagonal_cost;
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
            if *self.line_occlusion.get(&(dst.x, dst.y)).unwrap_or(&0) > 0 {
                cost += config.line_cost;
            }
        }

        cost
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
        self.placed_node_tree.insert(placed_node);
        for x in placed_node.top_left().x..=placed_node.bottom_right().x {
            for y in placed_node.top_left().y..=placed_node.bottom_right().y {
                self.shape_occlusion
                    .entry((x, y))
                    .and_modify(|e| *e += 1)
                    .or_insert(1);
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
            self.line_occlusion
                .entry((point.x, point.y))
                .and_modify(|e| *e += 1)
                .or_insert(1);
        }

        self.existing_edges.insert((start_index, end_index), line);

        Ok(())
    }

    fn remove_node(&mut self, node: &Bound<PyAny>) -> PyResult<()> {
        let index = self.object_map.get_full(node)?.map(|(index, _)| index);
        if let Some(index) = index {
            for x in
                self.placed_nodes[&index].top_left().x..=self.placed_nodes[&index].bottom_right().x
            {
                for y in self.placed_nodes[&index].top_left().y
                    ..=self.placed_nodes[&index].bottom_right().y
                {
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
                self.line_occlusion
                    .entry((point.x, point.y))
                    .and_modify(|e| *e -= 1);
            }
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
    ) -> PyResult<Vec<Vec<DirectedPoint>>> {
        let mut result = Vec::new();

        for (u, v, start, end, config) in edges {
            let directed_points =
                self.route_edge(start, end, config)?;
            let path = directed_points
                .iter()
                .map(|p| Point::new(p.x, p.y))
                .collect();
            let _ = self.add_edge(&u, &v, path);
            result.push(directed_points);
        }
        Ok(result)
    }

    fn route_edge(
        &self,
        start: DirectedPoint,
        end: DirectedPoint,
        config: RoutingConfig,
    ) -> PyResult<Vec<DirectedPoint>> {
        let mut open_set = PriorityQueue::new();
        open_set.push(start, Reverse(0));

        let mut came_from = HashMap::new();
        let mut g_score = HashMap::new();
        g_score.insert(start, 0);

        let mut f_score = HashMap::new();
        f_score.insert(start, heuristic(&start, &end, config));

        while let Some((current, _)) = open_set.pop() {
            if current == end {
                return Ok(reconstruct_path(&came_from, current));
            }

            let current_end_distance = (current.x - end.x).abs() + (current.y - end.y).abs();
            let current_start_distance = (current.x - start.x).abs() + (current.y - start.y).abs();

            let current_distance = min(current_start_distance, current_end_distance);

            for neighbor in
                get_neighbors(&current, config.clone().neighborhood, current_distance > config.direction_change_margin)
            {
                let tentative_g_score = g_score.get(&current).unwrap_or(&(i32::MAX - 100))
                    + self.transition_cost(&current, &neighbor, &config);

                if tentative_g_score < *g_score.get(&neighbor).unwrap_or(&(i32::MAX - 100)) {
                    came_from.insert(neighbor, current);
                    g_score.insert(neighbor, tentative_g_score);
                    f_score.insert(
                        neighbor,
                        tentative_g_score + heuristic(&neighbor, &end, config),
                    );

                    open_set.push(neighbor, Reverse(*f_score.get(&neighbor).unwrap()));
                }
            }
        }

        Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
            "Goal not found.",
        ))
    }
}
