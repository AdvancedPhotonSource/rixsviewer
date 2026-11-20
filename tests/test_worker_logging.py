# Copyright © UChicago Argonne LLC
# See LICENSE file for details
"""An exception raised inside a Worker must go through logging, traceback
included, so that it reaches the log file and not just the terminal."""

import logging

from rixsviewer.rixsviewer_gui import Worker


def test_worker_exception_logged_with_traceback(qapp, caplog):
    def load_frames():
        raise ValueError("corrupt tiff")

    errors = []
    worker = Worker(load_frames)
    worker.signals.error.connect(errors.append)

    with caplog.at_level(logging.ERROR, logger="rixsviewer"):
        worker.run()

    assert errors == ["corrupt tiff"]
    (record,) = [r for r in caplog.records if r.name == "rixsviewer.rixsviewer_gui"]
    assert "load_frames" in record.getMessage()
    assert record.exc_info[0] is ValueError
