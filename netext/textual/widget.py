from typing import Generic, Protocol, TypeGuard, cast

from textual.events import Resize
from textual.reactive import reactive
from textual.scroll_view import ScrollView, Size
from textual.strip import Strip

from netext import ConsoleGraph
from netext.buffer_renderer import render_buffers
from netext.console_graph import G, AutoZoom, ZoomSpec
from rich.segment import Segment


class SetupGraph(Protocol[G]):
    _console_graph: ConsoleGraph[G]
    _strip_segments: list[Strip]
    size: Size

    def _graph_was_updated(self) -> None:
        ...

    def refresh(self) -> None:
        ...

    def pre_render_strips(self) -> list[Strip]:
        ...


def _setup_console_graph(graph: "Graph[G]") -> TypeGuard[SetupGraph[G]]:
    if (
        graph.graph is not None
        and graph._console_graph is None
        and graph.size.width != 0
        and graph.size.height != 0
    ):
        graph._console_graph = ConsoleGraph(
            graph.graph,
            console=graph.app.console,
            max_width=graph.size.width,
            max_height=graph.size.height,
            **graph._console_graph_kwargs
        )
    return graph._console_graph is not None

class Graph(ScrollView, Generic[G]):
    graph: reactive[G | None] = reactive(cast(G | None, None))
    zoom: reactive[float | tuple[float, float] | ZoomSpec | AutoZoom] = reactive(
        cast(float | tuple[float, float] | ZoomSpec | AutoZoom, 1.0)
    )

    def __init__(
        self,
        graph: G | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        zoom: float | tuple[float, float] | ZoomSpec | AutoZoom = 1.0,
        **console_graph_kwargs
    ):
        self._console_graph_kwargs = console_graph_kwargs
        self._console_graph: ConsoleGraph[G] | None = None
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self.graph = graph
        self._strip_segments: list[Strip] = list()
        self._timer = self.set_timer(0, self._resized)
        self.zoom = zoom

    def on_resize(self, message: Resize):
        self.log("Graph was resized.")
        if self._timer is not None:
            self._timer.stop()
        self._timer = self.set_timer(0.1, self._resized)

    def _resized(self):
        if _setup_console_graph(self):
            self._console_graph.max_width = self.size.width
            self._console_graph.max_height = self.size.height
            self._strip_segments = self.pre_render_strips()
            self.refresh()

    def watch_graph(self, old_graph: G | None, new_graph: G | None) -> None:
        self._graph_was_updated()

    def watch_zoom(
        self,
        old_zoom: float | tuple[float, float] | ZoomSpec | AutoZoom,
        new_zoom: float | tuple[float, float] | ZoomSpec | AutoZoom,
    ) -> None:
        if _setup_console_graph(self):
            self._console_graph._zoom = new_zoom
            self._graph_was_updated()

    def _graph_was_updated(self):
        if _setup_console_graph(self):
            self._strip_segments = self.pre_render_strips()
            self.refresh()
        else:
            self._console_graph = None
            self._strip_segments = []

    def pre_render_strips(self) -> list[list[Segment]]:
        if self._console_graph is not None:
            all_buffers = list(self._console_graph._all_current_lod_buffers())
            return render_buffers(
                all_buffers, self._console_graph._viewport_with_constraints()
            )
        else:
            return []

    def render_line(self, y: int) -> Strip:
        scroll_x, scroll_y = self.scroll_offset  # The current scroll position
        y += scroll_y

        if y < 0 or y >= len(self._strip_segments):
            return Strip.blank(self.size.width)

        return Strip(self._strip_segments[y]).crop(scroll_x, scroll_x + self.size.width)
