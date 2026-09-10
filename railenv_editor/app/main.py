"""Application entrypoint and main window wiring."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Pin BLAS/OMP to one thread so openblas doesn't busy-spin a thread pool and
# burn CPU while the app idles. Must run before anything imports numpy.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QAction, QKeySequence  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QSpinBox,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..core.grid_model import GridModel  # noqa: E402
from ..core.transitions import HOTKEY_TO_TILE, TILE_DEDUP, TILE_LABELS, is_rotatable  # noqa: E402
from ..editor.canvas import RailGraphicsScene, RailView  # noqa: E402
from ..editor.export import from_msgpack_env, to_msgpack_env  # noqa: E402
from ..editor.inspector import InspectorDock  # noqa: E402
from ..editor.palette import Palette  # noqa: E402
from ..editor.tilebar import TileBar  # noqa: E402

APP_TITLE = "RailEnv Editor"

TOOL_HOTKEYS = {"p": "paint", "e": "erase", "s": "select", "m": "move", "v": "paste"}


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1280, 900)
        self._dirty = False
        self._current_path: Path | None = None

        self.model = GridModel(width=20, height=20)
        self.scene = RailGraphicsScene(self.model)
        self.scene.undo_stack.cleanChanged.connect(self._on_clean_changed)

        self.view = RailView(self.scene)
        self.view.setScene(self.scene)

        self.palette = Palette()
        self.palette.tool_selected.connect(self._on_tool)
        self.palette.rotation_changed.connect(self._on_rotation)

        self.tilebar = TileBar()
        self.tilebar.tile_chosen.connect(self._on_tile)

        self.inspector = InspectorDock(self.model)

        self._build_toolbar()
        self._build_statusbar()

        # layout: [palette | view | inspector] on top, tile bar below
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(0)
        top.addWidget(self.palette)
        top.addWidget(self.view, 1)
        top.addWidget(self.inspector)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addLayout(top, 1)
        root.addWidget(self.tilebar)
        self.setCentralWidget(central)

        self._status_label = QLabel("Ready")
        self.statusBar().addWidget(self._status_label)

        self._connect_scene()
        self._update_title()
        self.refresh_all()
        self.view.setFocus()

    # ------------------------------------------------------------- toolbar
    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        tb.setMovable(False)
        self.addToolBar(tb)

        def act(text: str, slot, shortcut=None) -> QAction:
            a = QAction(text, self)
            a.triggered.connect(slot)
            if shortcut:
                a.setShortcut(QKeySequence(shortcut))
            tb.addAction(a)
            return a

        act("New", self.new_project, "Ctrl+N")
        act("Open...", self.open_project, "Ctrl+O")
        act("Save", self.save_project, "Ctrl+S")
        tb.addSeparator()

        self.act_undo = act("Undo", lambda: self.scene.undo_stack.undo(), "Ctrl+Z")
        self.act_redo = act("Redo", lambda: self.scene.undo_stack.redo(), "Ctrl+Y")
        tb.addSeparator()

        act("Clear", self.scene.clear_all)
        act("Trim to content", self.trim_to_content)
        tb.addSeparator()

        # grid size
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 200)
        self.width_spin.setValue(self.model.width)
        self.width_spin.setPrefix("W ")
        self.width_spin.valueChanged.connect(self._on_resize)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, 200)
        self.height_spin.setValue(self.model.height)
        self.height_spin.setPrefix("H ")
        self.height_spin.valueChanged.connect(self._on_resize)
        tb.addWidget(QLabel(" Grid: "))
        tb.addWidget(self.width_spin)
        tb.addWidget(self.height_spin)
        tb.addSeparator()

        export_btn = QAction("Export Env (.mpk)", self)
        export_btn.triggered.connect(self.export_env)
        tb.addAction(export_btn)

    def _build_statusbar(self) -> None:
        self.statusBar().addPermanentWidget(
            QLabel("  P/E/S/M tools · 0-9 tiles · R rotate · F flip · drag paints a line · drag past an edge grows the grid")
        )

    # ------------------------------------------------------------- wiring
    def _connect_scene(self) -> None:
        self.scene.model_changed.connect(self._on_changed)
        self.scene.selectionChanged.connect(self._on_selection)
        self.scene.undo_stack.canUndoChanged.connect(self.act_undo.setEnabled)
        self.scene.undo_stack.canRedoChanged.connect(self.act_redo.setEnabled)
        self.scene.undo_stack.cleanChanged.connect(self._on_clean_changed)

    def refresh_all(self) -> None:
        self.scene.request_render()
        self._on_selection()
        self._update_status()
        self._sync_grid_spinners()

    def _on_tile(self, name: str, value: int) -> None:
        self._apply_tile(name, value)

    def _apply_tile(self, name: str, value: int) -> None:
        self.scene.select_tile(name, value)
        self.palette.set_tool("paint")
        self.palette.show_rotation(is_rotatable(name))
        self.palette.set_rotation(0)
        self.tilebar.set_tile(name)
        self._status_label.setText(f"Tile: {TILE_LABELS.get(name, name)}")

    def _on_tool(self, name: str) -> None:
        self.scene.set_tool(name)
        self._status_label.setText(f"Tool: {name}")

    def _on_rotation(self, rotation: int) -> None:
        self.scene.rotation = rotation
        self._status_label.setText(f"Rotation: {rotation}°")

    def _on_resize(self, *_a) -> None:
        w = self.width_spin.value()
        h = self.height_spin.value()
        # confirm if a manual shrink would cut any drawn content
        bbox = self.model.content_bbox()
        if bbox is not None:
            minx, miny, maxx, maxy = bbox
            ox, oy = self.model.origin
            if (maxx - ox + 1 > w) or (maxy - oy + 1 > h):
                ans = QMessageBox.question(self, APP_TITLE, "Shrink the grid? Existing content outside the new size will be cut.")
                if ans != QMessageBox.StandardButton.Yes:
                    self._sync_grid_spinners()
                    return
        self.model.resize(w, h)
        self.scene._rebuild()
        self.refresh_all()
        self._mark_dirty()

    def trim_to_content(self) -> None:
        if self.model.shrink_to_content():
            self.scene._rebuild()
            self.refresh_all()
            self._mark_dirty()

    def _sync_grid_spinners(self) -> None:
        from PySide6.QtCore import QSignalBlocker

        with QSignalBlocker(self.width_spin), QSignalBlocker(self.height_spin):
            self.width_spin.setValue(self.model.width)
            self.height_spin.setValue(self.model.height)

    def _on_changed(self) -> None:
        self.refresh_all()

    def _on_selection(self) -> None:
        sel = self.scene._selected_cells()
        cell = next(iter(sel)) if sel else None
        self.inspector.set_cell(cell)

    def _on_clean_changed(self, clean: bool) -> None:
        self._update_title()

    def _mark_dirty(self) -> None:
        self._dirty = True
        self._update_title()

    def _update_title(self) -> None:
        dirty = "" if self.scene.undo_stack.isClean() else " *"
        name = self._current_path.name if self._current_path else "untitled"
        self.setWindowTitle(f"{APP_TITLE} - {name}{dirty}")

    # ------------------------------------------------------------- status
    def _update_status(self) -> None:
        ox, oy = self.model.origin
        self._status_label.setText(
            f"Grid {self.model.width}x{self.model.height} @({ox},{oy})"
        )

    # ------------------------------------------------------------- keys
    def keyPressEvent(self, event) -> None:
        mod = event.modifiers()
        if mod & Qt.ControlModifier or mod & Qt.AltModifier or mod & Qt.MetaModifier:
            super().keyPressEvent(event)
            return
        if self._text_widget_focused():
            super().keyPressEvent(event)
            return
        key = event.key()
        if key == Qt.Key_R:
            self.scene.rotate_tile(1 if not (mod & Qt.ShiftModifier) else -1)
            self.palette.set_rotation(self.scene.rotation)
            event.accept()
            return
        if key == Qt.Key_F:
            self.scene.flip_tile()
            event.accept()
            return
        ch = event.text().lower()
        if ch in TOOL_HOTKEYS:
            self._select_tool(TOOL_HOTKEYS[ch])
            event.accept()
            return
        if ch.isdigit():
            idx = int(ch)
            if idx in HOTKEY_TO_TILE:
                name, value = HOTKEY_TO_TILE[idx]
                self._select_tile(name, value)
                event.accept()
                return
        super().keyPressEvent(event)

    @staticmethod
    def _text_widget_focused() -> bool:
        w = QApplication.focusWidget()
        # Real text editors only. QSpinBox steps with digits so it is excluded —
        # otherwise a grid-size spinbox stealing focus would disable all shortcuts.
        return isinstance(w, (QLineEdit, QTextEdit, QPlainTextEdit, QComboBox))

    def _select_tool(self, name: str) -> None:
        self.scene.set_tool(name)
        self.palette.set_tool(name)
        self._status_label.setText(f"Tool: {name}")

    def _select_tile(self, name: str, value: int | None = None) -> None:
        if value is None:
            value = dict(TILE_DEDUP)[name]
        self._apply_tile(name, value)

    def closeEvent(self, event) -> None:
        self.scene.shutdown()
        super().closeEvent(event)

    # ------------------------------------------------------------- file ops
    def new_project(self) -> None:
        if not self._confirm_discard():
            return
        self.model = GridModel(width=20, height=20)
        self.scene.set_model(self.model)
        self.scene.undo_stack.clear()
        self.inspector.model = self.model
        self._current_path = None
        self._dirty = False
        self.width_spin.setValue(self.model.width)
        self.height_spin.setValue(self.model.height)
        self.refresh_all()
        self._update_title()

    def open_project(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open", "", "RailEnv Env (*.mpk);;RailEnv Project (*.railproj);;All files (*)"
        )
        if not path:
            return
        try:
            if Path(path).suffix.lower() == ".mpk":
                self.model = from_msgpack_env(Path(path))
            else:
                self.model = GridModel.load(Path(path))
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", str(exc))
            return
        self.scene.set_model(self.model)
        self.scene.undo_stack.clear()
        self.inspector.model = self.model
        self._current_path = Path(path)
        self._dirty = False
        self.width_spin.setValue(self.model.width)
        self.height_spin.setValue(self.model.height)
        self.refresh_all()
        self._update_title()

    def save_project(self) -> None:
        path = self._current_path
        if path is None:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save", "network.mpk", "RailEnv Env (*.mpk);;RailEnv Project (*.railproj)"
            )
            if not path:
                return
            path = Path(path)
        try:
            if path.suffix.lower() == ".mpk":
                to_msgpack_env(self.model, path)
            else:
                self.model.save(path)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        self._current_path = path
        self.scene.undo_stack.setClean()
        self._update_title()

    def _confirm_discard(self) -> bool:
        if self.scene.undo_stack.isClean():
            return True
        ans = QMessageBox.question(self, APP_TITLE, "Discard unsaved changes?")
        return ans == QMessageBox.StandardButton.Yes

    # ------------------------------------------------------------- export
    def export_env(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Export Env", "network.mpk", "Flatland env (*.mpk)")
        if not path:
            return
        try:
            to_msgpack_env(self.model, Path(path))
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
