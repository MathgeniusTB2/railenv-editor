"""Left-hand tool palette: select a tool and the tile rotation."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QGridLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class Palette(QWidget):
    """Tools (paint/erase/select/move/paste) and 0-90-180-270 rotation."""

    tool_selected = Signal(str)      # paint / erase / select / move / paste
    rotation_changed = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMaximumWidth(240)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Tools"))
        self._tool_group = QButtonGroup(self)
        tool_buttons = [
            ("paint", "Paint (P)"),
            ("erase", "Erase (E)"),
            ("select", "Select (S)"),
            ("move", "Move (M)"),
            ("paste", "Paste (V)"),
        ]
        grid = QGridLayout()
        for i, (name, label) in enumerate(tool_buttons):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.clicked.connect(lambda _=False, n=name: self._select_tool(n))
            self._tool_group.addButton(btn)
            grid.addWidget(btn, i // 2, i % 2)
        layout.addLayout(grid)
        self._tool_buttons = {n: b for (n, _), b in zip(tool_buttons, self._tool_group.buttons(), strict=True)}
        self._tool_buttons["paint"].setChecked(True)

        layout.addWidget(QLabel("Rotation"))
        self._rotation_box = QWidget()
        rot_outer = QVBoxLayout(self._rotation_box)
        rot_outer.setContentsMargins(0, 0, 0, 0)
        self._rot_group = QButtonGroup(self)
        rot_grid = QGridLayout()
        for idx, rot in enumerate([0, 90, 180, 270]):
            btn = QToolButton()
            btn.setText(f"{rot}°")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _=False, r=rot: self._choose_rotation(r))
            self._rot_group.addButton(btn)
            rot_grid.addWidget(btn, idx // 4, idx % 4)
        rot_outer.addLayout(rot_grid)
        layout.addWidget(self._rotation_box)
        self._rot_buttons = {r: b for r, b in zip([0, 90, 180, 270], self._rot_group.buttons(), strict=True)}
        self._rot_buttons[0].setChecked(True)
        self.rotation = 0

        layout.addStretch(1)

    def _select_tool(self, name: str) -> None:
        self.tool_selected.emit(name)

    def _choose_rotation(self, rot: int) -> None:
        self.rotation = rot
        self._rot_buttons[rot].setChecked(True)
        self.rotation_changed.emit(rot)

    def set_tool(self, name: str) -> None:
        if name in self._tool_buttons:
            self._tool_buttons[name].setChecked(True)

    def set_rotation(self, rot: int) -> None:
        self.rotation = rot % 360
        if self.rotation in self._rot_buttons:
            self._rot_buttons[self.rotation].setChecked(True)

    def show_rotation(self, visible: bool) -> None:
        self._rotation_box.setVisible(visible)
