# Write the benchmarking functions here.
# See "Writing benchmarks" in the asv docs for more information.

from networkx import binomial_tree
from rich.console import Console

from netext import TerminalGraph


class TimeSuite:
    """
    An example benchmark that times the performance of various kinds
    of iterating over dictionaries in Python.
    """

    def setup(self):
        self.graph = binomial_tree(4)
        self.terminal_graph = TerminalGraph(self.graph)
        self.console = Console()

    def time_render_binomial_tree_4(self):
        with self.console.capture():
            self.console.print(self.terminal_graph)
