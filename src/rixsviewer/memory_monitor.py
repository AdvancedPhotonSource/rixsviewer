# Copyright © UChicago Argonne LLC
# See LICENSE file for details
"""Periodic RAM usage records in the log, to tell an out-of-memory kill --
which leaves no traceback -- from other crashes."""

import logging
import sys

from PySide6.QtCore import QTimer

try:
    import psutil
except ImportError:  # an environment set up before psutil became a dependency
    psutil = None

logger = logging.getLogger(__name__)

MEMORY_LOG_INTERVAL_S = 120
_GB = 1024**3


def _peak_rss(mem):
    """Most RAM this process has ever held, in bytes (None if unknown)."""
    if hasattr(mem, "peak_wset"):  # Windows
        return mem.peak_wset
    try:
        import resource
    except ImportError:
        return None
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024  # bytes on macOS, kB elsewhere


def get_memory_usage():
    """Snapshot of the RAM used by this process and by the whole machine.

    Returns
    -------
    dict
        All sizes in bytes.

        ``app_rss``          -- RAM currently held by this process.
        ``app_peak_rss``     -- most RAM this process has held since it
        started; catches spikes that fall between two snapshots.
        ``system_total``     -- installed RAM.
        ``system_available`` -- RAM that can still be handed out without
        swapping (free plus reclaimable cache).
        ``swap_used``, ``swap_total`` -- swap space.
    """
    mem = psutil.Process().memory_info()
    system = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "app_rss": mem.rss,
        # the two counters are kept separately and can disagree by a few MB
        "app_peak_rss": max(_peak_rss(mem) or 0, mem.rss),
        "system_total": system.total,
        "system_available": system.available,
        "swap_used": swap.used,
        "swap_total": swap.total,
    }


def format_memory_usage(usage):
    """One-line, human-readable form of a :func:`get_memory_usage` snapshot."""
    total = usage["system_total"]
    used = total - usage["system_available"]
    return (
        f"Memory: app {usage['app_rss'] / _GB:.2f} GB (peak {usage['app_peak_rss'] / _GB:.2f} GB)"
        f" | system {used / _GB:.1f} of {total / _GB:.1f} GB used ({100 * used / total:.0f}%),"
        f" {usage['system_available'] / _GB:.1f} GB available"
        f" | swap {usage['swap_used'] / _GB:.1f} of {usage['swap_total'] / _GB:.1f} GB used"
    )


def log_memory_usage():
    """Write the current RAM usage of the app and the system to the log."""
    try:
        usage = get_memory_usage()
    except (psutil.Error, OSError) as e:
        logger.warning("Could not read the memory usage: %s", e)
        return
    logger.info(format_memory_usage(usage))


def start_memory_logging(interval_s=MEMORY_LOG_INTERVAL_S, parent=None):
    """Log the RAM usage now, and again every ``interval_s`` seconds.

    Needs a running Qt event loop for the repeats.

    Parameters
    ----------
    interval_s : float
        Seconds between two records.
    parent : QObject, optional
        Owner of the timer; without one, the caller must keep the returned
        timer alive.

    Returns
    -------
    QTimer or None
        The running timer, or None if psutil is not installed.
    """
    if psutil is None:
        logger.warning("psutil is not installed: RAM usage will not be logged (pip install psutil)")
        return None
    timer = QTimer(parent)
    timer.setInterval(int(interval_s * 1000))
    timer.timeout.connect(log_memory_usage)
    timer.start()
    log_memory_usage()
    return timer
