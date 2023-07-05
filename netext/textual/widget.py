from typing import Generic, Protocol, Self, TypeGuard, cast

from textual.events import Resize
from textual.reactive import reactive
from textual.scroll_view import ScrollView
from textual.geometry import Region, Size
from textual.strip import Strip

from netext import ConsoleGraph
from netext.buffer_renderer import render_buffers
from netext.console_graph import G, AutoZoom, ZoomSpec
from rich.segment import Segment
from netext.geometry.region import Region as NetextRegion


class InitializedGraphView(Protocol[G]):
    _console_graph: ConsoleGraph[G]
    _strip_segments: list[list[Segment]]
    _scroll_via_viewport: bool

    size: Size
    virtual_size: Size

    def _graph_was_updated(self) -> None:
        ...

    def refresh(self) -> None:
        ...

    def pre_render_strips(self) -> list[list[Segment]]:
        ...


def _setup_console_graph(graph: "GraphView[G]") -> TypeGuard[InitializedGraphView[G]]:
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
            zoom=graph.zoom,
            **graph._console_graph_kwargs,
        )
    return graph._console_graph is not None


class GraphView(ScrollView, Generic[G]):
    graph: reactive[G | None] = reactive(cast(G | None, None))
    zoom: reactive[float | tuple[float, float] | ZoomSpec | AutoZoom] = reactive(
        cast(float | tuple[float, float] | ZoomSpec | AutoZoom, 1.0)
    )
    viewport: reactive[Region | None] = reactive(cast(Region | None, None))

    def __init__(
        self,
        graph: G | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        zoom: float | tuple[float, float] | ZoomSpec | AutoZoom = 1.0,
        viewport: Region | None = None,
        scroll_via_viewport: bool = False,
        **console_graph_kwargs,
    ):
        self._console_graph_kwargs = console_graph_kwargs
        self._console_graph: ConsoleGraph[G] | None = None
        self._scroll_via_viewport = scroll_via_viewport
        if scroll_via_viewport and viewport is not None:
            raise ValueError(
                "Cannot specify both viewport and scroll_via_viewport=True"
            )
        super().__init__(name=name, id=id, classes=classes, disabled=disabled)
        self.graph = graph
        self._strip_segments: list[list[Segment]] = list()
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
        new_zoom: float | tuple[float, float] | ZoomSpec | AutoZoom,
    ) -> None:
        if _setup_console_graph(self):
            self._console_graph.zoom = new_zoom
            self._graph_was_updated()

    def watch_viewport(
        self,
        new_viewport: Region | None,
    ) -> None:
        if _setup_console_graph(self):
            if new_viewport is None:
                self._console_graph.viewport = None
            else:
                if self._scroll_via_viewport:
                    raise ValueError(
                        "Cannot specify both viewport and scroll_via_viewport=True"
                    )

                base_viewport = self._console_graph.full_viewport
                self._console_graph.viewport = NetextRegion(
                    x=base_viewport.x + new_viewport.x,
                    y=base_viewport.y + new_viewport.y,
                    width=new_viewport.width,
                    height=new_viewport.height,
                )
            self._graph_was_updated()

    def _graph_was_updated(self):
        if _setup_console_graph(self):
            self._strip_segments = self.pre_render_strips()
            self.refresh()
        else:
            self._console_graph = None
            self._strip_segments = []

    def refresh(
        self, *regions: Region, repaint: bool = True, layout: bool = False
    ) -> Self:
        if self._console_graph is not None:
            if not self._scroll_via_viewport:
                self.virtual_size = Size(
                    *self._console_graph._viewport_with_constraints().size.as_tuple()
                )
        return super().refresh(*regions, repaint=repaint, layout=layout)

    def pre_render_strips(self) -> list[list[Segment]]:
        if self._console_graph is not None:
            if self._scroll_via_viewport:
                self.virtual_size = Size(
                    *self._console_graph.full_viewport.size.as_tuple()
                )

            all_buffers = list(self._console_graph._all_current_lod_buffers())
            strips = render_buffers(
                all_buffers, self._console_graph._viewport_with_constraints()
            )
            return strips
        else:
            return []

    def watch_scroll_x(self, old_value: float, new_value: float) -> None:
        if self.show_horizontal_scrollbar and round(old_value) != round(new_value):
            self.horizontal_scrollbar.position = round(new_value)
        self._update_scroll_viewport()
        self.refresh()

    def watch_scroll_y(self, old_value: float, new_value: float) -> None:
        if self.show_vertical_scrollbar and round(old_value) != round(new_value):
            self.vertical_scrollbar.position = round(new_value)
        self._update_scroll_viewport()
        self.refresh()

    def _update_scroll_viewport(self) -> None:
        if self._console_graph is not None:
            scroll_x, scroll_y = self.scroll_offset
            base_viewport = self._console_graph.full_viewport
            self._console_graph.viewport = NetextRegion(
                x=base_viewport.x + scroll_x,
                y=base_viewport.y + scroll_y,
                width=self.size.width,
                height=self.size.height,
            )
            self._strip_segments = self.pre_render_strips()

    def render_line(self, y: int) -> Strip:
        scroll_x, scroll_y = self.scroll_offset  # The current scroll position

        if self._scroll_via_viewport:
            scroll_x, scroll_y = 0, 0

        y += scroll_y

        if y < 0 or y >= len(self._strip_segments):
            return Strip.blank(self.size.width)

        return Strip(self._strip_segments[y]).crop(scroll_x, scroll_x + self.size.width)
