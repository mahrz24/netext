"""Pytest configuration for snapshot tests.

This borrows mostly from https://github.com/Textualize/textual/blob/main/tests/snapshot_tests/conftest.py
"""

from __future__ import annotations

import difflib
import importlib
import os
from dataclasses import dataclass
from datetime import datetime
from operator import attrgetter
from os import PathLike
from pathlib import Path, PurePath
import sys
import types
from typing import Union, List, Optional, Callable

import pytest
from _pytest.config import ExitCode
from _pytest.fixtures import FixtureRequest
from _pytest.main import Session
from _pytest.terminal import TerminalReporter
from jinja2 import Template
from rich.console import Console
from syrupy import SnapshotAssertion


from netext import ConsoleGraph

NETEXT_SNAPSHOT_SVG_KEY = pytest.StashKey[str]()
NETEXT_ACTUAL_SVG_KEY = pytest.StashKey[str]()
NETEXT_SNAPSHOT_PASS = pytest.StashKey[bool]()
NETEXT_GRAPH_KEY = pytest.StashKey[ConsoleGraph]()


def import_graph(path: str) -> ConsoleGraph:
    """Import a graph from a path.

    This function does some magic to import a graph from a path, and then
    returns it. In case the graph is printed by the script, it will be
    intercepted and returned.
    """
    sys.path.append(os.path.dirname(path))
    script_name = os.path.basename(path).replace(".py", "")

    spec = importlib.util.find_spec(script_name)
    source_code = spec.loader.get_source(script_name)

    # Replace the original function with the new one
    source_code = source_code.replace("console.print(", "_print_intercept(").replace("print(", "_print_intercept(")

    module = types.ModuleType(script_name)

    func = """
def _print_intercept(*args, **kwargs):
    import sys
    sys.modules[__name__].graph = args[0]
"""

    # Add the modified module to sys.modules
    sys.modules[script_name] = module

    exec(func + source_code, module.__dict__)

    return module.graph


@pytest.fixture
def snap_compare(snapshot: SnapshotAssertion, request: FixtureRequest) -> Callable[[str | PurePath], bool]:
    """
    This fixture returns a function which can be used to compare the output of a Textual
    app with the output of the same app in the past. This is snapshot testing, and it
    used to catch regressions in output.
    """

    def compare(
        graph_path: str | PurePath,
        terminal_size: tuple[int, int] = (80, 24),
    ) -> bool:
        """
        Compare a current screenshot of the app running at app_path, with
        a previously accepted (validated by human) snapshot stored on disk.
        When the `--snapshot-update` flag is supplied (provided by syrupy),
        the snapshot on disk will be updated to match the current screenshot.

        Args:
            app_path (str): The path of the app. Relative paths are relative to the location of the
                test this function is called from.
            terminal_size (tuple[int, int]): A pair of integers (WIDTH, HEIGHT), representing terminal size.

        Returns:
            Whether the screenshot matches the snapshot.
        """
        node = request.node
        path = Path(graph_path)
        if path.is_absolute():
            # If the user supplies an absolute path, just use it directly.
            graph = import_graph(str(path.resolve()))
        else:
            # If a relative path is supplied by the user, it's relative to the location of the pytest node,
            # NOT the location that `pytest` was invoked from.
            node_path = node.path.parent
            resolved = (node_path / graph_path).resolve()
            graph = import_graph(str(resolved))

        console = Console(width=terminal_size[0], height=terminal_size[1], record=True)
        console.print(graph)
        actual_screenshot = console.export_svg()

        result = snapshot == actual_screenshot

        if result is False:
            # The split and join below is a mad hack, sorry...
            node.stash[NETEXT_SNAPSHOT_SVG_KEY] = "\n".join(str(snapshot).splitlines()[1:-1])
            node.stash[NETEXT_ACTUAL_SVG_KEY] = actual_screenshot
            node.stash[NETEXT_GRAPH_KEY] = graph
        else:
            node.stash[NETEXT_SNAPSHOT_PASS] = True

        return result

    return compare


