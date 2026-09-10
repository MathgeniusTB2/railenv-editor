"""Right-hand inspector: shows the selected cell's transition bits."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ..core.grid_model import GridModel
from ..core.transitions import name_for_value


class InspectorDock(QWidget):
    """Details for the currently selected cell."""

    def __init__(self, model: GridModel, parent=None) -> None:
        super().__init__(parent)
        self.model = model
        self.setMinimumWidth(300)

        v = QVBoxLayout(self)
        v.addWidget(QLabel("Selected cell"))
        self._cell_label = QLabel("(none)")
        self._cell_label.setWordWrap(True)
        v.addWidget(self._cell_label)

        self._cell_bits = QLabel("")
        self._cell_bits.setWordWrap(True)
        v.addWidget(self._cell_bits)
        v.addStretch(1)

        self._selected_cell: tuple[int, int] | None = None

    def set_cell(self, cell: tuple[int, int] | None) -> None:
        self._selected_cell = cell
        if cell is None:
            self._cell_label.setText("(none selected)")
            self._cell_bits.setText("")
            return
        x, y = cell
        value = self.model.get(x, y)
        name = name_for_value(value)
        self._cell_label.setText(f"({x}, {y})  ->  {name}")
        if value:
            label = format(value, "016b")
            self._cell_bits.setText(
                f"value {value}\n{label[:4]} {label[4:8]} {label[8:12]} {label[12:16]}\n"
                "(N E S W facing groups)"
            )
        else:
            self._cell_bits.setText(f"value {value} (empty)")
