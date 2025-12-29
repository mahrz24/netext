use crate::geometry::Point;

use super::grid::RawPoint;

#[derive(Clone, Hash)]
pub(crate) struct RawArea {
    pub top_left: Point,
    pub bottom_right: Point,
}

impl RawArea {
    pub fn width(&self) -> i32 {
        self.bottom_right.x - self.top_left.x + 1
    }

    pub fn height(&self) -> i32 {
        self.bottom_right.y - self.top_left.y + 1
    }

    pub fn size(&self) -> usize {
        (self.width() * self.height()) as usize
    }

    pub fn num_segments(&self) -> usize {
        ((self.width() - 1) * self.height() + (self.height() - 1) * self.width()) as usize
    }

    pub fn point_to_raw_point(&self, point: &Point) -> Option<RawPoint> {
        if point.x < self.top_left.x
            || point.x > self.bottom_right.x
            || point.y < self.top_left.y
            || point.y > self.bottom_right.y
        {
            return None;
        }
        Some(RawPoint(
            ((point.x - self.top_left.x) + (point.y - self.top_left.y) * (self.width())) as u32,
        ))
    }

    pub fn raw_index_to_point(&self, raw_index: usize) -> Point {
        let width = self.width() as usize;
        let x = raw_index % width;
        let y = raw_index / width;
        Point {
            x: self.top_left.x + x as i32,
            y: self.top_left.y + y as i32,
        }
    }

    pub fn segment_index_between(&self, from: &Point, to: &Point) -> Option<usize> {
        let dx = to.x - from.x;
        let dy = to.y - from.y;

        // Grid coordinates relative to top-left.
        let grid_from_x = from.x - self.top_left.x;
        let grid_from_y = from.y - self.top_left.y;

        if dx == 1 && dy == 0 {
            // Right
            Some((grid_from_y * (self.width() - 1) + grid_from_x) as usize)
        } else if dx == -1 && dy == 0 {
            // Left
            Some((grid_from_y * (self.width() - 1) + (grid_from_x - 1)) as usize)
        } else if dx == 0 && dy == 1 {
            // Down
            Some(
                ((self.width() - 1) * self.height()
                    + grid_from_x * (self.height() - 1)
                    + grid_from_y) as usize,
            )
        } else if dx == 0 && dy == -1 {
            // Up
            Some(
                ((self.width() - 1) * self.height()
                    + grid_from_x * (self.height() - 1)
                    + (grid_from_y - 1)) as usize,
            )
        } else {
            None
        }
    }

    pub fn edge_prefix_sums<T>(&self, edge_buffer: &Vec<T>, prefix_x: &mut Vec<T>, prefix_y: &mut Vec<T>)
    where
        T: Copy + Default + std::ops::AddAssign,
    {
        let width = self.width() as usize;
        let height = self.height() as usize;

        assert!(prefix_x.len() == (width * height) as usize);
        assert!(prefix_y.len() == (width * height) as usize);

        // Fill horizontal prefix sums
        for y in 0..height {
            let mut sum: T = T::default();
            prefix_x[y * width] = sum;
            for x in 0..(width - 1) {
                let edge_index = (y * (width - 1) + x) as usize;
                let prefix_index = y * width + x + 1;
                sum += edge_buffer[edge_index];
                prefix_x[prefix_index] = sum;
            }
        }

        // Fill vertical prefix sums
        for x in 0..width {
            let mut sum: T = T::default();
            prefix_y[x] = sum;
            for y in 0..(height - 1) {
                let edge_index = ((width - 1) * height + x * (height - 1) + y) as usize;
                let prefix_index = (y + 1) * width + x;
                sum += edge_buffer[edge_index];
                prefix_y[prefix_index] = sum;
            }
        }
    }
}
