from typing import Generic

from textual.events import Resize
from textual.geometry import Size
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

    def on_resize(self, message: Resize):
        self.log("Graph was resized.")
        # For now we simply update the graph as well
        self._graph_was_updated()

    def watch_graph(self, old_graph: G | None, new_graph: G | None) -> None:
        self._graph_was_updated()

    def _graph_was_updated(self):
        if self.graph is not None:
            self.log("Console graph updated.")
            self._console_graph = ConsoleGraph(
                self.graph, console=self.app.console, **self._console_graph_kwargs
            )

            # TODO this needs to be cleaned up, better state management of the console graph
            # Also there is some itneraction between the sizes
            zoom_x, zoom_y = self._console_graph._project_positions(
                self.size.width, self.size.height
            )

            zoom = min([zoom_x, zoom_y])

            viewport = self._console_graph.viewport
            self.virtual_size = Size(viewport.width, viewport.height)

            all_buffers = self._console_graph._all_buffers(
                console=self._console_graph.console, zoom=zoom
            )

            self._console_graph._render_edges(self._console_graph.console, zoom=zoom)

            all_buffers = self._console_graph._all_buffers(
                console=self._console_graph.console, zoom=zoom
            )

            # In case the graph changes we want to render it fully (at least the full viewport that
            # was specified.
            self._strip_segments = render_buffers(
                all_buffers, self._console_graph._viewport_with_constraints()
            )
        else:
            self._console_graph = None
            self._strip_segments = []

    def render_line(self, y: int) -> Strip:
        scroll_x, scroll_y = self.scroll_offset  # The current scroll position
        y += scroll_y

        if y < 0 or y >= len(self._strip_segments):
            return Strip.blank(self.size.width)

        return Strip(self._strip_segments[y]).crop(scroll_x, scroll_x + self.size.width)
