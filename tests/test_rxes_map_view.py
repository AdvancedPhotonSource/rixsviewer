# Copyright © UChicago Argonne LLC
# See LICENSE file for details
"""Tests for the "RXES Map" tab: its position in the tab bar, RixsView's
2D-map plotting, and switching the RXES-specific display-target combo box.

Switching between intensity / intensity_norm / sample is a pure replot of
already-computed arrays -- it must not re-run bin_data_wrap.
"""
import numpy as np
import pytest


def _synthetic_rxes_result(
    n_emission=3, n_incident=2, emission_range=(11.190, 11.200), incident_range=(12.650, 12.660)
):
    emission_axis = np.linspace(*emission_range, n_emission)
    incident_axis = np.linspace(*incident_range, n_incident)
    intensity = np.arange(n_emission * n_incident, dtype=float).reshape(n_emission, n_incident)
    sample = np.ones((n_emission, n_incident))
    with np.errstate(invalid="ignore"):
        intensity_norm = intensity / np.clip(sample, 1, None)
    return {
        "kind": "rxes_map",
        "emission_axis": emission_axis,
        "incident_axis": incident_axis,
        "intensity": intensity,
        "sample": sample,
        "intensity_norm": intensity_norm,
    }


def test_rxes_map_and_profile_plots_show_all_four_borders(gui):
    for plot in (gui.view._rxes_plot, gui.view._rxes_profile_plot):
        for side in ("top", "right", "left", "bottom"):
            assert plot.getAxis(side).isVisible(), f"{side} axis not shown"


def test_rxes_map_tab_sits_between_process_and_calibration(gui):
    tabs = gui.ui.tabWidget
    assert tabs.indexOf(gui.ui.tab_rxesmap) == tabs.indexOf(gui.ui.tab_2) + 1
    assert tabs.indexOf(gui.ui.tab_rxesmap) < tabs.indexOf(gui.ui.tab)


def test_rxes_plottarget_combo_offers_the_three_map_arrays(gui):
    combo = gui.ui.comboBox_rxes_plottarget
    items = [combo.itemText(i) for i in range(combo.count())]
    assert items == ["intensity_norm", "intensity", "sample"]


def test_plot_rxes_map_displays_the_selected_array(gui):
    result = _synthetic_rxes_result()

    gui.view.plot_rxes_map(result, plot_target="sample")

    np.testing.assert_array_equal(gui.view.rxes_img_hdl.image, result["sample"])


def test_plot_rxes_map_does_not_show_a_title_on_the_2d_plot(gui):
    result = _synthetic_rxes_result()

    gui.view.plot_rxes_map(result, plot_target="intensity_norm")

    assert gui.view._rxes_plot.titleLabel.isVisible() is False


def test_plot_rxes_map_resets_view_range_for_a_new_scans_axis_bounds(gui):
    result1 = _synthetic_rxes_result(incident_range=(12.650, 12.660), emission_range=(11.190, 11.200))
    gui.view.plot_rxes_map(result1, plot_target="intensity_norm")

    # simulate the user having zoomed into a small sub-region of scan 1's map
    gui.view._rxes_plot.getViewBox().setRange(xRange=(12.652, 12.654), yRange=(11.191, 11.193), padding=0)

    result2 = _synthetic_rxes_result(incident_range=(13.000, 13.010), emission_range=(11.300, 11.310))
    gui.view.plot_rxes_map(result2, plot_target="intensity_norm")

    (xmin, xmax), (ymin, ymax) = gui.view._rxes_plot.getViewBox().viewRange()
    assert (xmin, xmax) == pytest.approx((13.000, 13.010))
    assert (ymin, ymax) == pytest.approx((11.300, 11.310))


