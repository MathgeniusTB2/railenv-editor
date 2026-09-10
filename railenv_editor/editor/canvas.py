"""The grid canvas: shows the Flatland PILSVG render and supports painting.

Rails are rendered to a QImage with Flatland's ``RenderTool(gl="PILSVG")``
backend and displayed as the scene background. That render runs on a background
thread; edits paint an instant rail overlay for changed cells until the
authentic PILSVG backdrop catches up. Cells use absolute ``(x, y)`` coordinates
(backed by ``GridModel.origin``) so the grid can auto-expand in any direction.
Hover/selection/agent markers are drawn as translucent overlays on top.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QObject, QPoint, QPointF, QRectF, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap, QUndoCommand, QUndoStack
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
)

from ..core.grid_model import GridModel
from ..core.transitions import CITY, EMPTY, exit_dirs, flip_value, rotate, value_to_tile

SCALE = 72
AIR = 6  # empty cells of "air" around the grid so you can draw past an edge
SELECT_COLOR = QColor(255, 200, 87, 120)
PREVIEW_COLOR = QColor(255, 152, 0, 110)
PENDING_COLOR = QColor(80, 160, 220, 200)
GHOST_COLOR = QColor(120, 200, 120, 150)
ERASE_COLOR = QColor(239, 83, 80, 150)
AGENT_COLOR = QColor(66, 133, 244)
TARGET_COLOR = QColor(234, 67, 53)

_MID = [(0.5, 0.0), (1.0, 0.5), (0.5, 1.0), (0.0, 0.5)]  # N E S W side midpoints


def _open_sides(value: int) -> list[int]:
    if value == 0:
        return []
    sides = set()
    for inc in range(4):
        for out in exit_dirs(value, inc):
            sides.add(inc)
            sides.add(out)
    return sorted(sides)


def _cell_segments(x: int, y: int, cell_px: int, value: int) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    ox, oy = x * cell_px, y * cell_px

    def pt(s: int) -> tuple[float, float]:
        return (ox + _MID[s][0] * cell_px, oy + _MID[s][1] * cell_px)

    sides = _open_sides(value)
    if not sides:
        return []
    if len(sides) == 2:
        a, b = sides
        if a % 2 == b % 2:
            return [(pt(a), pt(b))]
        corner = _MID[min(a, b)]
        c = (ox + corner[0] * cell_px, oy + corner[1] * cell_px)
        return [(pt(a), c), (c, pt(b))]
    cx, cy = ox + cell_px / 2, oy + cell_px / 2
    return [((cx, cy), pt(s)) for s in sides]


def _diff_cells(a: np.ndarray, b: np.ndarray) -> set[tuple[int, int]]:
    a = a.astype(np.int32)
    b = b.astype(np.int32)
    if a.shape != b.shape:
        return set()
    rows, cols = np.nonzero(a != b)
    return {(int(col), int(row)) for row, col in zip(rows, cols, strict=True)}


class PilsvgRenderer:
    """Render a uint16 grid to a numpy RGBA array using Flatland's PILSVG backend."""

    def __init__(self, scale: int = SCALE) -> None:
        self.scale = scale

    def render_array(self, cells: np.ndarray, city_cells: set[tuple[int, int]] | None = None) -> tuple[np.ndarray, int]:
        """Return (cropped uint8 RGBA array HxWx? , cell_px). No Qt objects created."""
        from flatland.envs.grid.rail_env_grid import RailEnvTransitions
        from flatland.envs.line_generators import Line
        from flatland.envs.rail_env import RailEnv
        from flatland.envs.rail_generators import rail_from_grid_transition_map
        from flatland.envs.rail_grid_transition_map import RailGridTransitionMap
        from flatland.utils.rendertools import RenderTool
        from PIL import Image

        g = np.asarray(cells, dtype=np.uint16)
        rows, cols = g.shape
        rm = RailGridTransitionMap(width=cols, height=rows, transitions=RailEnvTransitions(), grid=g)

        def line_gen(rail, num_agents, hints, num_resets, np_random):
            return Line(agent_waypoints={}, agent_speeds=[])

        def timetable(agents, distance_map, hints, np_random):
            class T:
                pass

            t = T()
            t.max_episode_steps = 1
            t.earliest_departures = []
            t.latest_arrivals = []
            return t

        env = RailEnv(
            width=cols,
            height=rows,
            rail_generator=rail_from_grid_transition_map(rm),
            line_generator=line_gen,
            timetable_generator=timetable,
            number_of_agents=0,
        )
        rt = RenderTool(env, gl="PILSVG", screen_width=cols * self.scale, screen_height=rows * self.scale)
        env.reset()
        arr = rt.render_env(show=False, show_agents=False, show_observations=False, return_image=True)
        rt.close_window()

        if city_cells:
            gl = rt.gl
            space = max(1, int(round((arr.shape[1] - 4) / cols)))
            building = gl.station_colors[4 % len(gl.station_colors)].resize((space, space))
            img = Image.fromarray(arr)
            for (c, r) in city_cells:
                if 0 <= c < cols and 0 <= r < rows:
                    img.paste(building, (c * space, r * space), building)
            arr = np.asarray(img)

        cell_px = max(1, int(round((arr.shape[1] - 4) / cols)))
        cropped = arr[: rows * cell_px, : cols * cell_px]
        return np.ascontiguousarray(cropped), cell_px

    def render(self, cells: np.ndarray, city_cells: set[tuple[int, int]] | None = None) -> tuple[QImage, int]:
        arr, cell_px = self.render_array(cells, city_cells)
        h, w = arr.shape[0], arr.shape[1]
        img = QImage(arr.data, w, h, arr.strides[0], QImage.Format_RGBA8888).copy()
        return img, cell_px


