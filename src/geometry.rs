use pyo3::{exceptions::PyIndexError, prelude::*, types::PyType, PyClass};
use rstar::PointDistance;
use std::hash::Hash;
use std::ops::{Mul, Sub};

pub trait PointLike {
    fn x(&self) -> i32;
    fn y(&self) -> i32;

    fn as_point(&self) -> Point {
        Point {
            x: self.x(),
            y: self.y(),
        }
    }
}

pub trait BoundingBox {
    fn top_left(&self) -> Point;
    fn bottom_right(&self) -> Point;

    fn bounding_box(&self) -> Rectangle {
        Rectangle {
            top_left: self.top_left().clone(),
            bottom_right: self.bottom_right().clone(),
        }
    }
}

pub trait Layoutable: PyClass {
    fn size(&self) -> Size;
}

#[pyclass]
#[derive(Clone, Debug, Hash, Eq, PartialEq, Copy)]
pub struct Size {
    pub width: i32,
    pub height: i32,
}

#[pymethods]
impl Size {
    #[new]
    pub fn new(width: i32, height: i32) -> Self {
        Size { width, height }
    }

    #[getter]
    pub fn width(&self) -> i32 {
        self.width
    }

    #[getter]
    pub fn height(&self) -> i32 {
        self.height
    }
}

#[pyclass]
#[derive(Clone, Debug, Hash, Eq, PartialEq, Copy)]
pub struct Point {
    pub x: i32,
    pub y: i32,
}

impl Sub for Point {
    type Output = Point;

    fn sub(self, other: Point) -> Point {
        Point {
            x: self.x - other.x,
            y: self.y - other.y,
        }
    }
}

impl<Scalar> Mul<Scalar> for Point
where
    Scalar: std::convert::Into<f64>,
{
    type Output = Point;

    fn mul(self, other: Scalar) -> Point {
        let other = other.into() as f64;
        Point {
            x: (self.x as f64 * other).round() as i32,
            y: (self.y as f64 * other).round() as i32,
        }
    }
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

    #[classmethod]
    fn max_point(cls: &Bound<'_, PyType>, points: Vec<Point>) -> PyResult<Point> {
        let max_x = points.iter().map(|p| p.x()).max().unwrap_or(0);
        let max_y = points.iter().map(|p| p.y()).max().unwrap_or(0);
        Ok(Point { x: max_x, y: max_y })
    }

    #[classmethod]
    fn min_point(cls: &Bound<'_, PyType>, points: Vec<Point>) -> PyResult<Point> {
        let min_x = points.iter().map(|p| p.x()).min().unwrap_or(0);
        let min_y = points.iter().map(|p| p.y()).min().unwrap_or(0);
        Ok(Point { x: min_x, y: min_y })
    }

    fn __eq__(&self, other: &Point) -> bool {
        self.x == other.x && self.y == other.y
    }

    fn __add__(&self, other: &Point) -> Point {
        Point {
            x: self.x + other.x,
            y: self.y + other.y,
        }
    }

    fn __sub__(&self, other: &Point) -> Point {
        Point {
            x: self.x - other.x,
            y: self.y - other.y,
        }
    }

    fn __mul__(&self, other: i32) -> Point {
        Point {
            x: self.x * other,
            y: self.y * other,
        }
    }

    fn __div__(&self, other: i32) -> Point {
        Point {
            x: self.x / other,
            y: self.y / other,
        }
    }

    fn distance_to_sqrd(&self, other: &Point) -> i32 {
        let x_diff = (self.x - other.x) as i32;
        let y_diff = (self.y - other.y) as i32;
        x_diff.pow(2) + y_diff.pow(2)
    }

    pub fn distance(&self, other: &Point) -> f64 {
        let x_diff = (self.x - other.x) as f64;
        let y_diff = (self.y - other.y) as f64;
        (x_diff.powi(2) + y_diff.powi(2)).sqrt()
    }

    pub fn length_as_vector(&self) -> f64 {
        let x = self.x as f64;
        let y = self.y as f64;
        (x.powi(2) + y.powi(2)).sqrt()
    }

    fn distance_to_max(&self, other: &Point) -> i32 {
        let x_diff = (self.x - other.x).abs();
        let y_diff = (self.y - other.y).abs();
        x_diff.max(y_diff)
    }

    fn as_tuple(&self) -> (i32, i32) {
        (self.x, self.y)
    }

    fn __len__(&self) -> PyResult<usize> {
        Ok(2) // The number of elements in the class
    }

    fn __getitem__(&self, idx: usize, py: Python<'_>) -> PyResult<PyObject> {
        match idx {
            0 => Ok(self.x.to_object(py)),
            1 => Ok(self.y.to_object(py)),
            _ => Err(PyIndexError::new_err("index out of range")),
        }
    }
}

impl rstar::Point for Point {
    type Scalar = i32;
    const DIMENSIONS: usize = 2;

    fn generate(mut generator: impl FnMut(usize) -> Self::Scalar) -> Self {
        Point {
            x: generator(0),
            y: generator(1),
        }
    }

