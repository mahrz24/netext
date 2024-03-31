use pyo3::exceptions::PyIndexError;
use pyo3::prelude::*;
use pyo3::wrap_pyfunction;

#[pyclass]
#[derive(Clone)]
struct Point {
    x: i32,
    y: i32,
}

#[pymethods]
impl Point {
    #[new]
    fn new(x: i32, y: i32) -> Self {
        Point { x, y }
    }
}

#[pyclass]
#[derive(Clone, Copy)]
enum Direction {
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
    DownLeft = 7
}

#[pyclass]
#[derive(Clone)]
struct Shape {
    top_left: Point,
    bottom_right: Point,
}

#[pymethods]
impl Shape {
    #[new]
    fn new(top_left: Point, bottom_right: Point) -> Self {
        Shape { top_left, bottom_right }
    }
}

#[pyclass]
#[derive(Clone)]
struct DirectedPoint {
    x: i32,
    y: i32,
    direction: Direction,
}

#[pymethods]
impl DirectedPoint {
    #[new]
    fn new(x: i32, y: i32, direction: Direction) -> Self {
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


#[pyfunction]
fn route_edge(
    py: Python,
    start: Point,
    end: Point,
    start_direction: Direction,
    end_direction: Direction,
    nodes: Vec<Shape>,
    routed_edges: Vec<Vec<Point>>,
) -> PyResult<Vec<DirectedPoint>> {
    // Implement your routing logic here and return an EdgePath
    // Placeholder return value
    Ok(vec![
        DirectedPoint {
            x: 1,
            y: 0,
            direction: Direction::Center,
        },
        DirectedPoint {
            x: 1,
            y: 1,
            direction: Direction::Center,
        },
    ])
}

// A module to wrap the Python functions and structs
#[pymodule]
fn _core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_class::<Point>()?;
    m.add_class::<Shape>()?;
    m.add_class::<Direction>()?;
    m.add_class::<DirectedPoint>()?;
    m.add_function(wrap_pyfunction!(route_edge, m)?)?;
    Ok(())
}