@dataclass
class SvgSnapshotDiff:
    """Model representing a diff between current screenshot of an app,
    and the snapshot on disk. This is ultimately intended to be used in
    a Jinja2 template."""

    snapshot: Optional[str]
    actual: Optional[str]
    test_name: str
    file_similarity: float
    path: PathLike
    line_number: int
    graph: ConsoleGraph
    environment: dict


def pytest_sessionfinish(
    session: Session,
    exitstatus: Union[int, ExitCode],
) -> None:
    """Called after whole test run finished, right before returning the exit status to the system.
    Generates the snapshot report and writes it to disk.
    """
    diffs: List[SvgSnapshotDiff] = []
    num_snapshots_passing = 0
    for item in session.items:
        # Grab the data our fixture attached to the pytest node
        num_snapshots_passing += int(item.stash.get(NETEXT_SNAPSHOT_PASS, False))
        snapshot_svg = item.stash.get(NETEXT_SNAPSHOT_SVG_KEY, None)
        actual_svg = item.stash.get(NETEXT_ACTUAL_SVG_KEY, None)
        graph = item.stash.get(NETEXT_GRAPH_KEY, None)

        if graph:
            path, line_index, name = item.reportinfo()
            similarity = 100 * difflib.SequenceMatcher(a=str(snapshot_svg), b=str(actual_svg)).ratio()
            diffs.append(
                SvgSnapshotDiff(
                    snapshot=str(snapshot_svg),
                    actual=str(actual_svg),
                    file_similarity=similarity,
                    test_name=name,
                    path=path,
                    line_number=line_index + 1,
                    graph=graph,
                    environment=dict(os.environ),
                )
            )

    if diffs:
        diff_sort_key = attrgetter("file_similarity")
        diffs = sorted(diffs, key=diff_sort_key)

        conftest_path = Path(__file__)
        snapshot_template_path = conftest_path.parent / "snapshot_report_template.jinja2"
        snapshot_report_path_dir = conftest_path.parent / "output"
        snapshot_report_path_dir.mkdir(parents=True, exist_ok=True)
        snapshot_report_path = snapshot_report_path_dir / "snapshot_report.html"

        template = Template(snapshot_template_path.read_text())

        num_fails = len(diffs)
        num_snapshot_tests = len(diffs) + num_snapshots_passing

        rendered_report = template.render(
            diffs=diffs,
            passes=num_snapshots_passing,
            fails=num_fails,
            pass_percentage=100 * (num_snapshots_passing / max(num_snapshot_tests, 1)),
            fail_percentage=100 * (num_fails / max(num_snapshot_tests, 1)),
            num_snapshot_tests=num_snapshot_tests,
            now=datetime.utcnow(),
        )
        with open(snapshot_report_path, "w+", encoding="utf-8") as snapshot_file:
            snapshot_file.write(rendered_report)

        session.config._netext_snapshots = diffs
        session.config._netext_snapshot_html_report = snapshot_report_path


def pytest_terminal_summary(
    terminalreporter: TerminalReporter,
    exitstatus: ExitCode,
    config: pytest.Config,
) -> None:
    """Add a section to terminal summary reporting.
    Displays the link to the snapshot report that was generated in a prior hook.
    """
    diffs = getattr(config, "_netext_snapshots", None)
    console = Console(legacy_windows=False, force_terminal=True)
    if diffs:
        snapshot_report_location = config._netext_snapshot_html_report
        console.print("[b red]Netext Snapshot Report", style="red")
        console.print(
            f"\n[black on red]{len(diffs)} mismatched snapshots[/]\n\n[b]View the"
            f" [link=file://{snapshot_report_location}]failure report[/].\n"
        )
        console.print(f"[dim]{snapshot_report_location}\n")
