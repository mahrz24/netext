from _typeshed import Incomplete

def points(
    coords,
    y: Incomplete | None = ...,
    z: Incomplete | None = ...,
    indices: Incomplete | None = ...,
    out: Incomplete | None = ...,
    **kwargs
): ...
def linestrings(
    coords,
    y: Incomplete | None = ...,
    z: Incomplete | None = ...,
    indices: Incomplete | None = ...,
    out: Incomplete | None = ...,
    **kwargs
): ...
def linearrings(
    coords,
    y: Incomplete | None = ...,
    z: Incomplete | None = ...,
    indices: Incomplete | None = ...,
    out: Incomplete | None = ...,
    **kwargs
): ...
def polygons(
    geometries,
    holes: Incomplete | None = ...,
    indices: Incomplete | None = ...,
    out: Incomplete | None = ...,
    **kwargs
): ...
def box(xmin, ymin, xmax, ymax, ccw: bool = ..., **kwargs): ...
def multipoints(
    geometries, indices: Incomplete | None = ..., out: Incomplete | None = ..., **kwargs
): ...
def multilinestrings(
    geometries, indices: Incomplete | None = ..., out: Incomplete | None = ..., **kwargs
): ...
def multipolygons(
    geometries, indices: Incomplete | None = ..., out: Incomplete | None = ..., **kwargs
): ...
def geometrycollections(
    geometries, indices: Incomplete | None = ..., out: Incomplete | None = ..., **kwargs
): ...
def prepare(geometry, **kwargs) -> None: ...
def destroy_prepared(geometry, **kwargs) -> None: ...
def empty(shape, geom_type: Incomplete | None = ..., order: str = ...): ...
