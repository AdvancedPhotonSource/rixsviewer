# Copyright © UChicago Argonne LLC
# See LICENSE file for details
"""WARNING-and-above records from any ``rixsviewer.*`` logger -- including
ones emitted from worker threads -- must also appear on the GUI status bar,
not just the console."""
import logging
import threading

from PySide6.QtWidgets import QApplication

from rixsviewer.model import user_settings
from rixsviewer.model.binning_model import RixsBinningModel
from rixsviewer.rixsviewer_gui import RixsViewerGUI


def _make_gui(tmp_path, monkeypatch):
    settings_dir = tmp_path / ".rixsviewer"
    monkeypatch.setattr(user_settings, "SETTINGS_DIR", settings_dir)
    monkeypatch.setattr(user_settings, "SETTINGS_FILE", settings_dir / "settings.json")
    monkeypatch.setattr(RixsBinningModel, "check_pv_connection", lambda self, timeout=0.5: False)
    return RixsViewerGUI(enable_tooltips=False)


def test_model_warning_shown_on_statusbar(qapp, tmp_path, monkeypatch):
    gui = _make_gui(tmp_path, monkeypatch)

    logging.getLogger("rixsviewer.model.utils").warning("bin size too small; falling back")
    QApplication.processEvents()

    assert gui.statusBar().currentMessage() == "WARNING: bin size too small; falling back"


def test_warning_from_worker_thread_shown_on_statusbar(qapp, tmp_path, monkeypatch):
    gui = _make_gui(tmp_path, monkeypatch)

    t = threading.Thread(target=lambda: logging.getLogger("rixsviewer.model.utils").warning("from worker"))
    t.start()
    t.join()
    QApplication.processEvents()

    assert gui.statusBar().currentMessage() == "WARNING: from worker"


def test_info_not_shown_on_statusbar(qapp, tmp_path, monkeypatch):
    gui = _make_gui(tmp_path, monkeypatch)
    gui.statusBar().clearMessage()

    logging.getLogger("rixsviewer.model.utils").info("routine info")
    QApplication.processEvents()

    assert gui.statusBar().currentMessage() == ""


def test_handler_detached_on_close(qapp, tmp_path, monkeypatch):
    gui = _make_gui(tmp_path, monkeypatch)
    pkg_logger = logging.getLogger("rixsviewer")
    assert gui._statusbar_log_handler in pkg_logger.handlers

    gui._detach_statusbar_log_handler()

    assert gui._statusbar_log_handler not in pkg_logger.handlers
