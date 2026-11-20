# Copyright © UChicago Argonne LLC
# See LICENSE file for details
"""Per-run log file under ``$HOME/.rixsviewer/logs``, including crash reports.

Every launch gets its own file, so several viewers sharing one (NFS) home
directory never write to -- or rotate -- the same file.  Besides the normal
log records, the file also receives what would otherwise only reach the
terminal (or nothing at all in a windowed build):

- uncaught Python exceptions, from the GUI thread, Qt slots and Python threads;
- Qt's own messages (warnings, and the fatal message printed before an abort);
- the Python traceback of every thread on a hard crash (segfault, abort, ...).
"""

import atexit
import faulthandler
import logging
import os
import platform
import re
import sys
import threading
import time

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import QtMsgType, qInstallMessageHandler, qVersion

from . import __version__
from .model import user_settings

logger = logging.getLogger(__name__)
# Deliberately outside the "rixsviewer" namespace: Qt's messages belong in the
# log file, not on the status bar that mirrors rixsviewer.* warnings.
qt_logger = logging.getLogger("qt")

LOG_FILE_FORMAT = "%(asctime)s %(levelname)-8s [%(threadName)s] %(name)s:%(lineno)d - %(message)s"
LOG_FILE_PREFIX = "rixsviewer_"
MAX_LOG_FILES = 20

_QT_LOG_LEVELS = {
    QtMsgType.QtDebugMsg: logging.DEBUG,
    QtMsgType.QtInfoMsg: logging.INFO,
    QtMsgType.QtWarningMsg: logging.WARNING,
    QtMsgType.QtCriticalMsg: logging.ERROR,
    QtMsgType.QtFatalMsg: logging.CRITICAL,
}

# faulthandler writes to this file descriptor from a signal handler, so it has
# to stay open for the life of the process -- hence a handle of its own rather
# than the logging handler's stream, which logging closes at interpreter exit
# (i.e. before a crash during Qt teardown).
_crash_file = None


def get_log_dir():
    """Directory holding the per-run log files (next to ``settings.json``)."""
    return user_settings.SETTINGS_DIR / "logs"


def _log_file_name():
    host = re.sub(r"[^A-Za-z0-9-]", "-", platform.node().split(".")[0]) or "host"
    return f"{LOG_FILE_PREFIX}{time.strftime('%Y%m%d_%H%M%S')}_{host}_{os.getpid()}.log"


def _mtime(path):
    try:
        return path.stat().st_mtime
    except OSError:  # removed by another instance in the meantime
        return 0.0


def _prune_old_logs(log_dir, keep):
    """Delete all but the ``keep`` most recently written log files."""
    logs = sorted(log_dir.glob(f"{LOG_FILE_PREFIX}*.log"), key=_mtime, reverse=True)
    for stale in logs[keep:]:
        try:
            stale.unlink()
        except OSError:
            pass


def _log_uncaught_exception(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    logger.critical("Uncaught exception: %s: %s", exc_type.__name__, exc_value, exc_info=(exc_type, exc_value, exc_tb))


def _log_uncaught_thread_exception(args):
    if issubclass(args.exc_type, SystemExit):
        return
    logger.critical(
        "Uncaught exception in thread %s: %s: %s",
        args.thread.name if args.thread is not None else "?",
        args.exc_type.__name__,
        args.exc_value,
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
    )


def _qt_message_handler(mode, context, message):
    qt_logger.log(_QT_LOG_LEVELS.get(mode, logging.INFO), "%s", message)


def _install_crash_hooks(log_file):
    global _crash_file

    sys.excepthook = _log_uncaught_exception
    threading.excepthook = _log_uncaught_thread_exception

    qInstallMessageHandler(_qt_message_handler)
    # Hand Qt's messages back to Qt before the interpreter is torn down.
    atexit.register(qInstallMessageHandler, None)

    _crash_file = open(log_file, "a", encoding="utf-8")
    faulthandler.enable(file=_crash_file, all_threads=True)


def setup_file_logging(level=logging.INFO):
    """Start logging this run to a new file under ``$HOME/.rixsviewer/logs``.

    Call once, from the application entry point.  Failing to create the file
    (read-only or full home directory, ...) is reported and otherwise ignored:
    the viewer must still start.

    Parameters
    ----------
    level : int
        Lowest level written to the file.

    Returns
    -------
    pathlib.Path or None
        The log file, or None if it could not be created.
    """
    log_dir = get_log_dir()
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        _prune_old_logs(log_dir, keep=MAX_LOG_FILES - 1)
        log_file = log_dir / _log_file_name()
        handler = logging.FileHandler(log_file, encoding="utf-8")
    except OSError as e:
        logger.warning("Not logging to a file: could not create one in %s: %s", log_dir, e)
        return None

    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(LOG_FILE_FORMAT))
    logging.getLogger().addHandler(handler)

    try:
        _install_crash_hooks(log_file)
    except (OSError, RuntimeError) as e:
        logger.warning("Crash reports will not reach the log file: %s", e)

    logger.info(
        "RixsViewer %s starting (pid %d on %s; Python %s, PySide6 %s, Qt %s, %s)",
        __version__,
        os.getpid(),
        platform.node(),
        platform.python_version(),
        pyside_version,
        qVersion(),
        platform.platform(),
    )
    logger.info("Command line: %s", " ".join(sys.argv))
    logger.info("Logging to %s", log_file)
    return log_file