    fn nth(&self, index: usize) -> Self::Scalar {
        match index {
            0 => self.x,
            1 => self.y,
            _ => panic!("Index out of bounds"),
        }
    }

    fn nth_mut(&mut self, index: usize) -> &mut Self::Scalar {
        match index {
            0 => &mut self.x,
            1 => &mut self.y,
            _ => panic!("Index out of bounds"),
        }
    }
}

impl PointLike for Point {
    fn x(&self) -> i32 {
        self.x
    }

    fn y(&self) -> i32 {
        self.y
    }
}

#[derive(Debug)]
pub struct Rectangle {
    top_left: Point,
    bottom_right: Point,
}

#[pyclass]
#[derive(Clone, Debug, Hash, Eq, PartialEq, Copy)]
pub struct RectangularNode {
    pub size: Size,
}

impl Layoutable for RectangularNode {
    fn size(&self) -> Size {
        self.size
    }
}

#[pymethods]
impl RectangularNode {
    #[new]
    fn new(size: Size) -> Self {
        RectangularNode { size }
    }
}

#[pyclass]
#[derive(Clone, Debug, Hash, Eq, PartialEq, Copy)]
pub struct PlacedRectangularNode {
    pub node: RectangularNode,
    pub center: Point,
}

impl BoundingBox for PlacedRectangularNode {
    fn top_left(&self) -> Point {
        Point {
            x: self.center.x - self.node.size.width / 2,
            y: self.center.y - self.node.size.height / 2,
        }
    }

    fn bottom_right(&self) -> Point {
        Point {
            x: self.center.x + self.node.size.width / 2,
            y: self.center.y + self.node.size.height / 2,
        }
    }
}

impl PointDistance for PlacedRectangularNode {
    fn distance_2(&self, point: &Point) -> i32 {
        let x = point.x();
        let y = point.y();
        let x1 = self.top_left().x;
        let y1 = self.top_left().y;
        let x2 = self.bottom_right().x;
        let y2 = self.bottom_right().y;

        if x < x1 {
            if y < y1 {
                return (x1 - x).pow(2) + (y1 - y).pow(2);
            } else if y > y2 {
                return (x1 - x).pow(2) + (y2 - y).pow(2);
            } else {
                return (x1 - x).pow(2);
            }
        } else if x > x2 {
            if y < y1 {
                return (x2 - x).pow(2) + (y1 - y).pow(2);
            } else if y > y2 {
                return (x2 - x).pow(2) + (y2 - y).pow(2);
            } else {
                return (x - x2).pow(2);
            }
        } else {
            if y < y1 {
                return (y1 - y).pow(2);
            } else if y > y2 {
                return (x2 - x).pow(2) + (y2 - y).pow(2);
            } else {
                return (x - x2).pow(2);
            }
        }
    }
}


#[pymethods]
impl PlacedRectangularNode {
    #[new]
    fn new(center: Point, node: RectangularNode) -> Self {
        PlacedRectangularNode { center, node }
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

#[pymethods]
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
            Direction::UpRight | Direction::UpLeft | Direction::DownRight | Direction::DownLeft => {
                true
            }
            _ => false,
        }
    }
}

impl Direction {
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
#[derive(Clone, Copy, Eq, Debug)]
pub struct DirectedPoint {
    pub x: i32,
    pub y: i32,
    pub direction: Direction,
    pub debug: bool,
}

impl PartialEq for DirectedPoint {
    fn eq(&self, other: &Self) -> bool {
        self.x == other.x && self.y == other.y && self.direction == other.direction
    }
}

impl Hash for DirectedPoint {
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        self.x.hash(state);
        self.y.hash(state);
        self.direction.hash(state);
    }
}

impl PointLike for DirectedPoint {
    fn x(&self) -> i32 {
        self.x
    }

    fn y(&self) -> i32 {
        self.y
    }
}

#[pymethods]
impl DirectedPoint {
    #[new]
    pub fn new(x: i32, y: i32, direction: Direction) -> Self {
        DirectedPoint {
            x,
            y,
            direction,
            debug: false,
        }
    }

    #[getter]
    fn get_debug(&self) -> PyResult<bool> {
        Ok(self.debug)
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

    #[getter]
    fn get_point(&self) -> PyResult<Point> {
        Ok(Point {
            x: self.x,
            y: self.y,
        })
    }

    fn __len__(&self) -> PyResult<usize> {
        Ok(2) // The number of elements in the class
    }

    fn __getitem__(&self, idx: usize, py: Python<'_>) -> PyResult<PyObject> {
        let direction = match Py::new(py, self.direction) {
            Ok(direction) => direction,
            Err(e) => return Err(e),
        };

        match idx {
            0 => Ok(Py::new(
                py,
                Point {
                    x: self.x,
                    y: self.y,
                },
            )?
            .to_object(py)),
            1 => Ok(direction.to_object(py)),
            _ => Err(PyIndexError::new_err("index out of range")),
        }
    }
}
