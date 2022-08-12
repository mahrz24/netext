from collections import defaultdict
from heapq import merge
from typing import Iterable, Iterator, List, Tuple

from rich.segment import Segment

from .segment_buffer import SegmentBuffer


def render_buffers(
    buffers: Iterable[SegmentBuffer], width: int, height: int
) -> Iterator[Segment]:
    buffers_by_row = defaultdict(list)
    for buffer in buffers:
        y_offsets = [segment.y_offset for segment in buffer.segment_lines]
        assert len(set(y_offsets)) == len(
            y_offsets
        ), "Duplicate segments with same y offsets in buffers are not allowed."
        buffer_y_span = list(range(0, buffer.bottom_y - buffer.top_y + 1))
        assert y_offsets == buffer_y_span, (
            "Buffer does not contain a segment for all rows or segments are not"
            " ordered."
            f" {buffer.top_y} {buffer.bottom_y} {buffer} {y_offsets} {buffer_y_span}"
        )
        buffers_by_row[buffer.top_y] = sorted(buffers_by_row[buffer.top_y] + [buffer])

    active_buffers: List[Tuple[int, List[Segment], int, SegmentBuffer]] = []
    for row in range(height):
        # This contains information where the segments for the currently
        # active buffers start (active buffer == intersects with current line)
        active_buffers = sorted(
            [
                (
                    buffer.left_x + buffer.segment_lines[buffer_row + 1].x_offset,
                    buffer.segment_lines[buffer_row + 1].segments,
                    buffer_row + 1,
                    buffer,
                )
                for _, _, buffer_row, buffer in active_buffers
                if buffer_row + 1 < buffer.height
            ]
        )

        new_active_buffers = sorted(
            [
                (
                    buffer.left_x + buffer.segment_lines[0].x_offset,
                    buffer.segment_lines[0].segments,
                    0,
                    buffer,
                )
                for buffer in buffers_by_row[row]
            ]
        )

        active_buffers = list(merge(active_buffers, new_active_buffers))

        if not active_buffers:
            yield Segment(" " * width + "\n")
            continue

        current_x = 0

        working_buffers = list(active_buffers)
        while working_buffers:
            line_left_x, segments, buffer_row, buffer = working_buffers.pop(0)
            full_segments_cell_length = sum(segment.cell_length for segment in segments)
            # The final position is allowed to be the first element outside of the
            # canvas. Otherwise it's an overflow.
            assert (
                line_left_x + full_segments_cell_length <= buffer.right_x + 1
            ), "Segment overflow."

            segment_left_x = line_left_x
            skip_remaining_segments = False
            for j, segment in enumerate(segments):
                if skip_remaining_segments:
                    break

                full_segment_cell_length = segment.cell_length
                # Empty segments should be ignored, though ideally we should not store them
                # in the buffer at all.
                if full_segment_cell_length == 0:
                    continue

                # We need to cut the segment and only print the non overlapped part if the current x coordinate
                # is already the buffer's left boundary.
                if current_x > segment_left_x:
                    segment = segment.split_cells(current_x - segment_left_x)[1]
                elif current_x < segment_left_x:
                    # Pad to the left boundary of the segment
                    yield Segment(" " * (segment_left_x - current_x))
                    current_x = segment_left_x

                # Perform a look ahead, and if the left boundary of any of the next active buffers
                # intersects with the current buffer & length (and has a smaller z-index), we split the
                # current buffer segment at that place and add the remaining part after the intersecting
                # segment.
                for i, (line_left_x_next, _, _, buffer_next) in enumerate(
                    working_buffers
                ):
                    if (
                        line_left_x_next <= segment_left_x + full_segment_cell_length
                        and buffer_next.z_index < buffer.z_index
                    ):
                        # We have to account for the case where we are already past
                        # the left of the next buffer due to already previously
                        # yielded segments (hence the max)
                        segment, overflow_segment = segment.split_cells(
                            max(0, line_left_x_next - current_x)
                        )

                        # In case we already are past the new left x we have
                        # to adjust the new buffer
                        working_buffers.insert(
                            i + 1,
                            (
                                line_left_x_next - min(0, line_left_x_next - current_x),
                                [overflow_segment] + segments[j + 1 :],
                                buffer_row,
                                buffer,
                            ),
                        )

                        # We found an overlap and inserted the working buffer again past the overlap
                        # inclduing the remaining segments
                        skip_remaining_segments = True
                        break

                # Do not render over the right boundary of the canvas
                if current_x + segment.cell_length > width:
                    segment = segment.split_cells(width - current_x)[0]

                # If the overlap from a prior segment or the overlap of an upcoming
                # segment (with lower z-index) cut the segment to disappear, nothing
                # will be yielded.
                if segment.cell_length > 0:
                    yield segment
                    current_x += segment.cell_length
                segment_left_x += full_segment_cell_length

        if current_x < width:
            yield Segment(" " * (width - current_x))
        yield Segment("\n")
