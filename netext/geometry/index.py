from typing import Hashable
from rtree.index import Index as RTreeIndex

from netext.rendering.segment_buffer import StripBuffer

class BufferIndex:
    def __init__(self) -> None:
        self._index = RTreeIndex()
        self._coordinate_map: dict[Hashable, tuple[float, float, float, float]] = {}
        self._buffer_map: dict[Hashable, StripBuffer] = {}

    def insert(self, buffer: StripBuffer) -> None:
        if buffer.reference is None:
            raise ValueError("Cannot insert buffer without reference")
        buffer_key = (buffer.reference.type, buffer.reference.ref)
        self._coordinate_map[buffer_key] = buffer.bounding_box
        self._buffer_map[buffer_key] = buffer
        self._index.insert(
            id=hash(buffer_key),
            coordinates=buffer.bounding_box,
        )

    def delete(self, buffer: StripBuffer) -> None:
        if buffer.reference is None:
            raise ValueError("Cannot insert buffer without reference")
        buffer_key = (buffer.reference.type, buffer.reference.ref)
        self._index.delete(id=hash(buffer_key), coordinates=self._coordinate_map[buffer_key])

    def update(self, buffer: StripBuffer) -> None:
        self.delete(buffer_id)
        self.insert(buffer_id, buffer)
