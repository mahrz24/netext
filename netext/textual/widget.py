from typing import Generic

from textual.events import Resize
from textual.reactive import reactive
from textual.scroll_view import ScrollView
from textual.strip import Strip

from netext import ConsoleGraph
from netext.buffer_renderer import render_buffers
from netext.console_graph import G


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
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self.graph = graph
        self._strips = None
        self._timer = None

    def on_resize(self, message: Resize):
        self.log("Graph was resized.")
        # For now we simply update the graph as well
        if self._timer is not None:
            self._timer.stop()
        self._timer = self.set_timer(1, self._graph_was_updated)
        self._graph_was_updated()

    def watch_graph(self, old_graph: G | None, new_graph: G | None) -> None:
        self._graph_was_updated()

    def _graph_was_updated(self):
        if self.graph is not None and self.size.width != 0 and self.size.height != 0:
            self._console_graph = ConsoleGraph(
                self.graph,
                console=self.app.console,
                max_width=self.size.width,
                max_height=self.size.height,
                **self._console_graph_kwargs
            )

            all_buffers = list(self._console_graph._all_current_lod_buffers())
            self._strip_segments = render_buffers(
                all_buffers, self._console_graph._viewport_with_constraints()
            )
            self.refresh()
        else:
            self._console_graph = None
            self._strip_segments = []

    def render_line(self, y: int) -> Strip:
        scroll_x, scroll_y = self.scroll_offset  # The current scroll position
        y += scroll_y

        if y < 0 or y >= len(self._strip_segments):
            return Strip.blank(self.size.width)

        return Strip(self._strip_segments[y]).crop(scroll_x, scroll_x + self.size.width)
