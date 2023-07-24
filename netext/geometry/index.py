from typing import Generic, Hashable, TypeVar, cast
from rtree.index import Index as RTreeIndex

from netext.rendering.segment_buffer import StripBuffer

T = TypeVar("T", bound=StripBuffer)
AnnotationT = TypeVar("AnnotationT")


class BufferIndex(Generic[T, AnnotationT]):
    def __init__(self) -> None:
        self._index = RTreeIndex()
        self._coordinate_map: dict[Hashable, tuple[float, float, float, float]] = {}
        self._buffer_map: dict[Hashable, T] = {}
        self._annotations: dict[Hashable, AnnotationT | None] = {}

    def insert(self, buffer: T, annotation: AnnotationT | None = None) -> None:
        if buffer.reference is None:
            raise ValueError("Cannot insert buffer without reference")
        buffer_key = hash((buffer.reference.type, buffer.reference.ref))
        self._coordinate_map[buffer_key] = buffer.bounding_box
        self._buffer_map[buffer_key] = buffer
        self._annotations[buffer_key] = annotation
        self._index.insert(
            id=buffer_key,
            coordinates=buffer.bounding_box,
        )

    def delete(self, buffer: T) -> None:
        if buffer.reference is None:
            raise ValueError("Cannot insert buffer without reference")
        buffer_key = hash((buffer.reference.type, buffer.reference.ref))
        self._index.delete(id=buffer_key, coordinates=self._coordinate_map[buffer_key])

    def intersection(self, bounding_box: tuple[float, float, float, float]) -> list[T]:
        return [
            self._buffer_map[hash]
            for hash in self._index.intersection(bounding_box, objects=True)
        ]

    def annotations_for_intersection(
        self, bounding_box: tuple[float, float, float, float]
    ) -> list[AnnotationT]:
        return cast(
            list[AnnotationT],
            [
                self._annotations[hash]
                for hash in self._index.intersection(bounding_box, objects=True)
                if self._annotations[hash] is not None
            ],
        )

    def update(self, buffer: T) -> None:
        self.delete(buffer)
        self.insert(buffer)

    def reset(self) -> None:
        self._index = RTreeIndex()
        self._coordinate_map = {}
        self._buffer_map = {}
