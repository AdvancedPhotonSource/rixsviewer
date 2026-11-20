# Copyright © UChicago Argonne LLC
# See LICENSE file for details
"""Regression tests for a crash found in code review: RixsViewerGUI's
process_binning/_evict_scan_data touch dset._data unconditionally, but
RixsRxesScanDataset never had that attribute -- crashing on essentially
every RXES scan start in auto-update mode (process_binning), and on
eviction whenever the GUI switches away from an RXES scan
(_evict_scan_data).
"""


def test_process_binning_survives_rxes_header_with_no_frames_yet(gui):
    del gui.process_binning  # exercise the real method, not the fixture's isolation stub
    gui.ui.checkBox_autoupdate.setChecked(True)

    gui.beamline.start_rxes_scan(1, n_emission=2, n_incident=2)  # header only, no data rows/TIFFs yet
    gui.update_spec_record()  # must not raise AttributeError


def test_evicting_an_rxes_dataset_when_a_new_scan_arrives_does_not_crash(gui):
    gui.beamline.run_rxes_scan(1, n_emission=2, n_incident=2)
    gui.update_spec_record()
    assert gui.current_rixs_dset is not None

    gui.beamline.run_scan(2)
    gui.update_spec_record()  # evicts scan 1 (RXES) -> must not raise AttributeError


def test_switching_from_rxes_to_a_plain_scan_disables_and_clears_the_rxes_map_tab(gui):
    """Regression test: selecting a non-RXES scan right after an RXES scan
    used to leave the previous RXES map on screen -- the tab should
    instead be disabled, cleared, and focus moved back to Process."""
    gui.beamline.run_rxes_scan(1, n_emission=2, n_incident=2)
    gui.update_spec_record()
    result = gui.current_rixs_dset.bin_data_wrap(metadata_source="SpecFile")
    gui._route_binning_result(result, show_rawdata=False, plot_target="intensity_norm")

    idx = gui.ui.tabWidget.indexOf(gui.ui.tab_rxesmap)
    assert gui.ui.tabWidget.isTabEnabled(idx) is True
    assert gui.ui.tabWidget.currentWidget() is gui.ui.tab_rxesmap
    assert gui.view.rxes_img_hdl.image is not None

    gui.beamline.run_scan(2)
    gui.update_spec_record()

    assert gui.ui.tabWidget.isTabEnabled(idx) is False
    assert gui.ui.tabWidget.currentWidget() is gui.ui.tab_2
    assert gui.view.rxes_img_hdl.image is None


def test_switching_back_to_an_rxes_scan_reenables_the_rxes_map_tab(gui):
    gui.beamline.run_scan(1)
    gui.update_spec_record()
    idx = gui.ui.tabWidget.indexOf(gui.ui.tab_rxesmap)
    assert gui.ui.tabWidget.isTabEnabled(idx) is False

    gui.beamline.run_rxes_scan(2, n_emission=2, n_incident=2)
    gui.update_spec_record()

    assert gui.ui.tabWidget.isTabEnabled(idx) is True


def test_calibrate_parameters_consults_supports_calibration_predicate(gui, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.append(True))

    gui.beamline.run_rxes_scan(1, n_emission=2, n_incident=2)
    gui.update_spec_record()
    dset = gui.current_rixs_dset

    calls = []
    original = dset.supports_calibration
    def spy():
        calls.append(True)
        return original()
    monkeypatch.setattr(dset, "supports_calibration", spy)

    gui.calibrate_parameters()

    assert calls == [True]  # the gate actually consulted the predicate
    assert warned == [True]  # ...and correctly denied calibration for RXES


# ---------------------------------------------------------------------------
# RXES Map tab's own "Force NEnergyBins" pair
# ---------------------------------------------------------------------------


def test_rxes_force_nenergybins_is_checked_by_default(gui):
    assert gui.ui.checkBox_overwrite_rxes_binning_points.isChecked() is True
    assert gui.ui.spinBox_force_rxes_binning_points.isEnabled() is True


def test_toggling_rxes_force_checkbox_toggles_spinbox_enabled(gui):
    gui.ui.checkBox_overwrite_rxes_binning_points.setChecked(False)
    assert gui.ui.spinBox_force_rxes_binning_points.isEnabled() is False

    gui.ui.checkBox_overwrite_rxes_binning_points.setChecked(True)
    assert gui.ui.spinBox_force_rxes_binning_points.isEnabled() is True


def test_selecting_a_new_rxes_scan_sets_spinbox_to_its_emission_points(gui):
    gui.beamline.run_rxes_scan(1, n_emission=7, n_incident=3)
    gui.beamline.run_scan(2)
    gui.update_spec_record()

    gui.ui.tableView_scan.selectRow(0)

    assert gui.ui.spinBox_force_rxes_binning_points.value() == 7


