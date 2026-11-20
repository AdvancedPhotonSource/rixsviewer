# Copyright © UChicago Argonne LLC
# See LICENSE file for details
"""Every way of exporting data must open its file dialog in the folder of
the SPEC file that is currently loaded -- both the "Export" buttons and the
"Export..." entry in the plots' right-click menu (which is pyqtgraph's own
dialog, and would otherwise open in the directory RixsViewer was launched
from).
"""

import importlib
import os

from PySide6.QtWidgets import QFileDialog

from rixsviewer import rixsviewer_gui

from conftest import FakeBeamline


def _plot_export_folder():
    # ``pyqtgraph.exporters.Exporter`` as an attribute is the class; the
    # folder pyqtgraph's export dialog opens in lives on the module.
    return importlib.import_module("pyqtgraph.exporters.Exporter").LastExportDirectory


class _RecordingDialog:
    """Stands in for QFileDialog: records the start path and 'cancels'."""

    AcceptMode = QFileDialog.AcceptMode
    Option = QFileDialog.Option
    start_paths = []

    def __init__(self, parent, caption, directory, name_filter):
        self.start_paths.append(directory)

    def setAcceptMode(self, mode):
        pass

    def setOption(self, option, on=True):
        pass

    def exec(self):
        return 0


class _BinnedDataset:
    bin_result = {"energy_axis": [0.0]}


class TestExportStartFolder:
    def test_export_button_opens_next_to_the_spec_file(self, gui, monkeypatch):
        _RecordingDialog.start_paths = []
        monkeypatch.setattr(rixsviewer_gui, "QFileDialog", _RecordingDialog)
        gui.current_rixs_dset = _BinnedDataset()

        gui.save_bin_results()

        spec_folder = os.path.dirname(gui.beamline.spec)
        assert _RecordingDialog.start_paths == [
            os.path.join(spec_folder, "fake_bindata_rixsviewer.spec")
        ]

    def test_plot_right_click_export_opens_in_the_spec_folder(self, gui):
        assert _plot_export_folder() == os.path.dirname(gui.beamline.spec)

    def test_plot_right_click_export_follows_a_newly_loaded_spec_file(self, gui, tmp_path):
        other_folder = tmp_path / "another_experiment"
        other_folder.mkdir()
        other = FakeBeamline(str(other_folder))

        gui.spec_filename = other.spec
        gui.tiff_folder = other.workdir
        gui.setup_scan_table()

        assert _plot_export_folder() == str(other_folder)
