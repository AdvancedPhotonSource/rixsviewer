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