def test_plot_rxes_map_keeps_zoom_across_a_live_update_of_the_same_scan(gui):
    result1 = _synthetic_rxes_result(incident_range=(12.650, 12.660), emission_range=(11.190, 11.200))
    gui.view.plot_rxes_map(result1, plot_target="intensity_norm")

    zoom_x, zoom_y = (12.652, 12.654), (11.191, 11.193)
    gui.view._rxes_plot.getViewBox().setRange(xRange=zoom_x, yRange=zoom_y, padding=0)

    # same scan polled again (unchanged axis bounds) -- e.g. more frames accumulated
    result1_again = _synthetic_rxes_result(incident_range=(12.650, 12.660), emission_range=(11.190, 11.200))
    gui.view.plot_rxes_map(result1_again, plot_target="intensity_norm")

    (xmin, xmax), (ymin, ymax) = gui.view._rxes_plot.getViewBox().viewRange()
    assert (xmin, xmax) == pytest.approx(zoom_x)
    assert (ymin, ymax) == pytest.approx(zoom_y)


def test_switching_rxes_plottarget_replots_the_cached_result_without_recomputing(gui, monkeypatch):
    result = _synthetic_rxes_result()
    gui.beamline.run_rxes_scan(1, n_emission=2, n_incident=2)
    gui.update_spec_record()
    gui.current_rixs_dset.bin_result = result

    recomputed = []
    monkeypatch.setattr(gui.current_rixs_dset, "bin_data_wrap", lambda *a, **k: recomputed.append(True))

    gui.ui.comboBox_rxes_plottarget.setCurrentText("sample")

    np.testing.assert_array_equal(gui.view.rxes_img_hdl.image, result["sample"])
    assert recomputed == []


def test_switching_rxes_plottarget_is_a_noop_without_a_cached_rxes_result(gui):
    # A plain EnergyScan dataset has no rxes_map bin_result -- must not raise.
    gui.beamline.run_scan(1)
    gui.update_spec_record()

    gui.ui.comboBox_rxes_plottarget.setCurrentText("sample")


# ---------------------------------------------------------------------------
# RIXS profile panel (checkBox_show_rixsprofile)
# ---------------------------------------------------------------------------


def test_profile_plot_visible_by_default(gui):
    assert gui.view._rxes_profile_plot.isVisible() is True


def test_plot_rxes_map_shows_median_incident_profile_by_default(gui):
    result = _synthetic_rxes_result(n_emission=3, n_incident=5)

    gui.view.plot_rxes_map(result, plot_target="intensity_norm")

    median_index = len(result["incident_axis"]) // 2
    x, y = gui.view._rxes_profile_curve.getData()
    np.testing.assert_array_equal(x, result["emission_axis"])
    np.testing.assert_array_equal(y, result["intensity_norm"][:, median_index])
    assert gui.view._rxes_vline.value() == result["incident_axis"][median_index]


def test_selecting_near_a_clicked_incident_energy_updates_profile_and_marker(gui):
    result = _synthetic_rxes_result(n_emission=3, n_incident=5)
    gui.view.plot_rxes_map(result, plot_target="intensity_norm")
    incident_axis = result["incident_axis"]
    target_index = 3
    click_value = incident_axis[target_index] + 0.0001  # near, not exact

    gui.view._select_incident_index_near(click_value)

    x, y = gui.view._rxes_profile_curve.getData()
    np.testing.assert_array_equal(y, result["intensity_norm"][:, target_index])
    assert gui.view._rxes_vline.value() == incident_axis[target_index]


def test_set_rxes_profile_visible_toggles_plot_and_marker(gui):
    result = _synthetic_rxes_result(n_emission=3, n_incident=5)
    gui.view.plot_rxes_map(result, plot_target="intensity_norm")

    gui.view.set_rxes_profile_visible(False)
    assert gui.view._rxes_profile_plot.isVisible() is False
    assert gui.view._rxes_vline.isVisible() is False

    gui.view.set_rxes_profile_visible(True)
    assert gui.view._rxes_profile_plot.isVisible() is True
    assert gui.view._rxes_vline.isVisible() is True
    median_index = len(result["incident_axis"]) // 2
    x, y = gui.view._rxes_profile_curve.getData()
    np.testing.assert_array_equal(y, result["intensity_norm"][:, median_index])


