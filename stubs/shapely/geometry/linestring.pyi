from _typeshed import Incomplete
from shapely.geometry.base import BaseGeometry

class LineString(BaseGeometry):
    def __new__(self, coordinates: Incomplete | None = ...): ...
    @property
    def __geo_interface__(self): ...
    def svg(
        self,
        scale_factor: float = ...,
        stroke_color: Incomplete | None = ...,
        opacity: Incomplete | None = ...,
        **kwargs
    ): ...
    @property
    def xy(self): ...
    def offset_curve(
        self, distance, quad_segs: int = ..., join_style=..., mitre_limit: float = ...
    ): ...
    def parallel_offset(
        self,
        distance,
        side: str = ...,
        resolution: int = ...,
        join_style=...,
        mitre_limit: float = ...,
    ): ...
