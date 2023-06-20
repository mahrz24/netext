from typing import Generic

from textual.events import Resize
from textual.reactive import reactive
from textual.scroll_view import ScrollView
from textual.strip import Strip

from netext import ConsoleGraph
from netext.buffer_renderer import render_buffers
from netext.console_graph import G
from rich.segment import Segment

class Graph(ScrollView, Generic[G]):
    graph: reactive[G | None] = reactive(None)

    def __init__(
        self,
        graph: G | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        **console_graph_kwargs
    ):
        self._console_graph_kwargs = console_graph_kwargs
        self._console_graph = None
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self.graph = graph
        self._strips = None
        self._timer = self.set_timer(0, self._resized)

    def on_resize(self, message: Resize):
        self.log("Graph was resized.")
        if self._timer is not None:
            self._timer.stop()
        self._timer = self.set_timer(1, self._resized)

    def _resized(self):
        if self.graph is not None and self._console_graph is None:
            self._setup_console_graph()

        if self._console_graph is not None and self.size.width != 0 and self.size.height != 0:
            self._console_graph.max_width = self.size.width
            self._console_graph.max_height = self.size.height
            self._strip_segments = self.pre_render_strips()
            self.refresh()
    def watch_graph(self, old_graph: G | None, new_graph: G | None) -> None:
        self._graph_was_updated()

    def _setup_console_graph(self):
        if self.graph is not None and self.size.width != 0 and self.size.height != 0:
            self._console_graph = ConsoleGraph(
                self.graph,
                console=self.app.console,
                max_width=self.size.width,
                max_height=self.size.height,
                **self._console_graph_kwargs
            )

    def _graph_was_updated(self):
        self._setup_console_graph()

        if self._console_graph is not None:
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
