# Copyright © UChicago Argonne LLC
# See LICENSE file for details
"""Window size/position should persist across restarts: saved on a confirmed
close, restored at startup, via the same $HOME/.rixsviewer/settings.json
used for spec_filename/tiff_folder/splitter_state."""
import base64

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMessageBox


def test_save_window_geometry_encodes_saveGeometry(gui, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "rixsviewer.rixsviewer_gui.save_window_geometry", lambda encoded: captured.update(value=encoded)
    )

    gui._save_window_geometry()

    assert base64.b64decode(captured["value"]) == bytes(gui.saveGeometry())


def test_restore_window_geometry_applies_the_saved_bytes(gui, monkeypatch):
    original_geometry = bytes(gui.saveGeometry())
    encoded = base64.b64encode(original_geometry).decode("ascii")

    calls = []
    monkeypatch.setattr(gui, "restoreGeometry", lambda qba: calls.append(bytes(qba)))

    gui._restore_window_geometry({"window_geometry": encoded})

    assert calls == [original_geometry]


def test_restore_window_geometry_actually_restores_via_real_qt_round_trip(gui):
    gui.resize(654, 321)
    encoded = base64.b64encode(bytes(gui.saveGeometry())).decode("ascii")

    gui.resize(100, 100)  # perturb it
    ok = gui.restoreGeometry(QByteArray.fromBase64(encoded.encode("ascii")))

    assert ok is True


def test_restore_window_geometry_is_a_noop_without_saved_data(gui):
    gui._restore_window_geometry({})  # must not raise
    gui._restore_window_geometry({"window_geometry": None})  # must not raise


def test_closing_and_confirming_saves_window_geometry(gui, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    calls = []
    monkeypatch.setattr(gui, "_save_window_geometry", lambda: calls.append(True))

    gui.closeEvent(QCloseEvent())

    assert calls == [True]


def test_closing_and_declining_does_not_save_window_geometry(gui, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    calls = []
    monkeypatch.setattr(gui, "_save_window_geometry", lambda: calls.append(True))

    gui.closeEvent(QCloseEvent())

    assert calls == []