def test_profile_index_resets_to_median_when_incident_grid_size_changes(gui):
    small = _synthetic_rxes_result(n_emission=3, n_incident=2)
    gui.view.plot_rxes_map(small, plot_target="intensity_norm")
    gui.view._select_incident_index_near(small["incident_axis"][1])  # pick a non-default index

    bigger = _synthetic_rxes_result(n_emission=3, n_incident=7)
    gui.view.plot_rxes_map(bigger, plot_target="intensity_norm")

    expected_index = len(bigger["incident_axis"]) // 2
    x, y = gui.view._rxes_profile_curve.getData()
    np.testing.assert_array_equal(y, bigger["intensity_norm"][:, expected_index])
    assert gui.view._rxes_vline.value() == bigger["incident_axis"][expected_index]


def test_profile_index_persists_across_a_same_shape_replot(gui):
    result1 = _synthetic_rxes_result(n_emission=3, n_incident=5)
    gui.view.plot_rxes_map(result1, plot_target="intensity_norm")
    chosen_index = 1
    gui.view._select_incident_index_near(result1["incident_axis"][chosen_index])

    result2 = _synthetic_rxes_result(n_emission=3, n_incident=5)  # same shape, e.g. a live-update tick
    gui.view.plot_rxes_map(result2, plot_target="intensity_norm")

    x, y = gui.view._rxes_profile_curve.getData()
    np.testing.assert_array_equal(y, result2["intensity_norm"][:, chosen_index])


def test_selecting_incident_index_before_any_result_is_a_noop(gui):
    gui.view._select_incident_index_near(12.65)  # must not raise
    assert gui.view._rxes_last_result is None


def test_checkbox_toggle_calls_set_rxes_profile_visible(gui, monkeypatch):
    calls = []
    monkeypatch.setattr(gui.view, "set_rxes_profile_visible", lambda v: calls.append(v))

    gui.ui.checkBox_show_rixsprofile.setChecked(False)

    assert calls == [False]


def test_switching_display_target_updates_profile_source_array(gui):
    result = _synthetic_rxes_result(n_emission=3, n_incident=5)
    gui.beamline.run_rxes_scan(1, n_emission=3, n_incident=5)
    gui.update_spec_record()
    gui.current_rixs_dset.bin_result = result

    gui.view.plot_rxes_map(result, plot_target="intensity_norm")
    median_index = len(result["incident_axis"]) // 2

    gui.ui.comboBox_rxes_plottarget.setCurrentText("sample")

    x, y = gui.view._rxes_profile_curve.getData()
    np.testing.assert_array_equal(y, result["sample"][:, median_index])


# ---------------------------------------------------------------------------
# Colormap selection (comboBox_rxes_cmap)
# ---------------------------------------------------------------------------


def test_rxes_cmap_combo_defaults_to_jet(gui):
    assert gui.ui.comboBox_rxes_cmap.currentText() == "jet"
    assert gui.view._rxes_cmap_name == "jet"


def test_set_rxes_colormap_changes_the_map_colors(gui):
    lut_before = gui.view._rxes_hist.gradient.colorMap().getLookupTable(nPts=8)

    gui.view.set_rxes_colormap("viridis")

    lut_after = gui.view._rxes_hist.gradient.colorMap().getLookupTable(nPts=8)
    assert gui.view._rxes_cmap_name == "viridis"
    assert not np.array_equal(lut_before, lut_after)


def test_cmap_combo_change_calls_set_rxes_colormap(gui, monkeypatch):
    calls = []
    monkeypatch.setattr(gui.view, "set_rxes_colormap", lambda name: calls.append(name))

    gui.ui.comboBox_rxes_cmap.setCurrentText("plasma")

    assert calls == ["plasma"]
