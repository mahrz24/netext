from textual.app import App, ComposeResult
from netext.geometry.point import FloatPoint
from netext.textual.widget import GraphView

import networkx as nx
import pytest


class DummyApp(App):
    def __init__(self, *args, **kwargs):
        self._graph = kwargs.pop("graph")
        self._scroll_via_viewport = kwargs.pop("scroll_via_viewport", False)
        self.clicked = 0
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        yield GraphView(
            self._graph,
            zoom=1,
            scroll_via_viewport=self._scroll_via_viewport,
            id="graph",
        )

    def on_graph_view_element_click(self, event: GraphView.ElementClick) -> None:
        self.clicked += 1


@pytest.mark.asyncio
async def test_minimal_app():
    graph = nx.DiGraph()
    graph.add_node(1, **{"$x": 1, "$y": 1})
    graph.add_node(2, **{"$x": 10, "$y": 1})
    graph.add_edge(1, 2)

    app = DummyApp(graph=graph)
    async with app.run_test():
        assert True


@pytest.mark.asyncio
async def test_add_remove_app():
    graph = nx.DiGraph()
    graph.add_node(1, **{"$x": 1, "$y": 1})
    graph.add_node(2, **{"$x": 10, "$y": 1})
    graph.add_edge(1, 2)

    app = DummyApp(graph=graph)
    async with app.run_test() as _:
        app.query_one(GraphView).add_node(3, position=FloatPoint(10, 1))
        assert len(app.query_one(GraphView)._console_graph._core_graph.all_nodes()) == 3

        app.query_one(GraphView).remove_node(1)
        assert len(app.query_one(GraphView)._console_graph._core_graph.all_nodes()) == 2


@pytest.mark.asyncio
async def test_click_event():
    graph = nx.DiGraph()
    graph.add_node(1, **{"$x": 1, "$y": 1})
    graph.add_node(2, **{"$x": 10, "$y": 1})
    graph.add_edge(1, 2)

    app = DummyApp(graph=graph)
    async with app.run_test() as pilot:
        app.query_one(GraphView).add_node(3, position=FloatPoint(10, 1))
        assert len(app.query_one(GraphView)._console_graph._core_graph.all_nodes()) == 3
        offset = app.query_one(GraphView).graph_to_widget_coordinates(FloatPoint(10, 1))

        await pilot.click(GraphView, offset=offset)
        assert app.clicked == 1
