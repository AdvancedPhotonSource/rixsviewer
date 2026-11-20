# Copyright © UChicago Argonne LLC
# See LICENSE file for details
"""RixsViewerGUI(enable_tooltips=False) -- wired to the CLI's --no-tooltip
flag -- must skip _setup_tooltips() entirely, leaving widgets without the
tooltips they'd otherwise get."""
from rixsviewer.model import user_settings
from rixsviewer.model.binning_model import RixsBinningModel
from rixsviewer.rixsviewer_gui import RixsViewerGUI


def _make_gui(tmp_path, monkeypatch, **kwargs):
    settings_dir = tmp_path / ".rixsviewer"
    monkeypatch.setattr(user_settings, "SETTINGS_DIR", settings_dir)
    monkeypatch.setattr(user_settings, "SETTINGS_FILE", settings_dir / "settings.json")

    original = RixsBinningModel.check_pv_connection
    RixsBinningModel.check_pv_connection = lambda self, timeout=0.5: False
    try:
        return RixsViewerGUI(**kwargs)
    finally:
        RixsBinningModel.check_pv_connection = original


def test_tooltips_enabled_by_default(qapp, tmp_path, monkeypatch):
    gui = _make_gui(tmp_path, monkeypatch)

    assert gui.ui.pushButton_process.toolTip() != ""


def test_enable_tooltips_false_skips_tooltip_setup(qapp, tmp_path, monkeypatch):
    gui = _make_gui(tmp_path, monkeypatch, enable_tooltips=False)

    assert gui.ui.pushButton_process.toolTip() == ""
