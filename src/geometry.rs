use pyo3::{class, exceptions::PyIndexError, prelude::*};

#[pyclass]
#[derive(Clone, Debug, Hash, Eq, PartialEq, Copy)]
pub struct Point {
    pub x: i32,
    pub y: i32,
}

#[pymethods]
impl Point {
    #[new]
    pub fn new(x: i32, y: i32) -> Self {
        Point { x, y }
    }

    #[getter]
    pub fn x(&self) -> i32 {
        self.x
    }

    #[getter]
    pub fn y(&self) -> i32 {
        self.y
    }
}

#[derive(Debug)]
struct Rectangle {
    top_left: Point,
    bottom_right: Point,
}

#[pyclass]
#[derive(Clone, Debug, Hash, Eq, PartialEq, Copy)]
pub struct Shape {
    top_left: Point,
    bottom_right: Point,
}

#[pymethods]
impl Shape {
    #[new]
    fn new(top_left: Point, bottom_right: Point) -> Self {
        Shape {
            top_left,
            bottom_right,
        }
    }

    fn corner_points(&self) -> Vec<(i32, i32)> {
        let mut points = Vec::new();
        for x in [self.top_left.x, self.bottom_right.x].iter() {
            for y in [self.top_left.y, self.bottom_right.y].iter() {
                points.push((*x, *y));
            }
        }
        points
    }
}

#[pyclass]
#[derive(Clone, Copy, Eq, PartialEq, Hash, Debug)]
pub enum Neighborhood {
    #[pyo3(name = "ORTHOGONAL")]
    Orthogonal,
    #[pyo3(name = "MOORE")]
    Moore,
}

#[pyclass]
#[derive(Clone, Copy, Eq, PartialEq, Hash, Debug)]
pub enum Direction {
    #[pyo3(name = "CENTER")]
    Center = -1,
    #[pyo3(name = "UP")]
    Up = 0,
    #[pyo3(name = "DOWN")]
    Down = 1,
    #[pyo3(name = "LEFT")]
    Left = 2,
    #[pyo3(name = "RIGHT")]
    Right = 3,
    #[pyo3(name = "UP_RIGHT")]
    UpRight = 4,
    #[pyo3(name = "UP_LEFT")]
    UpLeft = 5,
    #[pyo3(name = "DOWN_RIGHT")]
    DownRight = 6,
    #[pyo3(name = "DOWN_LEFT")]
    DownLeft = 7,
}

impl Direction {
    pub fn opposite(&self) -> Direction {
        match self {
            Direction::Up => Direction::Down,
            Direction::Down => Direction::Up,
            Direction::Left => Direction::Right,
            Direction::Right => Direction::Left,
            Direction::UpRight => Direction::DownLeft,
            Direction::DownLeft => Direction::UpRight,
            Direction::UpLeft => Direction::DownRight,
            Direction::DownRight => Direction::UpLeft,
            Direction::Center => Direction::Center,
        }
    }

    pub fn is_diagonal(&self) -> bool {
        match self {
            Direction::UpRight
            | Direction::UpLeft
            | Direction::DownRight
            | Direction::DownLeft => true,
            _ => false,
        }
    }

    fn corner_cost(&self, other: Direction, corner_cost: f64) -> f64 {
        match (self, other) {
            (Direction::Up, Direction::Down) => 1.0,
            (Direction::Down, Direction::Up) => 1.0,
            (Direction::Left, Direction::Right) => 1.0,
            (Direction::Right, Direction::Left) => 1.0,
            (Direction::UpRight, Direction::DownLeft) => 1.0,
            (Direction::DownLeft, Direction::UpRight) => 1.0,
            (Direction::UpLeft, Direction::DownRight) => 1.0,
            (Direction::DownRight, Direction::UpLeft) => 1.0,
            _ => corner_cost,
        }
    }

    pub fn all_directions(neighborhood: Neighborhood) -> Vec<Direction> {
        match neighborhood {
            Neighborhood::Orthogonal => vec![
                Direction::Center,
                Direction::Up,
                Direction::Down,
                Direction::Left,
                Direction::Right,
            ],
            Neighborhood::Moore => vec![
                Direction::Center,
                Direction::Up,
                Direction::Down,
                Direction::Left,
                Direction::Right,
                Direction::UpRight,
                Direction::UpLeft,
                Direction::DownRight,
                Direction::DownLeft,
            ],
        }
    }

    pub fn other_directions(&self, neighborhood: Neighborhood) -> Vec<Direction> {
        Direction::all_directions(neighborhood)
            .iter()
            .filter(|&d| *d != *self)
            .cloned()
            .collect()
    }
}

#[pyclass]
#[derive(Clone, Eq, PartialEq, Hash, Copy, Debug)]
pub struct DirectedPoint {
    pub x: i32,
    pub y: i32,
    pub direction: Direction,
}

#[pymethods]
impl DirectedPoint {
    #[new]
    pub fn new(x: i32, y: i32, direction: Direction) -> Self {
        DirectedPoint { x, y, direction }
    }

    #[getter]
    fn get_x(&self) -> PyResult<i32> {
        Ok(self.x)
    }

    #[getter]
    fn get_y(&self) -> PyResult<i32> {
        Ok(self.y)
    }

    #[getter]
    fn get_direction(&self) -> PyResult<Direction> {
        Ok(self.direction.clone())
    }

    fn __len__(&self) -> PyResult<usize> {
        Ok(3) // The number of elements in the class
    }

    fn __getitem__(&self, idx: usize, py: Python<'_>) -> PyResult<PyObject> {
        let direction = match Py::new(py, self.direction) {
            Ok(direction) => direction,
            Err(e) => return Err(e),
        };

        match idx {
            0 => Ok(self.x.to_object(py)),
            1 => Ok(self.y.to_object(py)),
            2 => Ok(direction.to_object(py)),
            _ => Err(PyIndexError::new_err("index out of range")),
        }
    }
}
