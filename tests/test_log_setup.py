# Copyright © UChicago Argonne LLC
# See LICENSE file for details
"""setup_file_logging() must record each run -- log records, uncaught
exceptions, Qt messages and hard-crash tracebacks -- in its own file under
$HOME/.rixsviewer/logs, without ever keeping the viewer from starting."""

import faulthandler
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest
from PySide6.QtCore import qInstallMessageHandler, qWarning

import rixsviewer
from rixsviewer import log_setup
from rixsviewer.model import user_settings


@pytest.fixture()
def settings_dir(tmp_path, monkeypatch, caplog):
    """Point the settings dir at a throwaway path and undo every process-wide
    change setup_file_logging() makes once the test is over."""
    settings_dir = tmp_path / ".rixsviewer"
    monkeypatch.setattr(user_settings, "SETTINGS_DIR", settings_dir)
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    # pytest owns the real faulthandler; test_segfault_... covers the real thing
    monkeypatch.setattr(faulthandler, "enable", lambda **kwargs: None)
    caplog.set_level(logging.INFO)

    root = logging.getLogger()
    handlers_before = list(root.handlers)
    yield settings_dir
    qInstallMessageHandler(None)
    for handler in root.handlers[:]:
        if handler not in handlers_before:
            root.removeHandler(handler)
            handler.close()
    if log_setup._crash_file is not None:
        log_setup._crash_file.close()
        log_setup._crash_file = None


def _flushed_text(log_file):
    for handler in logging.getLogger().handlers:
        handler.flush()
    return log_file.read_text(encoding="utf-8")


def test_log_file_created_next_to_settings(settings_dir):
    log_file = log_setup.setup_file_logging()

    assert log_file.parent == settings_dir / "logs"
    assert log_file.name.startswith("rixsviewer_") and log_file.suffix == ".log"
    assert str(os.getpid()) in log_file.name


def test_package_records_written_to_log_file(settings_dir):
    log_file = log_setup.setup_file_logging()

    logging.getLogger("rixsviewer.model.utils").info("routine info")
    logging.getLogger("rixsviewer.model.utils").warning("bin size too small")

    text = _flushed_text(log_file)
    assert "routine info" in text
    assert "bin size too small" in text
    assert "rixsviewer.model.utils" in text  # which module said it


def test_log_file_starts_with_version_and_path(settings_dir):
    log_file = log_setup.setup_file_logging()

    text = _flushed_text(log_file)
    assert f"RixsViewer {rixsviewer.__version__} starting" in text
    assert str(log_file) in text


def test_uncaught_exception_traceback_written_to_log_file(settings_dir):
    log_file = log_setup.setup_file_logging()

    try:
        raise ValueError("boom in a slot")
    except ValueError:
        sys.excepthook(*sys.exc_info())

    text = _flushed_text(log_file)
    assert "Uncaught exception: ValueError: boom in a slot" in text
    assert "Traceback (most recent call last)" in text
    assert "test_uncaught_exception_traceback_written_to_log_file" in text


def test_uncaught_thread_exception_written_to_log_file(settings_dir):
    log_file = log_setup.setup_file_logging()

    def explode():
        raise RuntimeError("boom in a thread")

    t = threading.Thread(target=explode, name="exploding-thread")
    t.start()
    t.join()

    text = _flushed_text(log_file)
    assert "Uncaught exception in thread exploding-thread: RuntimeError: boom in a thread" in text
    assert "Traceback (most recent call last)" in text


def test_qt_messages_written_to_log_file(settings_dir):
    log_file = log_setup.setup_file_logging()

    qWarning("QThread: Destroyed while thread is still running")

    text = _flushed_text(log_file)
    assert "WARNING" in text
    assert "QThread: Destroyed while thread is still running" in text


def test_old_log_files_pruned(settings_dir):
    log_dir = settings_dir / "logs"
    log_dir.mkdir(parents=True)
    for i in range(log_setup.MAX_LOG_FILES + 5):
        old = log_dir / f"rixsviewer_old_{i:02d}.log"
        old.write_text("old run")
        os.utime(old, (1_000_000 + i, 1_000_000 + i))  # higher i == newer
    unrelated = log_dir / "notes.txt"
    unrelated.write_text("keep me")

    log_file = log_setup.setup_file_logging()

    remaining = sorted(p.name for p in log_dir.glob("rixsviewer_*.log"))
    assert len(remaining) == log_setup.MAX_LOG_FILES
    assert log_file.name in remaining
    assert "rixsviewer_old_00.log" not in remaining  # oldest went first
    assert f"rixsviewer_old_{log_setup.MAX_LOG_FILES + 4:02d}.log" in remaining
    assert unrelated.read_text() == "keep me"


def test_unwritable_log_dir_does_not_raise(settings_dir, monkeypatch):
    blocker = settings_dir.parent / "not_a_directory"
    blocker.write_text("")
    monkeypatch.setattr(user_settings, "SETTINGS_DIR", blocker / ".rixsviewer")
    handlers_before = list(logging.getLogger().handlers)

    assert log_setup.setup_file_logging() is None
    assert logging.getLogger().handlers == handlers_before


def test_importing_package_creates_no_log_file(settings_dir):
    # only main() may start a log file; see the comment there
    assert not (settings_dir / "logs").exists()


def test_segfault_traceback_written_to_log_file(tmp_path):
    """End to end, in a child process that really dies of a segfault."""
    script = (
        "import faulthandler\n"
        "from rixsviewer.log_setup import setup_file_logging\n"
        "setup_file_logging()\n"
        "def crash_here():\n"
        "    faulthandler._sigsegv()\n"
        "crash_here()\n"
    )
    env = dict(os.environ, HOME=str(tmp_path), USERPROFILE=str(tmp_path))
    src_dir = str(Path(rixsviewer.__file__).parents[1])
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [src_dir, env.get("PYTHONPATH")]))

    result = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True, timeout=120)

    assert result.returncode != 0
    log_files = list((tmp_path / ".rixsviewer" / "logs").glob("rixsviewer_*.log"))
    assert len(log_files) == 1, result.stderr
    text = log_files[0].read_text(encoding="utf-8")
    assert "Segmentation fault" in text
    assert "crash_here" in text
    assert "exited normally" not in text
