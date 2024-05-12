from collections.abc import Hashable
from typing import Generic, TypeVar



from netext.geometry.point import FloatPoint




class LayoutEngine(Generic[G]):
    def __call__(self, graph: G) -> dict[Hashable, FloatPoint]:
        return NotImplemented  # pragma: no cover
