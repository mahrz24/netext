from _typeshed import Incomplete
from typing import Any
from shapely.geometry.base import BaseGeometry

class Point(BaseGeometry):
    def __new__(self, *args: Any) -> Point: ...
    @property
    def x(self): ...
    @property
    def y(self): ...
    @property
    def z(self): ...
    @property
    def __geo_interface__(self): ...
    def svg(
        self,
        scale_factor: float = ...,
        fill_color: Incomplete | None = ...,
        opacity: Incomplete | None = ...,
        **kwargs
    ): ...
    @property
    def xy(self): ...