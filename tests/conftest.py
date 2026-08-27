# Copyright © UChicago Argonne LLC
# See LICENSE file for details
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# same suppression used in rixsviewer_gui.main()
os.environ.setdefault("QT_LOGGING_RULES", "qt.core.qobject.connect=false")

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
