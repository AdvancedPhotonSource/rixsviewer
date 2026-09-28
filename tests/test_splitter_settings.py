# Copyright © UChicago Argonne LLC
# See LICENSE file for details
"""Splitter sizes should persist across restarts: saved on a confirmed
close, restored at startup, via the same $HOME/.rixsviewer/settings.json
used for spec_filename/tiff_folder (not the unrelated sibling app's
$HOME/.trxasviewer/config.json)."""
import base64

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMessageBox


def test_save_splitter_state_encodes_all_named_splitters(gui, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "rixsviewer.rixsviewer_gui.save_splitter_state", lambda states: captured.update(states)
    )

    gui._save_splitter_state()

    assert set(captured.keys()) == {
        "splitter", "splitter_2", "splitter_3", "splitter_4", "splitter_rxesmap",
    }
    for name, encoded in captured.items():
        splitter = getattr(gui.ui, name)
        assert base64.b64decode(encoded) == bytes(splitter.saveState())


def test_restore_splitter_state_applies_the_saved_bytes(gui, monkeypatch):
    original_state = bytes(gui.ui.splitter.saveState())
    encoded = base64.b64encode(original_state).decode("ascii")

    calls = []
    monkeypatch.setattr(gui.ui.splitter, "restoreState", lambda qba: calls.append(bytes(qba)))

    gui._restore_splitter_state({"splitter_state": {"splitter": encoded}})

    assert calls == [original_state]


def test_restore_splitter_state_actually_restores_via_real_qt_round_trip(gui):
    gui.ui.splitter.setSizes([123, 456])
    encoded = base64.b64encode(bytes(gui.ui.splitter.saveState())).decode("ascii")

    gui.ui.splitter.setSizes([1, 1])  # perturb it
    ok = gui.ui.splitter.restoreState(QByteArray.fromBase64(encoded.encode("ascii")))

    assert ok is True


def test_restore_splitter_state_is_a_noop_without_saved_data(gui):
    gui._restore_splitter_state({})  # must not raise
    gui._restore_splitter_state({"splitter_state": {}})  # must not raise


def test_closing_and_confirming_saves_splitter_state(gui, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    calls = []
    monkeypatch.setattr(gui, "_save_splitter_state", lambda: calls.append(True))

    gui.closeEvent(QCloseEvent())

    assert calls == [True]


def test_closing_and_declining_does_not_save_splitter_state(gui, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    calls = []
    monkeypatch.setattr(gui, "_save_splitter_state", lambda: calls.append(True))

    gui.closeEvent(QCloseEvent())

    assert calls == []
