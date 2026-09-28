# Copyright © UChicago Argonne LLC
# See LICENSE file for details
"""process_binning's on_result must route a 2D RXES map result away from
the 1D plot call (which expects 1D energy_axis/intensity_norm arrays and
would break on 2D-shaped ones), instead of crashing."""
import numpy as np


def test_rxes_map_result_does_not_call_plot_binned_data(gui, monkeypatch):
    called = []
    monkeypatch.setattr(gui.view, "plot_binned_data", lambda *a, **k: called.append(True))

    gui.beamline.run_rxes_scan(1, n_emission=2, n_incident=2)
    gui.update_spec_record()  # populates gui.current_rixs_dset via the stubbed process_binning
    dset = gui.current_rixs_dset
    result = dset.bin_data_wrap(metadata_source="SpecFile")

    # exercise the real routing method directly, bypassing the fixture's
    # no-op process_binning stub (which exists to isolate other tests
    # from the QThreadPool worker)
    gui._route_binning_result(result, show_rawdata=False, plot_target="intensity_norm")

    assert called == []


def test_spectrum_result_still_calls_plot_binned_data(gui, monkeypatch):
    called = []
    monkeypatch.setattr(gui.view, "plot_binned_data", lambda *a, **k: called.append(True))

    spectrum_result = {"energy_axis": np.array([1.0, 2.0]), "intensity_norm": np.array([0.1, 0.2])}
    gui._route_binning_result(spectrum_result, show_rawdata=False, plot_target="intensity_norm")

    assert called == [True]


def test_rxes_map_result_calls_plot_rxes_map_with_the_rxes_specific_combo_target(gui, monkeypatch):
    """The `plot_target` argument passed into `_route_binning_result` comes
    from the 1D-plot combo box (`comboBox_plottarget`) and doesn't apply to
    an RXES map -- the RXES-specific combo box (`comboBox_rxes_plottarget`)
    must be consulted instead."""
    called = []
    monkeypatch.setattr(
        gui.view, "plot_rxes_map", lambda result, plot_target: called.append((result, plot_target))
    )

    # Set before the dataset has a cached bin_result, so this doesn't itself
    # trigger a (guarded no-op) replot via on_rxes_plottarget_changed.
    gui.ui.comboBox_rxes_plottarget.setCurrentText("sample")

    gui.beamline.run_rxes_scan(1, n_emission=2, n_incident=2)
    gui.update_spec_record()
    dset = gui.current_rixs_dset
    result = dset.bin_data_wrap(metadata_source="SpecFile")

    gui._route_binning_result(result, show_rawdata=False, plot_target="intensity_norm")

    assert len(called) == 1
    got_result, got_target = called[0]
    assert got_result is result
    assert got_target == "sample"


def test_rxes_map_result_switches_focus_to_the_rxes_map_tab(gui):
    gui.beamline.run_rxes_scan(1, n_emission=2, n_incident=2)
    gui.update_spec_record()
    dset = gui.current_rixs_dset
    result = dset.bin_data_wrap(metadata_source="SpecFile")

    gui.ui.tabWidget.setCurrentWidget(gui.ui.tab_2)  # start on the Process tab
    gui._route_binning_result(result, show_rawdata=False, plot_target="intensity_norm")

    assert gui.ui.tabWidget.currentWidget() is gui.ui.tab_rxesmap
