from ._ragged_array import (
    from_ragged_array as from_ragged_array,
    to_ragged_array as to_ragged_array,
)
from _typeshed import Incomplete

def to_wkt(
    geometry,
    rounding_precision: int = ...,
    trim: bool = ...,
    output_dimension: int = ...,
    old_3d: bool = ...,
    **kwargs,
): ...
def to_wkb(
    geometry,
    hex: bool = ...,
    output_dimension: int = ...,
    byte_order: int = ...,
    include_srid: bool = ...,
    flavor: str = ...,
    **kwargs,
): ...
def to_geojson(geometry, indent: Incomplete | None = ..., **kwargs): ...
def from_wkt(geometry, on_invalid: str = ..., **kwargs): ...
def from_wkb(geometry, on_invalid: str = ..., **kwargs): ...
def from_geojson(geometry, on_invalid: str = ..., **kwargs): ...
