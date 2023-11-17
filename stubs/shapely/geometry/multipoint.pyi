from _typeshed import Incomplete
from shapely.geometry.base import BaseMultipartGeometry

class MultiPoint(BaseMultipartGeometry):
    def __new__(self, points: Incomplete | None = ...): ...
    @property
    def __geo_interface__(self): ...
    def svg(
        self,
        scale_factor: float = ...,
        color: Incomplete | None = ...,
        opacity: Incomplete | None = ...,
        **kwargs,
    ): ...
