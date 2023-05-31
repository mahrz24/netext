import ast
import networkx as nx
from rich import print
from rich.table import Table
from rich.text import Text
from netext import ConsoleGraph
from netext.node_rasterizer import JustContent


def read_file(file_path):
    with open(file_path, "r") as file:
        content = file.read()
    return content


def traverse_ast(node, graph, parent=None):
    line = node.lineno if hasattr(node, "lineno") else -1
    node_label = type(node).__name__
    node_id = f"{node_label}_{line}"

    graph.add_node(node_id, label=node_label, line=line)
    if parent is not None:
        graph.add_edge(parent, node_id)

    for child in ast.iter_child_nodes(node):
        traverse_ast(child, graph, parent=node_id)


script_path = "examples/minimal.py"
script_content = read_file(script_path)
script_ast = ast.parse(script_content)

ast_graph = nx.DiGraph()
traverse_ast(script_ast, ast_graph)


def _render(n, d, s):
    t = Table(title=n, style="magenta")

    t.add_column("Key")
    t.add_column("Value")

    for key in ["label", "line"]:
        t.add_row(key, Text(str(d[key]), style="blue"))

    return t


nx.set_node_attributes(ast_graph, _render, "$content-renderer")
nx.set_node_attributes(ast_graph, JustContent(), "$shape")

print(ConsoleGraph(ast_graph))
