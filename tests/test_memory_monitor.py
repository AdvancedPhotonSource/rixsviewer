# Copyright © UChicago Argonne LLC
# See LICENSE file for details
"""The RAM usage of the app and of the system must be written to the log at
startup and then every two minutes, so that a log file which just stops can
be told apart as an out-of-memory kill."""

import logging

import numpy as np
from PySide6.QtTest import QTest

from rixsviewer import memory_monitor

MB = 1024**2
GB = 1024**3


def _memory_records(caplog):
    return [r for r in caplog.records if r.name == "rixsviewer.memory_monitor"]


def test_snapshot_covers_app_and_system():
    usage = memory_monitor.get_memory_usage()

    assert 0 < usage["app_rss"] <= usage["app_peak_rss"]
    assert usage["app_rss"] < usage["system_total"]
    assert 0 < usage["system_available"] <= usage["system_total"]
    assert 0 <= usage["swap_used"] <= usage["swap_total"]


def test_app_memory_follows_allocations():
    before = memory_monitor.get_memory_usage()

    block = np.ones(200 * MB, dtype=np.uint8)  # ones(), so the pages really are touched
    during = memory_monitor.get_memory_usage()
    del block

    assert during["app_rss"] - before["app_rss"] > 150 * MB
    # the peak outlives the allocation
    assert memory_monitor.get_memory_usage()["app_peak_rss"] >= during["app_rss"] - 10 * MB


def test_format_is_one_readable_line():
    usage = {
        "app_rss": int(1.5 * GB),
        "app_peak_rss": 4 * GB,
        "system_total": 64 * GB,
        "system_available": 48 * GB,
        "swap_used": 0,
        "swap_total": 8 * GB,
    }

    assert memory_monitor.format_memory_usage(usage) == (
        "Memory: app 1.50 GB (peak 4.00 GB)"
        " | system 16.0 of 64.0 GB used (25%), 48.0 GB available"
        " | swap 0.0 of 8.0 GB used"
    )


def test_log_memory_usage_writes_one_info_record(caplog):
    with caplog.at_level(logging.INFO, logger="rixsviewer"):
        memory_monitor.log_memory_usage()

    (record,) = _memory_records(caplog)
    assert record.levelno == logging.INFO
    assert record.getMessage().startswith("Memory: app ")


def test_unreadable_memory_usage_does_not_raise(caplog, monkeypatch):
    def fail():
        raise OSError("/proc not mounted")

    monkeypatch.setattr(memory_monitor, "get_memory_usage", fail)

    with caplog.at_level(logging.INFO, logger="rixsviewer"):
        memory_monitor.log_memory_usage()

    (record,) = _memory_records(caplog)
    assert record.levelno == logging.WARNING
    assert "/proc not mounted" in record.getMessage()


def test_logs_at_start_and_then_periodically(qapp, caplog):
    with caplog.at_level(logging.INFO, logger="rixsviewer"):
        timer = memory_monitor.start_memory_logging(interval_s=0.05)
        assert len(_memory_records(caplog)) == 1  # right away, not after the first interval
        QTest.qWait(400)
        timer.stop()

    assert len(_memory_records(caplog)) >= 3


def test_default_interval_is_two_minutes(qapp):
    timer = memory_monitor.start_memory_logging()
    try:
        assert timer.interval() == 120_000
        assert timer.isActive()
    finally:
        timer.stop()


def test_missing_psutil_is_reported_not_fatal(qapp, caplog, monkeypatch):
    monkeypatch.setattr(memory_monitor, "psutil", None)

    with caplog.at_level(logging.INFO, logger="rixsviewer"):
        timer = memory_monitor.start_memory_logging()

    assert timer is None
    (record,) = _memory_records(caplog)
    assert record.levelno == logging.WARNING
    assert "psutil" in record.getMessage()
