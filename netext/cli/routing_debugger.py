from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rich.text import Text

# Textual imports; keep simple to match installed version.
from textual.app import App, ComposeResult  # type: ignore
from textual.containers import Container, Horizontal, Vertical  # type: ignore
from textual.widgets import Footer, Static  # type: ignore


Palette = [
    "#102040",
    "#1d4ed8",
    "#2563eb",
    "#3b82f6",
    "#60a5fa",
    "#93c5fd",
    "#bfdbfe",
]

# Heatmap scale shared across H/V segments and corners.
HEAT_COLORS = [
    "#22c55e",  # 1 -> green
    "#b45309",  # 2 -> brown
    "#d97706",  # 3 -> orange-brown
    "#f97316",  # 4 -> orange
    "#dc2626",  # 5+ -> red
]


@dataclass
class TraceLayout:
    top_left: tuple[int, int]
    width: int
    height: int
    nodes: list[dict[str, Any]]
    grid_points: list[dict[str, Any]]


@dataclass
class TraceIteration:
    routed_edges: list[dict[str, Any]]
    all_paths: list[dict[str, Any]]
    ripped_up_next: list[dict[str, Any]]
    raw_usage: list[int]
    raw_corner_usage: list[int]
    overflow: dict[str, Any]


class Cell:
    __slots__ = ("char", "fg", "bg")

    def __init__(self) -> None:
        self.char = " "
        self.fg: str | None = None
        self.bg: str | None = None

    def set(self, char: str | None = None, fg: str | None = None, bg: str | None = None) -> None:
        if char is not None:
            self.char = char
        if fg is not None:
            self.fg = fg
        if bg is not None:
            self.bg = bg

    def to_markup(self) -> str:
        parts = []
        if self.fg:
            parts.append(self.fg)
        if self.bg:
            parts.append(f"on {self.bg}")
        if parts:
            return f"[{' '.join(parts)}]{self.char}[/]"
        return self.char


def load_trace(path: Path) -> tuple[TraceLayout, list[TraceIteration]]:
    data = json.loads(path.read_text())
    layout = data.get("layout", {})
    raw_area = layout.get(
        "raw_area", {"top_left": {"x": 0, "y": 0}, "width": 0, "height": 0, "bottom_right": {"x": 0, "y": 0}}
    )
    trace_layout = TraceLayout(
        top_left=(raw_area.get("top_left", {}).get("x", 0), raw_area.get("top_left", {}).get("y", 0)),
        width=int(raw_area.get("width", 0)),
        height=int(raw_area.get("height", 0)),
        nodes=layout.get("nodes", []),
        grid_points=layout.get("grid_points", []),
    )
    iterations: list[TraceIteration] = []
    for entry in data.get("iterations", []):
        iterations.append(
            TraceIteration(
                routed_edges=entry.get("routed_edges", []),
                all_paths=entry.get("all_paths", []),
                ripped_up_next=entry.get("ripped_up_next", []),
                raw_usage=entry.get("raw_usage", []),
                raw_corner_usage=entry.get("raw_corner_usage", []),
                overflow=entry.get("overflow", {}),
            )
        )
    return trace_layout, iterations


def gradient(value: int, max_value: int) -> str | None:
    # Deprecated: keep for compatibility if called elsewhere.
    return None


def usage_color(usage: int) -> str | None:
    if usage <= 0:
        return None
    idx = min(len(HEAT_COLORS) - 1, usage - 1)
    return HEAT_COLORS[idx]


def direction(a: tuple[int, int], b: tuple[int, int]) -> tuple[int, int]:
    return (b[0] - a[0], b[1] - a[1])


def char_for_dirs(prev_dir: tuple[int, int] | None, next_dir: tuple[int, int] | None) -> str:
    if prev_dir == next_dir:
        if prev_dir in ((1, 0), (-1, 0)):
            return "─"
        if prev_dir in ((0, 1), (0, -1)):
            return "│"
    dirs = {prev_dir, next_dir}
    # y increases downward; map explicit corner glyphs based on incident directions
    if (1, 0) in dirs and (0, 1) in dirs:  # from left and up/down -> connect left + down
        return "┐"
    if (-1, 0) in dirs and (0, 1) in dirs:  # from right and up/down -> connect right + down
        return "┌"
    if (1, 0) in dirs and (0, -1) in dirs:  # from left and down/up -> connect left + up
        return "┘"
    if (-1, 0) in dirs and (0, -1) in dirs:  # from right and down/up -> connect right + up
        return "└"
    if (1, 0) in dirs or (-1, 0) in dirs:
        return "─"
    if (0, 1) in dirs or (0, -1) in dirs:
        return "│"
    return "·"


