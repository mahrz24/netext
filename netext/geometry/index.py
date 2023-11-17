from typing import Generic, Hashable, TypeVar, cast
from rtree.index import Index as RTreeIndex

from netext.rendering.segment_buffer import StripBuffer

T = TypeVar("T", bound=StripBuffer)
AnnotationT = TypeVar("AnnotationT", bound=Hashable)


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
        # We do not store the buffer itself in the index, because the index
        # wants to pickle objects, which we do not need here.
        self._index.insert(
            id=buffer_key,
            coordinates=buffer.bounding_box,
        )

    def delete(self, buffer: T) -> None:
        if buffer.reference is None:
            raise ValueError("Cannot insert buffer without reference")
        buffer_key = hash((buffer.reference.type, buffer.reference.ref))
        self._index.delete(id=buffer_key, coordinates=self._coordinate_map[buffer_key])
        del self._buffer_map[buffer_key]
        del self._coordinate_map[buffer_key]
        del self._annotations[buffer_key]

    def intersection(self, bounding_box: tuple[float, float, float, float], restrict: list[T]) -> list[T]:
        restrict_refs = [buffer.reference for buffer in restrict]
        return [
            self._buffer_map[item.id]
            for item in self._index.intersection(bounding_box, objects=True)
            if self._buffer_map[item.id].reference in restrict_refs
        ]

    def annotations_for_intersection(
        self,
        bounding_box: tuple[float, float, float, float],
        restrict: list[AnnotationT],
    ) -> list[AnnotationT]:
        restrict_hashes = [hash(annotation) for annotation in restrict]
        return cast(
            list[AnnotationT],
            [
                self._annotations[item.id]
                for item in self._index.intersection(bounding_box, objects=True)
                if self._annotations.get(item.id) is not None and hash(self._annotations[item.id]) in restrict_hashes
            ],
        )

    def update(self, buffer: T, annotation: AnnotationT | None = None) -> None:
        self.delete(buffer)
        self.insert(buffer, annotation)

    def reset(self) -> None:
        self._index = RTreeIndex()
        self._coordinate_map = {}
        self._buffer_map = {}
