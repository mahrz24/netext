from netext.edge_routing.edge import EdgeSegment
from netext.geometry import Point
from bitarray import bitarray
from netext.geometry.line_segment import LineSegment
from netext.rendering.bitmap_buffer import BitmapBuffer


def _bresenham_line_drawing(line_segment: LineSegment, bitmap_buffer: BitmapBuffer) -> None:
    x0 = line_segment.start.x - bitmap_buffer.x
    x1 = line_segment.end.x - bitmap_buffer.x

    y0 = line_segment.start.y - bitmap_buffer.y
    y1 = line_segment.end.y - bitmap_buffer.y

    if abs(y1 - y0) < abs(x1 - x0):
        if x0 > x1:
            x1, x0 = x0, x1
            y1, y0 = y0, y1
        _bresenham_flat(x0, y0, x1, y1, bitmap_buffer)
    else:
        if y0 > y1:
            x1, x0 = x0, x1
            y1, y0 = y0, y1
        _bresenham_steep(x0, y0, x1, y1, bitmap_buffer)


def _bresenham_flat(x0: int, y0: int, x1: int, y1: int, bitmap_buffer: BitmapBuffer) -> None:
    dx = x1 - x0
    dy = y1 - y0
    yi = 1

    if dy < 0:
        yi = -1
        dy = -dy

    y = y0
    D = 2 * dy - dx

    for x in range(x0, x1 + 1):
        _put_pixel(x, y, bitmap_buffer)
        if D > 0:
            y += yi
            D = D + (2 * (dy - dx))
        else:
            D = D + 2 * dy


def _put_pixel(x: int, y: int, bitmap_buffer: BitmapBuffer) -> None:
    bitmap_buffer.buffer[x + y * bitmap_buffer.width] = True


def _bresenham_steep(x0: int, y0: int, x1: int, y1: int, bitmap_buffer: BitmapBuffer) -> None:
    dx = x1 - x0
    dy = y1 - y0
    xi = 1
    if dx < 0:
        x = x0 - x1
        xi = -1
        dx = -dx
    D = (2 * dx) - dy
    x = x0

    for y in range(y0, y1 + 1):
        _put_pixel(x, y, bitmap_buffer)
        if D > 0:
            x = x + xi
            D = D + (2 * (dx - dy))
        else:
            D = D + 2 * dx


def rasterize_edge_segments(edge_segments: list[EdgeSegment], x_scaling: int, y_scaling: int) -> BitmapBuffer:
    min_point = Point(
        x=min([min([seg.start.x, seg.end.x]) for seg in edge_segments]),
        y=min([min([seg.start.y, seg.end.y]) for seg in edge_segments]),
    )
    max_point = Point(
        x=max([max([seg.start.x, seg.end.x]) for seg in edge_segments]),
        y=max([max([seg.start.y, seg.end.y]) for seg in edge_segments]),
    )
    width = (max_point.x - min_point.x + 1) * x_scaling
    height = (max_point.y - min_point.y + 1) * y_scaling
    buffer = bitarray(width * height)
    buffer.setall(0)
    bitmap_buffer = BitmapBuffer(
        x=min_point.x * x_scaling,
        y=min_point.y * y_scaling,
        width=width,
        height=height,
        buffer=buffer,
    )

    for edge_segment in edge_segments:
        scaled_segment = EdgeSegment(
            start=Point(edge_segment.start.x * x_scaling, edge_segment.start.y * y_scaling),
            end=Point(edge_segment.end.x * x_scaling, edge_segment.end.y * y_scaling),
        )
        _bresenham_line_drawing(scaled_segment, bitmap_buffer=bitmap_buffer)

    return bitmap_buffer
