import pytest
from networkx import binomial_tree
from rich.console import Console

from netext import TerminalGraph


@pytest.fixture
def console():
    return Console()


def test_render_binomial_tree(console):
    graph = binomial_tree(4)
    terminal_graph = TerminalGraph(graph)

    with console.capture():
        console.print(terminal_graph)
