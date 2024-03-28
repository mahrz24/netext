import sys
from netext.edge_routing.edge import EdgePath
from netext.rendering.segment_buffer import Spacer, Strip
from rich.segment import Segment


def rasterize_edge_path(path: EdgePath) -> list[Strip]:
    strips = []
    # Create a map of the points y coordinates to a list of points sorted by the x coordinate
    y_to_x = {}
    min_x = sys.maxsize
    max_x = -sys.maxsize
    for point in path.points:
        if point.y not in y_to_x:
            y_to_x[point.y] = []
        y_to_x[point.y].append(point.x)
        min_x = min(min_x, point.x)
        max_x = max(max_x, point.x)
    # Sort the x coordinates
    for y in y_to_x.keys():
        y_to_x[y] = sorted(y_to_x[y])
    # Get the y bounds
    min_y = min(y_to_x.keys())
    max_y = max(y_to_x.keys())
    # Create the strips
    for y in range(min_y, max_y + 1):
        segments: list[Spacer | Segment] = []
        if y not in y_to_x:
            segments.append(Spacer(max_x - min_x + 1))
            continue
        x_coords = y_to_x[y]

        last_x = min_x - 1
        x = min_x
        for x in x_coords:
            if x - last_x > 1:
                segments.append(Spacer(x - last_x - 1))
            if x != last_x or x == min_x:
                segments.append(Segment("*"))
            last_x = x
        if x < max_x and x - last_x > 0:
            segments.append(Spacer(max_x - x - 1))
        strips.append(Strip(segments=segments))
    return strips
