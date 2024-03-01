from ._enum import ParamEnum
from .geometry.base import BaseGeometry
from _typeshed import Incomplete
from typing import Any, Iterable, Union

class BinaryPredicate(ParamEnum):
    intersects: int
    within: int
    contains: int
    overlaps: int
    crosses: int
    touches: int
    covers: int
    covered_by: int
    contains_properly: int

class STRtree:
    def __init__(self, geoms: Iterable[BaseGeometry], node_capacity: int = ...) -> None: ...
    def __len__(self) -> int: ...
    def __reduce__(self): ...
    @property
    def geometries(self): ...
    def query(
        self,
        geometry,
        predicate: Incomplete | None = ...,
        distance: Incomplete | None = ...,
    ): ...
    def nearest(self, geometry) -> Union[Any, None]: ...
    def query_nearest(
        self,
        geometry,
        max_distance: Incomplete | None = ...,
        return_distance: bool = ...,
        exclusive: bool = ...,
        all_matches: bool = ...,
    ): ...