class _RenderWorker(QObject):
    """Runs on a dedicated QThread; renders to numpy bytes (no Qt objects)."""

    done = Signal(int, bytes, int, int, int, int, object, object, object)  # gen, raw, w, h, stride, cell_px, cells, cities, origin

    def __init__(self) -> None:
        super().__init__()
        self.renderer = PilsvgRenderer(SCALE)

    @Slot(object, object, object, int)
    def render(self, grid: np.ndarray, cities: set, origin: tuple, generation: int) -> None:
        try:
            arr, cell_px = self.renderer.render_array(grid, cities)
        except Exception:
            self.done.emit(generation, b"", 0, 0, 0, 0, grid, cities, origin)
            return
        raw = bytes(np.ascontiguousarray(arr).data)
        self.done.emit(generation, raw, arr.shape[1], arr.shape[0], arr.strides[0],
                       cell_px, grid, cities, origin)


class RailGraphicsScene(QGraphicsScene):
    """Renders a GridModel via PILSVG (async) and handles painting/selection."""

    model_changed = Signal()
    _render_request = Signal(object, object, object, int)  # grid, cities, origin, generation

    def __init__(self, model: GridModel, parent=None) -> None:
        super().__init__(parent)
        self.model = model
        self.undo_stack = QUndoStack(self)
        self.renderer = PilsvgRenderer(SCALE)

        self.tool = "paint"
        self.current_tile_name = "vertical_straight"
        self.current_tile = 32800  # base value
        self.rotation = 0
        self.cell_px = SCALE

        self._bg_item: QGraphicsPixmapItem | None = None
        self._overlay_items: list[QGraphicsItem] = []
        self._selected: set[tuple[int, int]] = set()
        self._preview_cells: list[tuple[int, int]] = []
        self._pending: set[tuple[int, int]] = set()
        self._hover_cell: tuple[int, int] | None = None

        self._seg_start: tuple[int, int] | None = None
        self._seg_end: tuple[int, int] | None = None
        self._seg_erase = False
        self._marquee_start: tuple[int, int] | None = None
        self._clipboard: list[list[int]] = []

        self._render_thread = QThread(self)
        self._render_worker = _RenderWorker()
        self._render_worker.moveToThread(self._render_thread)
        self._render_thread.start()
        self._render_worker.done.connect(self._on_render_done, Qt.QueuedConnection)
        self._render_request.connect(self._render_worker.render, Qt.QueuedConnection)
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(40)
        self._render_timer.timeout.connect(self._do_render)
        self._busy = False
        self._rerender = False
        self._generation = 0
        self._snapshot = None

        self._rebuild()

    # ------------------------------------------------------------- layout/render
    def set_model(self, model: GridModel) -> None:
        self.model = model
        self._rebuild()

    def _rebuild(self) -> None:
        self.clear()
        self._overlay_items.clear()
        self._selected.clear()
        self._preview_cells.clear()
        self._pending.clear()
        self._hover_cell = None
        self._refresh_scene_rect()
        self._bg_item = QGraphicsPixmapItem()
        self._bg_item.setZValue(-10)
        self.addItem(self._bg_item)
        self._schedule_render()

    def _refresh_scene_rect(self) -> None:
        ox, oy = self.model.origin
        minx = ox - AIR
        miny = oy - AIR
        maxx = ox + self.model.width - 1 + AIR
        maxy = oy + self.model.height - 1 + AIR
        self.setSceneRect(minx * self.cell_px, miny * self.cell_px,
                          (maxx - minx + 1) * self.cell_px, (maxy - miny + 1) * self.cell_px)

    def _schedule_render(self) -> None:
        self._render_timer.start()

    def set_background(self, qimg: QImage, cell_px: int, origin: tuple[int, int]) -> None:
        if self._bg_item is None:
            return
        self.cell_px = cell_px
        self._bg_item.setPixmap(QPixmap.fromImage(qimg))
        self._bg_item.setPos(origin[0] * cell_px, origin[1] * cell_px)
        self._refresh_scene_rect()

    def _do_render(self) -> None:
        if self._busy:
            self._rerender = True
            return
        ox, oy = self.model.origin
        cells = np.array(self.model.cells, dtype=np.uint16, copy=True)
        cities = {(x - ox, y - oy) for x, y in self.model.cities}
        self._generation += 1
        self._busy = True
        self._snapshot = (cells, cities, (ox, oy))
        self._render_request.emit(cells, cities, (ox, oy), self._generation)

    def _on_render_done(self, generation: int, raw: bytes, width: int, height: int, stride: int,
                        cell_px: int, snapshot_cells: np.ndarray, snapshot_cities: set,
                        origin: tuple[int, int]) -> None:
        self._busy = False
        try:
            if generation == self._generation and raw and cell_px > 0:
                rows, cols = snapshot_cells.shape
                expected_w, expected_h = cols * cell_px, rows * cell_px
                if width == expected_w and height == expected_h and stride >= width * 4 and len(raw) >= stride * height:
                    arr = np.frombuffer(raw, dtype=np.uint8).reshape(height, stride).copy()
                    arr = arr[:, : width * 4].reshape(height, width, 4)  # drop any padding
                    img = QImage(arr.data, width, height, width * 4, QImage.Format_RGBA8888).copy()
                    self.set_background(img, cell_px, origin)
                    self._pending = _diff_cells(snapshot_cells, self.model.cells)
                    ox, oy = origin
                    old_cities = {(ox + c, oy + r) for c, r in snapshot_cities}
                    self._pending |= old_cities ^ set(self.model.cities)
                    self._update_overlays()
        except Exception:
            pass
        if self._rerender:
            self._rerender = False
            self._schedule_render()

    def shutdown(self) -> None:
        self._render_thread.quit()
        self._render_thread.wait(2000)

    def request_render(self) -> None:
        self._schedule_render()

    def cell_at(self, pos: QPointF) -> tuple[int, int] | None:
        if not self.sceneRect().contains(pos):
            return None
        return (int(pos.x()) // self.cell_px, int(pos.y()) // self.cell_px)

    def _rect(self, cell: tuple[int, int]) -> QRectF:
        x, y = cell
        return QRectF(x * self.cell_px, y * self.cell_px, self.cell_px, self.cell_px)

    # ------------------------------------------------------------- tools
    def value_for_current_tool(self) -> int:
        if self.current_tile_name in (CITY, EMPTY):
            return 0
        return rotate(self.current_tile, self.rotation)

    def is_current_city(self) -> bool:
        return self.current_tile_name == CITY

    def set_tool(self, name: str) -> None:
        self.tool = name
        self._seg_start = None
        self._seg_end = None
        self._marquee_start = None
        self._hover_cell = None
        self._update_overlays()

    def select_tile(self, name: str, value: int) -> None:
        self.current_tile_name = name
        self.current_tile = int(value)
        self.rotation = 0
        self._update_overlays()

    def rotate_tile(self, direction: int) -> None:
        if self.current_tile_name in (CITY, EMPTY):
            return
        self.rotation = (self.rotation + (90 if direction > 0 else -90)) % 360
        self._update_overlays()

    def flip_tile(self) -> None:
        if self.current_tile_name in (CITY, EMPTY):
            return
        self.current_tile = flip_value(self.value_for_current_tool())
        self.rotation = 0
        hit = value_to_tile(self.current_tile)
        if hit:
            self.current_tile_name = hit[0]
        self._update_overlays()

    # ------------------------------------------------------------- painting
    def begin_segment(self, cell: tuple[int, int], erase: bool) -> None:
        self._seg_start = cell
        self._seg_end = cell
        self._seg_erase = erase
        self._hover_cell = None
        self._preview_cells = [cell]
        self._update_overlays()

    def preview_segment(self, cell: tuple[int, int]) -> None:
        if self._seg_start is None:
            return
        self._seg_end = cell
        self._preview_cells = self._segment_cells(self._seg_start, cell)
        self._update_overlays()

    def commit_segment(self, cell: tuple[int, int]) -> None:
        if self._seg_start is None:
            return
        cells = self._segment_cells(self._seg_start, cell)
        self.model.grow_to_include(cells)
        value = 0 if self._seg_erase else self.value_for_current_tool()
        city = (not self._seg_erase) and self.is_current_city()
        self.undo_stack.push(PlaceCellsCommand(self, cells, value, city))
        self._seg_start = None
        self._seg_end = None
        self._preview_cells = []
        self._update_overlays()

    def cancel_segment(self) -> None:
        self._seg_start = None
        self._seg_end = None
        self._preview_cells = []
        self._update_overlays()

    @staticmethod
    def _segment_cells(a: tuple[int, int], b: tuple[int, int]) -> list[tuple[int, int]]:
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        cells = []
        if abs(dx) >= abs(dy):
            step = 1 if bx >= ax else -1
            cells.extend((x, ay) for x in range(ax, bx + step, step))
        else:
            step = 1 if by >= ay else -1
            cells.extend((ax, y) for y in range(ay, by + step, step))
        return cells

    def paste_clipboard(self, cell: tuple[int, int]) -> None:
        if self._clipboard:
            self.model.grow_to_include(self._paste_cells(cell))
            self.undo_stack.push(PasteCommand(self, cell, self._clipboard))

    def _paste_cells(self, origin: tuple[int, int]) -> set[tuple[int, int]]:
        cells = set()
        for dy, row in enumerate(self._clipboard):
            for dx, v in enumerate(row):
                if v >= 0:
                    cells.add((origin[0] + dx, origin[1] + dy))
        return cells

    def clear_all(self) -> None:
        if not np.any(self.model.cells) and not self.model.cities:
            return
        self.undo_stack.push(ClearCommand(self))

    # ------------------------------------------------------------- signalling
    def mark_cells_changed(self, cells: set[tuple[int, int]]) -> None:
        self._pending |= {c for c in cells if self.model.in_bounds(*c)}
        self._update_overlays()
        self.model_changed.emit()
        self._schedule_render()

    def _apply_grid(self, new: np.ndarray, origin: tuple[int, int] | None = None, cities: set | None = None) -> None:
        old_cells = np.array(self.model.cells, dtype=np.uint16, copy=True)
        old_cities = set(self.model.cities)
        self.model.cells = new
        self.model.height, self.model.width = new.shape
        if origin is not None:
            self.model.origin = (int(origin[0]), int(origin[1]))
        if cities is not None:
            self.model.cities = set(cities)
        self._refresh_scene_rect()
        self._pending = _diff_cells(old_cells, self.model.cells) | (old_cities ^ self.model.cities)
        self._update_overlays()
        self.model_changed.emit()
        self._schedule_render()

    # ------------------------------------------------------------- selection
    def begin_marquee(self, cell: tuple[int, int]) -> None:
        self._marquee_start = cell

    def set_marquee_to(self, cell: tuple[int, int]) -> None:
        if self._marquee_start is None:
            return
        self._selected = set(self._cells_in_rect(self._marquee_start, cell))
        self._update_overlays()

    def finish_marquee(self, cell: tuple[int, int]) -> None:
        if self._marquee_start is None:
            return
        self._selected = set(self._cells_in_rect(self._marquee_start, cell))
        self._marquee_start = None
        self._update_overlays()

    @staticmethod
    def _cells_in_rect(a: tuple[int, int], b: tuple[int, int]) -> list[tuple[int, int]]:
        x0, x1 = sorted((a[0], b[0]))
        y0, y1 = sorted((a[1], b[1]))
        return [(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]

    def select_cell(self, cell: tuple[int, int]) -> None:
        self._selected = {cell}
        self._update_overlays()

    def _selected_cells(self) -> set[tuple[int, int]]:
        return set(self._selected)

    def copy_selection(self) -> None:
        if not self._selected:
            return
        xs = [c[0] for c in self._selected]
        ys = [c[1] for c in self._selected]
        min_x, min_y = min(xs), min(ys)
        grid = []
        for y in range(min_y, max(ys) + 1):
            row = [self.model.get(x, y) if (x, y) in self._selected else -1 for x in range(min_x, max(xs) + 1)]
            grid.append(row)
        self._clipboard = grid

    # ------------------------------------------------------------- hover preview
    def set_hover(self, cell: tuple[int, int] | None) -> None:
        if self._hover_cell == cell:
            return
        self._hover_cell = cell
        self._update_overlays()

    # ------------------------------------------------------------- overlay
    def _add_rail_lines(self, cell: tuple[int, int], pen: QPen) -> None:
        cp = self.cell_px
        x, y = cell
        v = self.model.get(x, y)
        for p0, p1 in _cell_segments(x, y, cp, v):
            self._overlay_items.append(self.addLine(p0[0], p0[1], p1[0], p1[1], pen))
            it = self._overlay_items[-1]
            it.setZValue(5)

    def _add_pix(self, pixmap: QPixmap, cell: tuple[int, int], opacity: float) -> None:
        item = QGraphicsPixmapItem(pixmap)
        item.setPos(cell[0] * self.cell_px, cell[1] * self.cell_px)
        item.setOpacity(opacity)
        item.setZValue(6)
        self.addItem(item)
        self._overlay_items.append(item)

    def _update_overlays(self) -> None:
        from .icons import pixmaps, value_icon

        for it in self._overlay_items:
            self.removeItem(it)
        self._overlay_items.clear()
        pen = QPen(QColor(0, 0, 0, 0), 0)
        icons = pixmaps()

        # pending (edited but not yet re-rendered) cells -> instant pilsvg feedback
        tint = QColor(PENDING_COLOR.red(), PENDING_COLOR.green(), PENDING_COLOR.blue(), 28)
        for cell in self._pending:
            self._overlay_items.append(self.addRect(self._rect(cell), pen, tint))
            if self.model.in_bounds(*cell):
                x, y = cell
                if (x, y) in self.model.cities:
                    self._add_pix(icons.get(CITY), cell, 0.8)
                else:
                    v = self.model.get(x, y)
                    vp = value_icon(v)
                    if vp is not None:
                        self._add_pix(vp, cell, 1.0)

        if self._hover_cell is not None and self.tool in ("paint", "erase"):
            hc = self._hover_cell
            if self.tool == "erase":
                self._overlay_items.append(self.addRect(self._rect(hc), pen, ERASE_COLOR))
                if self.model.in_bounds(*hc):
                    self._add_rail_lines(hc, QPen(ERASE_COLOR, 3, Qt.SolidLine, Qt.RoundCap))
            elif self.is_current_city():
                self._overlay_items.append(self.addRect(self._rect(hc), pen, QColor(*GHOST_COLOR.toTuple()[:3], 60)))
                self._add_pix(icons.get(CITY), hc, 0.7)
            elif self.current_tile_name == EMPTY:
                self._overlay_items.append(self.addRect(self._rect(hc), pen, QColor(255, 255, 255, 90)))
            else:
                self._overlay_items.append(self.addRect(self._rect(hc), pen, QColor(*GHOST_COLOR.toTuple()[:3], 60)))
                vp = value_icon(self.value_for_current_tool())
                if vp is not None:
                    self._add_pix(vp, hc, 0.6)

        for cell in self._preview_cells:
            self._overlay_items.append(self.addRect(self._rect(cell), pen, PREVIEW_COLOR))
            if self._seg_erase:
                if self.model.in_bounds(*cell):
                    self._add_rail_lines(cell, QPen(ERASE_COLOR, 3, Qt.SolidLine, Qt.RoundCap))
            elif self.is_current_city():
                self._add_pix(icons.get(CITY), cell, 0.6)
            else:
                vp = value_icon(self.value_for_current_tool())
                if vp is not None:
                    self._add_pix(vp, cell, 0.6)

        for cell in self._selected:
            self._overlay_items.append(self.addRect(self._rect(cell), pen, SELECT_COLOR))

        for it in self._overlay_items:
            it.setZValue(5)


class PlaceCellsCommand(QUndoCommand):
    def __init__(self, scene: RailGraphicsScene, cells: list[tuple[int, int]], value: int, city: bool) -> None:
        super().__init__("place")
        self.scene = scene
        self.cells = cells
        self.value = value
        self.city = city
        self.old_rail = {c: scene.model.get(*c) for c in cells}
        self.old_city = {c: c in scene.model.cities for c in cells}

    def _apply(self) -> None:
        model = self.scene.model
        for (x, y) in self.cells:
            model.set(x, y, 0 if self.city else self.value)
            if self.city:
                model.cities.add((x, y))
            else:
                model.cities.discard((x, y))
        self.scene.mark_cells_changed(set(self.cells))

    def redo(self) -> None:
        self._apply()

    def undo(self) -> None:
        model = self.scene.model
        for cell in self.cells:
            model.set(*cell, self.old_rail[cell])
            if self.old_city[cell]:
                model.cities.add(cell)
            else:
                model.cities.discard(cell)
        self.scene.mark_cells_changed(set(self.cells))


class ClearCommand(QUndoCommand):
    def __init__(self, scene: RailGraphicsScene) -> None:
        super().__init__("clear")
        self.scene = scene
        self.before_cells = scene.model.cells.copy()
        self.before_cities = set(scene.model.cities)
        self.before_origin = scene.model.origin

    def redo(self) -> None:
        self.scene._apply_grid(np.zeros_like(self.before_cells), self.before_origin, set())

    def undo(self) -> None:
        self.scene._apply_grid(self.before_cells, self.before_origin, self.before_cities)


class PasteCommand(QUndoCommand):
    def __init__(self, scene: RailGraphicsScene, origin: tuple[int, int], clipboard: list[list[int]]):
        super().__init__("paste")
        self.scene, self.ox, self.oy, self.clipboard = scene, origin[0], origin[1], clipboard
        self.snapshot = scene.model.cells.copy()
        self.snapshot_cities = set(scene.model.cities)

    def redo(self) -> None:
        model = self.scene.model
        for dy, row in enumerate(self.clipboard):
            for dx, v in enumerate(row):
                if v < 0:
                    continue
                x, y = self.ox + dx, self.oy + dy
                if model.in_bounds(x, y):
                    model.set(x, y, v)
                    model.cities.discard((x, y))
        self.scene.mark_cells_changed(self.scene._paste_cells((self.ox, self.oy)))

    def undo(self) -> None:
        self.scene._apply_grid(self.snapshot, self.scene.model.origin, self.snapshot_cities)


class RailView(QGraphicsView):
    """Scrollable, zoomable view over the PILSVG scene."""

    WHEEL_BASE = 1.12   # gentler zoom per wheel notch
    MIN_SCALE = 0.04    # still zoomable back in
    MAX_SCALE = 40.0

    def __init__(self, scene: RailGraphicsScene, parent=None) -> None:
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing, True)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setFocusPolicy(Qt.StrongFocus)
        self._panning = False
        self._pan_start = QPoint()
        self._arrow_keys: set[Qt.Key] = set()
        self._arrow_timer = QTimer(self)
        self._arrow_timer.setInterval(16)
        self._arrow_timer.timeout.connect(self._scroll_by_arrows)

    # ------------------------------------------------------------- zoom / pan
    def _zoom(self, delta: int) -> None:
        if delta == 0:
            return
        factor = self.WHEEL_BASE ** (delta / 120.0)
        current = self.transform().m11()
        new = current * factor
        if new < self.MIN_SCALE:
            factor = self.MIN_SCALE / current
        elif new > self.MAX_SCALE:
            factor = self.MAX_SCALE / current
        self.scale(factor, factor)

    def _pan_by(self, dx: int, dy: int) -> None:
        if dx == 0 and dy == 0:
            return
        h = self.horizontalScrollBar()
        v = self.verticalScrollBar()
        h.setValue(h.value() - dx)
        v.setValue(v.value() - dy)

    def _scroll_by_arrows(self) -> None:
        step = 40
        h = self.horizontalScrollBar()
        v = self.verticalScrollBar()
        if Qt.Key_Left in self._arrow_keys:
            h.setValue(h.value() - step)
        if Qt.Key_Right in self._arrow_keys:
            h.setValue(h.value() + step)
        if Qt.Key_Up in self._arrow_keys:
            v.setValue(v.value() - step)
        if Qt.Key_Down in self._arrow_keys:
            v.setValue(v.value() + step)

    def wheelEvent(self, event) -> None:
        # pinch (Cmd/Ctrl + two-finger) -> zoom
        if event.modifiers() & Qt.ControlModifier:
            self._zoom(event.angleDelta().y())
            return
        pd = event.pixelDelta()
        # trackpad two-finger scroll -> pan
        if pd.x() != 0 or pd.y() != 0:
            self._pan_by(pd.x(), pd.y())
            return
        # discrete mouse wheel -> zoom
        self._zoom(event.angleDelta().y())

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down) and not event.isAutoRepeat():
            self._arrow_keys.add(event.key())
            self._arrow_timer.start()
            self._scroll_by_arrows()
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if event.key() in self._arrow_keys:
            self._arrow_keys.discard(event.key())
            if not self._arrow_keys:
                self._arrow_timer.stop()
            event.accept()
            return
        super().keyReleaseEvent(event)

    def focusOutEvent(self, event) -> None:
        self._arrow_keys.clear()
        self._arrow_timer.stop()
        super().focusOutEvent(event)

    def mousePressEvent(self, event) -> None:
        scene = self.scene()  # type: RailGraphicsScene
        pos = self.mapToScene(event.pos())
        cell = scene.cell_at(pos)
        if event.button() == Qt.MiddleButton:
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.LeftButton:
            if scene.tool == "paste" and scene._clipboard and cell is not None:
                scene.paste_clipboard(cell)
                scene.tool = "select"
                self.viewport().update()
                event.accept()
                return
            if scene.tool in ("paint", "erase") and cell is not None:
                scene.begin_segment(cell, erase=(scene.tool == "erase"))
                event.accept()
                return
            if scene.tool == "select" and cell is not None:
                scene.begin_marquee(cell)
                scene.select_cell(cell)
                scene.selectionChanged.emit()
                event.accept()
                return
            if scene.tool == "move":
                self._panning = True
                self._pan_start = event.pos()
                self.setCursor(Qt.ClosedHandCursor)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        scene = self.scene()  # type: RailGraphicsScene
        if self._panning:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        pos = self.mapToScene(event.pos())
        if scene.tool in ("paint", "erase") and event.buttons() & Qt.LeftButton:
            cell = scene.cell_at(pos)
            if cell is not None:
                scene.preview_segment(cell)
            event.accept()
            return
        if scene.tool in ("paint", "erase"):
            scene.set_hover(scene.cell_at(pos))
            event.accept()
            return
        if scene.tool == "select" and event.buttons() & Qt.LeftButton:
            cell = scene.cell_at(pos)
            if cell is not None:
                scene.set_marquee_to(cell)
                scene.selectionChanged.emit()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        scene = self.scene()  # type: RailGraphicsScene
        if self._panning and event.button() in (Qt.MiddleButton, Qt.LeftButton):
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        pos = self.mapToScene(event.pos())
        if scene.tool in ("paint", "erase") and event.button() == Qt.LeftButton:
            cell = scene.cell_at(pos) or scene._seg_end
            if cell is not None:
                scene.commit_segment(cell)
            event.accept()
            return
        if scene.tool == "select" and event.button() == Qt.LeftButton:
            cell = scene.cell_at(pos) or scene._marquee_start
            if cell is not None:
                scene.finish_marquee(cell)
                scene.selectionChanged.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:
        scene = self.scene()  # type: RailGraphicsScene
        if scene.tool in ("paint", "erase"):
            scene.set_hover(None)
        super().leaveEvent(event)
