"""Bottom tile bar: native PILSVG tile icons in a scrollable single row."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QScrollArea,
    QToolButton,
    QWidget,
)

from ..core.transitions import TILE_DEDUP, TILE_HOTKEY, TILE_LABELS
from .icons import pixmaps

DIGIT_KEYS = 10  # digits 0-9: 0 = empty (last), 1-9 = first nine rail tiles


class TileBar(QWidget):
    """Horizontal, scrollable bar of tile buttons (icon + optional hotkey digit)."""

    tile_chosen = Signal(str, int)  # (name, value)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMaximumHeight(116)
        icons = pixmaps()
        cell = icons["vertical_straight"].width() if icons else 56

        inner = QWidget()
        row = QHBoxLayout(inner)
        row.setContentsMargins(6, 4, 6, 4)
        row.setSpacing(6)

        self._tile_group = QButtonGroup(self)
        self._tile_group.setExclusive(True)
        self._buttons: dict[str, QToolButton] = {}

        for name, value in TILE_DEDUP:
            btn = QToolButton()
            btn.setIcon(QIcon(icons[name]))
            btn.setIconSize(QSize(cell, cell))
            hotkey = TILE_HOTKEY.get(name, "")
            if hotkey:
                btn.setText(hotkey)
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            btn.setCheckable(True)
            key_hint = f" (key {hotkey})" if hotkey else ""
            btn.setToolTip(f"{TILE_LABELS.get(name, name)}{key_hint}")
            btn.clicked.connect(lambda _=False, n=name, v=value: self._choose(n, v))
            self._tile_group.addButton(btn)
            self._buttons[name] = btn
            row.addWidget(btn)
        row.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMaximumHeight(110)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._choose("vertical_straight", 32800)

    def _choose(self, name: str, value: int) -> None:
        btn = self._buttons[name]
        btn.setChecked(True)
        self.tile_chosen.emit(name, value)

    def set_tile(self, name: str) -> None:
        if name in self._buttons:
            self._buttons[name].setChecked(True)
