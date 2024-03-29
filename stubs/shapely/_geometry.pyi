from ._enum import ParamEnum
from enum import IntEnum

class GeometryType(IntEnum):
    MISSING: int
    POINT: int
    LINESTRING: int
    LINEARRING: int
    POLYGON: int
    MULTIPOINT: int
    MULTILINESTRING: int
    MULTIPOLYGON: int
    GEOMETRYCOLLECTION: int

def get_type_id(geometry, **kwargs): ...
def get_dimensions(geometry, **kwargs): ...
def get_coordinate_dimension(geometry, **kwargs): ...
def get_num_coordinates(geometry, **kwargs): ...
def get_srid(geometry, **kwargs): ...
def set_srid(geometry, srid, **kwargs): ...
def get_x(point, **kwargs): ...
def get_y(point, **kwargs): ...
def get_z(point, **kwargs): ...
def get_point(geometry, index, **kwargs): ...
def get_num_points(geometry, **kwargs): ...
def get_exterior_ring(geometry, **kwargs): ...
def get_interior_ring(geometry, index, **kwargs): ...
def get_num_interior_rings(geometry, **kwargs): ...
def get_geometry(geometry, index, **kwargs): ...
def get_parts(geometry, return_index: bool = ...): ...
def get_rings(geometry, return_index: bool = ...): ...
def get_num_geometries(geometry, **kwargs): ...
def get_precision(geometry, **kwargs): ...

class SetPrecisionMode(ParamEnum):
    valid_output: int
    pointwise: int
    keep_collapsed: int

def set_precision(geometry, grid_size, mode: str = ..., **kwargs): ...
def force_2d(geometry, **kwargs): ...
def force_3d(geometry, z: float = ..., **kwargs): ...
