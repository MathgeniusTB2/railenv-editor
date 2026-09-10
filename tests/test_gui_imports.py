"""Import smoke tests for the GUI layer (no QApplication display required)."""


def test_main_window_imports():
    from railenv_editor.app.main import MainWindow  # noqa: F401


def test_palette_imports():
    from railenv_editor.editor.palette import Palette  # noqa: F401


def test_inspector_imports():
    from railenv_editor.editor.inspector import InspectorDock  # noqa: F401


def test_canvas_imports():
    from railenv_editor.editor.canvas import RailGraphicsScene, RailView  # noqa: F401