def test_reselecting_the_same_rxes_scan_does_not_reset_a_manually_changed_spinbox(gui):
    gui.beamline.run_rxes_scan(1, n_emission=7, n_incident=3)
    gui.update_spec_record()
    gui.ui.tableView_scan.selectRow(0)

    gui.ui.spinBox_force_rxes_binning_points.setValue(500)
    gui.ui.tableView_scan.selectRow(0)  # re-select the same, already-current row

    assert gui.ui.spinBox_force_rxes_binning_points.value() == 500


def test_resolve_nenergybins_override_uses_rxes_controls_for_an_rxes_scan(gui):
    gui.beamline.run_rxes_scan(1, n_emission=7, n_incident=3)
    gui.update_spec_record()
    gui.ui.tableView_scan.selectRow(0)
    gui.ui.checkBox_overwrite_rxes_binning_points.setChecked(True)
    gui.ui.spinBox_force_rxes_binning_points.setValue(42)

    assert gui._resolve_nenergybins_override() == {"NEnergyBins": 42, "force_NEnergyBins": True}

    gui.ui.checkBox_overwrite_rxes_binning_points.setChecked(False)
    assert gui._resolve_nenergybins_override() == {"force_NEnergyBins": False}


def test_resolve_nenergybins_override_uses_process_tab_controls_for_a_plain_scan(gui):
    gui.beamline.run_scan(1)
    gui.update_spec_record()
    gui.ui.tableView_scan.selectRow(0)

    assert gui.ui.checkBox_overwrite_binning_points.isChecked() is False
    assert gui._resolve_nenergybins_override() == {"force_NEnergyBins": False}

    gui.ui.checkBox_overwrite_binning_points.setChecked(True)
    gui.ui.spinBox_force_binning_points.setValue(99)
    assert gui._resolve_nenergybins_override() == {"NEnergyBins": 99, "force_NEnergyBins": True}


def test_pressing_enter_in_rxes_binning_spinbox_reprocesses(gui, monkeypatch):
    gui.beamline.run_rxes_scan(1, n_emission=7, n_incident=3)
    gui.update_spec_record()
    gui.ui.tableView_scan.selectRow(0)

    calls = []
    monkeypatch.setattr(gui, "process_binning", lambda: calls.append(True))

    gui.ui.spinBox_force_rxes_binning_points.setValue(50)
    gui.ui.spinBox_force_rxes_binning_points.editingFinished.emit()

    assert calls == [True]


def test_toggling_rxes_force_checkbox_reprocesses(gui, monkeypatch):
    gui.beamline.run_rxes_scan(1, n_emission=7, n_incident=3)
    gui.update_spec_record()
    gui.ui.tableView_scan.selectRow(0)

    calls = []
    monkeypatch.setattr(gui, "process_binning", lambda: calls.append(True))

    gui.ui.checkBox_overwrite_rxes_binning_points.setChecked(False)

    assert calls == [True]


def test_editing_rxes_binning_spinbox_is_a_noop_for_a_non_rxes_scan(gui, monkeypatch):
    gui.beamline.run_scan(1)
    gui.update_spec_record()
    gui.ui.tableView_scan.selectRow(0)

    calls = []
    monkeypatch.setattr(gui, "process_binning", lambda: calls.append(True))

    # the RXES tab's own spinbox, not the Process tab's -- must not reprocess
    # a plain scan even if this signal somehow fires
    gui.ui.spinBox_force_rxes_binning_points.editingFinished.emit()

    assert calls == []


# ---------------------------------------------------------------------------
# Crosshair checkbox + click-to-navigate wiring
# ---------------------------------------------------------------------------


def test_show_crosshair_checked_by_default(gui):
    assert gui.ui.checkBox_show_crosshair.isChecked() is True


def test_toggling_show_crosshair_calls_set_rxes_crosshair_visible(gui, monkeypatch):
    calls = []
    monkeypatch.setattr(gui.view, "set_rxes_crosshair_visible", lambda v: calls.append(v))

    gui.ui.checkBox_show_crosshair.setChecked(False)

    assert calls == [False]


def test_rxes_map_click_callback_sets_the_frame_slider(gui):
    gui.beamline.run_rxes_scan(1, n_emission=3, n_incident=3)
    gui.update_spec_record()
    gui.ui.tableView_scan.selectRow(0)
    gui.ui.horizontalSlider_frame_index.setRange(0, 20)

    gui._on_rxes_map_frame_clicked(4)

    assert gui.ui.horizontalSlider_frame_index.value() == 4