EDGE_DISPLAY_MODES = ["edges", "edges_endpoints", "endpoints", "none"]


class RoutingTraceApp(App):
    CSS = """
Screen {
        align: center middle;
    }
    #info {
        height: 1;
    }
    #canvas {
        height: 1fr;
        width: 1fr;
        overflow: auto;
    }
    #canvas-content {
        width: auto;
    }
    #sidebar {
        width: 36;
        border: heavy $accent;
        padding: 1 1;
        height: 1fr;
    }
    """
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("n", "next_iteration", "Next"),
        ("p", "prev_iteration", "Prev"),
        ("r", "toggle_ripups", "Toggle rip-ups"),
        ("h", "toggle_heatmap_horizontal", "Toggle H heatmap"),
        ("v", "toggle_heatmap_vertical", "Toggle V heatmap"),
        ("c", "toggle_heatmap_corners", "Toggle corner heatmap"),
        ("j", "next_edge", "Next edge"),
        ("k", "prev_edge", "Prev edge"),
        ("u", "toggle_nodes", "Toggle nodes"),
        ("e", "toggle_edges", "Toggle edges"),
    ]

    def __init__(self, trace_path: Path):
        super().__init__()
        self.trace_path = trace_path
        self.layout: TraceLayout
        self.iterations: list[TraceIteration]
        self.iter_index = 0
        self.show_ripups = True
        self.show_heat_h = True
        self.show_heat_v = True
        self.show_heat_corners = False
        self.selected_edge_index = 0
        self.show_nodes = True
        self.edge_display_mode = "edges"

    def compose(self) -> ComposeResult:
        self.layout, self.iterations = load_trace(self.trace_path)
        yield Vertical(
            Static(id="info"),
            Horizontal(
                Container(Static(id="canvas-content"), id="canvas"),
                Static(id="sidebar"),
            ),
            Footer(),
        )

    def on_mount(self) -> None:
        self.refresh_view()

    def action_next_iteration(self) -> None:
        if self.iter_index < len(self.iterations) - 1:
            self.iter_index += 1
            self.selected_edge_index = 0
            self.refresh_view()

    def action_prev_iteration(self) -> None:
        if self.iter_index > 0:
            self.iter_index -= 1
            self.selected_edge_index = 0
            self.refresh_view()

    def action_toggle_ripups(self) -> None:
        self.show_ripups = not self.show_ripups
        self.refresh_view()

    def action_toggle_heatmap_horizontal(self) -> None:
        self.show_heat_h = not self.show_heat_h
        self.refresh_view()

    def action_toggle_heatmap_vertical(self) -> None:
        self.show_heat_v = not self.show_heat_v
        self.refresh_view()

    def action_toggle_heatmap_corners(self) -> None:
        self.show_heat_corners = not self.show_heat_corners
        self.refresh_view()

    def action_toggle_nodes(self) -> None:
        self.show_nodes = not self.show_nodes
        self.refresh_view()

    def action_toggle_edges(self) -> None:
        idx = EDGE_DISPLAY_MODES.index(self.edge_display_mode)
        self.edge_display_mode = EDGE_DISPLAY_MODES[(idx + 1) % len(EDGE_DISPLAY_MODES)]
        self.refresh_view()

    def action_next_edge(self) -> None:
        paths = self.iterations[self.iter_index].all_paths
        if not paths:
            return
        self.selected_edge_index = min(self.selected_edge_index + 1, len(paths) - 1)
        self.refresh_view()

    def action_prev_edge(self) -> None:
        paths = self.iterations[self.iter_index].all_paths
        if not paths:
            return
        self.selected_edge_index = max(self.selected_edge_index - 1, 0)
        self.refresh_view()

    def refresh_view(self) -> None:
        paths = self.iterations[self.iter_index].all_paths
        if paths:
            self.selected_edge_index = max(0, min(self.selected_edge_index, len(paths) - 1))
        else:
            self.selected_edge_index = 0
        info = self.query_one("#info", Static)
        canvas = self.query_one("#canvas", Container)
        sidebar = self.query_one("#sidebar", Static)
        info.update(self.info_text())
        renderable = self.render_scene()
        content = canvas.query_one("#canvas-content", Static)
        content.update(renderable)
        sidebar.update(self.sidebar_text())

    def info_text(self) -> Text:
        iteration = self.iterations[self.iter_index]
        text = Text()
        text.append(f"Trace: {self.trace_path.name}  ")
        text.append(f"Iteration {self.iter_index + 1}/{len(self.iterations)}  ")
        text.append(f"Overflow total: {iteration.overflow.get('total', 0)}  ")
        text.append(
            f"[H:{'on' if self.show_heat_h else 'off'} "
            f"V:{'on' if self.show_heat_v else 'off'} "
            f"C:{'on' if self.show_heat_corners else 'off'} "
            f"E:{self.edge_display_mode} "
            f"N:{'on' if self.show_nodes else 'off'} "
            f"Rip:{'on' if self.show_ripups else 'off'}]"
        )
        return text

    def sidebar_text(self) -> Text:
        iteration = self.iterations[self.iter_index]
        lines = []
        for idx, path in enumerate(iteration.all_paths):
            directed = path.get("directed_path", [])
            if not directed:
                continue
            start = directed[0]
            end = directed[-1]
            rip = any(
                (start["x"], start["y"], end["x"], end["y"])
                == (edge["start"]["x"], edge["start"]["y"], edge["end"]["x"], edge["end"]["y"])
                for edge in iteration.ripped_up_next
            )
            marker = "➤" if idx == self.selected_edge_index else " "
            lines.append(
                f"{marker} {idx:02d} ({start['x']},{start['y']})→({end['x']},{end['y']}) len={len(directed)}{' RIP' if rip else ''}"
            )
        selected = None
        if iteration.all_paths and 0 <= self.selected_edge_index < len(iteration.all_paths):
            selected = iteration.all_paths[self.selected_edge_index]
        detail = ""
        if selected:
            directed = selected.get("directed_path", [])
            if directed:
                detail = "\n".join(
                    [
                        f"Start: ({directed[0]['x']},{directed[0]['y']})",
                        f"End:   ({directed[-1]['x']},{directed[-1]['y']})",
                        f"Steps: {len(directed)}",
                    ]
                )
        sidebar = Text()
        sidebar.append("\n".join(lines) or "(no edges)")
        if detail:
            sidebar.append("\n\n")
            sidebar.append(detail)
        return sidebar

    def render_scene(self) -> Text:
        layout = self.layout
        iteration = self.iterations[self.iter_index]
        width = layout.width
        height = layout.height
        cells = [[Cell() for _ in range(width)] for _ in range(height)]

        horiz_count = (width - 1) * height

        def cell_from_raw(x_raw: int, y_raw: int) -> tuple[int, int]:
            return x_raw - layout.top_left[0], y_raw - layout.top_left[1]

        # Heatmaps for segments
        if self.show_heat_h or self.show_heat_v:
            for idx, usage in enumerate(iteration.raw_usage):
                if idx < horiz_count:
                    if not self.show_heat_h:
                        continue
                    x = idx % (width - 1)
                    y = idx // (width - 1)
                else:
                    if not self.show_heat_v:
                        continue
                    vert_idx = idx - horiz_count
                    x = vert_idx // (height - 1)
                    y = vert_idx % (height - 1)
                color = usage_color(usage)
                if color:
                    cx, cy = x, y
                    if 0 <= cx < width and 0 <= cy < height:
                        cells[cy][cx].set(char="·", bg=color)

        # Heatmap for corners (grid points)
        if self.show_heat_corners:
            for idx, usage in enumerate(iteration.raw_corner_usage):
                color = usage_color(usage)
                if not color:
                    continue
                x = layout.top_left[0] + (idx % width)
                y = layout.top_left[1] + (idx // width)
                cx, cy = cell_from_raw(x, y)
                if 0 <= cx < width and 0 <= cy < height:
                    cells[cy][cx].set(char="·", bg=color)

        # Grid points
        for gp in layout.grid_points:
            gx, gy = gp["raw"]["x"], gp["raw"]["y"]
            cx, cy = cell_from_raw(gx, gy)
            if 0 <= cx < width and 0 <= cy < height:
                blocked = gp.get("blocked", False)
                masked_adjacent = gp.get("masked_adjacent", False)
                if blocked:
                    fg = "#9f0d0d"
                elif masked_adjacent:
                    fg = "#06b6d4"
                else:
                    fg = "#6b7280"
                cells[cy][cx].set(char="·", fg=fg)

        # Determine ripped-up edges (start/end match)
        ripup_pairs = {
            (edge["start"]["x"], edge["start"]["y"], edge["end"]["x"], edge["end"]["y"])
            for edge in iteration.ripped_up_next
        }

        # Paths and endpoints
        draw_edges = self.edge_display_mode in ("edges", "edges_endpoints")
        draw_endpoints = self.edge_display_mode in ("endpoints", "edges_endpoints")

        selected_path = None
        if draw_edges:
            # First pass: draw non-selected edges
            for idx, path_entry in enumerate(iteration.all_paths):
                directed = path_entry.get("directed_path", [])
                if not directed:
                    continue
                if idx == self.selected_edge_index:
                    selected_path = path_entry
                    continue
                start = directed[0]
                end = directed[-1]
                ripup = (start["x"], start["y"], end["x"], end["y"]) in ripup_pairs if self.show_ripups else False
                color = "#a855f7" if ripup else "#2563eb"
                # Deduplicate consecutive identical points to preserve corners
                points: list[tuple[int, int]] = []
                for p in directed:
                    pt = (p["x"], p["y"])
                    if not points or points[-1] != pt:
                        points.append(pt)
                for point in points:
                    cx, cy = cell_from_raw(point[0], point[1])
                    if 0 <= cx < width and 0 <= cy < height:
                        cells[cy][cx].set(char="■", fg=color)

            # Selected edge drawn last on top with heavy strokes
            if selected_path:
                directed = selected_path.get("directed_path", [])
                points: list[tuple[int, int]] = []
                for p in directed:
                    pt = (p["x"], p["y"])
                    if not points or points[-1] != pt:
                        points.append(pt)
                for point in points:
                    cx, cy = cell_from_raw(point[0], point[1])
                    if 0 <= cx < width and 0 <= cy < height:
                        cells[cy][cx].set(char="■", fg="#facc15")

        if draw_endpoints:
            for path_entry in iteration.all_paths:
                directed = path_entry.get("directed_path", [])
                if not directed:
                    continue
                start = directed[0]
                end = directed[-1]
                sx, sy = cell_from_raw(start["x"], start["y"])
                ex, ey = cell_from_raw(end["x"], end["y"])
                if 0 <= sx < width and 0 <= sy < height:
                    cells[sy][sx].set(char="*", fg="#f59e0b")
                if 0 <= ex < width and 0 <= ey < height:
                    cells[ey][ex].set(char="+", fg="#22d3ee")

        # Nodes last so they stay intact over paths/heatmaps
        if self.show_nodes:
            for node in layout.nodes:
                tlx, tly = node["top_left"]["x"], node["top_left"]["y"]
                brx, bry = node["bottom_right"]["x"], node["bottom_right"]["y"]
                for y in range(tly, bry + 1):
                    for x in range(tlx, brx + 1):
                        cx, cy = cell_from_raw(x, y)
                        if 0 <= cx < width and 0 <= cy < height:
                            edge_cell = x in (tlx, brx) or y in (tly, bry)
                            cells[cy][cx].set(char="█" if edge_cell else "▒", fg="#cbd5e1", bg="#1f2937")

        lines = ["".join(cell.to_markup() for cell in row) for row in cells]
        txt = Text.from_markup("\n".join(lines))
        txt.no_wrap = True
        txt.overflow = "ignore"
        return txt


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Routing trace debugger")
    parser.add_argument("trace", type=Path, help="Path to routing trace JSON")
    args = parser.parse_args(argv)
    if not args.trace.exists():
        raise SystemExit(f"Trace file not found: {args.trace}")
    RoutingTraceApp(args.trace).run()


if __name__ == "__main__":
    main()
