from textual.app import App, ComposeResult
from netext.textual.widget import GraphView

import networkx as nx
import pytest


class DummyApp(App):
    def __init__(self, *args, **kwargs):
        self._graph = kwargs.pop("graph")
        self._scroll_via_viewport = kwargs.pop("scroll_via_viewport", False)
        super().__init__(*args, **kwargs)

    def compose(self) -> ComposeResult:
        yield GraphView(
            self._graph,
            zoom=1,
            scroll_via_viewport=self._scroll_via_viewport,
            id="graph",
        )


@pytest.mark.asyncio
async def test_minimal_app():
    graph = nx.DiGraph()
    graph.add_node(1, **{"$x": 1, "$y": 1})
    graph.add_node(2, **{"$x": 10, "$y": 1})
    graph.add_edge(1, 2)

    app = DummyApp(graph=graph)
    async with app.run_test():
        assert True
