from _typeshed import Incomplete
from shapely.geometry.base import BaseMultipartGeometry

class GeometryCollection(BaseMultipartGeometry):
    def __new__(self, geoms: Incomplete | None = ...): ...
    @property
    def __geo_interface__(self): ...
