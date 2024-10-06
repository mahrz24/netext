use pyo3::{exceptions::PyIndexError, prelude::*, types::PyType, PyClass};

pub trait PointLike {
    fn x(&self) -> i32;
    fn y(&self) -> i32;
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

pub trait PlacedNode: BoundingBox {
    fn contains_point(&self, point: &impl PointLike) -> bool;
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
        Ok(Point{ x: max_x, y: max_y })
    }

    #[classmethod]
    fn min_point(cls: &Bound<'_, PyType>, points: Vec<Point>) -> PyResult<Point> {
        let min_x = points.iter().map(|p| p.x()).min().unwrap_or(0);
        let min_y = points.iter().map(|p| p.y()).min().unwrap_or(0);
        Ok(Point{ x: min_x, y: min_y })
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
        RectangularNode {
            size
        }
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


impl PlacedNode for PlacedRectangularNode {
    fn contains_point(&self, point: &impl PointLike) -> bool {
        point.x() >= self.top_left().x
            && point.x() <= self.bottom_right().x
            && point.y() >= self.top_left().y
            && point.y() <= self.bottom_right().y
    }
}

#[pymethods]
impl PlacedRectangularNode {
    #[new]
    fn new(center: Point, node: RectangularNode) -> Self {
        PlacedRectangularNode {
            center, node
        }
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
            Direction::UpRight
            | Direction::UpLeft
            | Direction::DownRight
            | Direction::DownLeft => true,
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
#[derive(Clone, Eq, PartialEq, Hash, Copy, Debug)]
pub struct DirectedPoint {
    pub x: i32,
    pub y: i32,
    pub direction: Direction,
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

    #[getter]
    fn get_point(&self) -> PyResult<Point> {
        Ok(Point { x: self.x, y: self.y })
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
            0 => Ok(Py::new(py, Point { x: self.x, y: self.y })?.to_object(py)),
            1 => Ok(direction.to_object(py)),
            _ => Err(PyIndexError::new_err("index out of range")),
        }
    }
}
