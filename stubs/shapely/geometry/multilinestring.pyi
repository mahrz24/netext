from _typeshed import Incomplete
from shapely.geometry.base import BaseMultipartGeometry

class MultiLineString(BaseMultipartGeometry):
    def __new__(self, lines: Incomplete | None = ...): ...
    @property
    def __geo_interface__(self): ...
    def svg(
        self,
        scale_factor: float = ...,
        color: Incomplete | None = ...,
        opacity: Incomplete | None = ...,
        **kwargs,
    ): ...
