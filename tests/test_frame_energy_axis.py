# Copyright © UChicago Argonne LLC
# See LICENSE file for details
import logging

import numpy as np

from rixsviewer.model.utils import _compute_energy_axis, compute_frame_energy_axis


def test_matches_hand_computed_rowland_formula():
    # Values must satisfy Eb <= energy_ref (near-backscattering geometry).
    energy_ref = np.array([11.190, 11.195])
    xaxis = np.array([-2.0, -1.0, 0.0, 1.0, 2.0])
    Eb = 11.184
    Ra = 1998.0
    DeltaD = 0.022

    theta_b = np.arcsin(Eb / energy_ref)
    scale = Eb / (2 * Ra) / np.tan(theta_b)
    expected = energy_ref.reshape(-1, 1) - np.outer(scale, xaxis) * DeltaD

    result = compute_frame_energy_axis(energy_ref, xaxis, Eb, Ra, DeltaD)

    np.testing.assert_allclose(result, expected)


def test_single_frame_shape():
    result = compute_frame_energy_axis(
        [11.190], np.arange(5) - 2, 11.184, 1998.0, 0.022
    )
    assert result.shape == (1, 5)


def test_accepts_plain_list_input():
    result = compute_frame_energy_axis(
        [11.190, 11.195], [-1.0, 0.0, 1.0], 11.184, 1998.0, 0.022
    )
    assert result.shape == (2, 3)


def _bin_finer_than_native(force, caplog):
    """Bin a 3-frame EnergyScan with a bin count far finer than the pixels."""
    merixE = np.linspace(11.190, 11.200, 3)
    xaxis = np.arange(-5, 6)
    data_2d = np.ones((merixE.size, xaxis.size))
    with caplog.at_level(logging.WARNING, logger="rixsviewer.model.utils"):
        _, bin_energy_axis, _ = _compute_energy_axis(
            data_2d, xaxis, merixE, 11.184, 1998.0, "EnergyScan", 0.022, 11.190, 11.200,
            NEnergyBins=9999, force_NEnergyBins=force,
        )
    return bin_energy_axis, caplog.text


def test_too_fine_bin_count_warns_about_fallback_when_not_forced(caplog):
    bin_energy_axis, log_text = _bin_finer_than_native(False, caplog)

    assert len(bin_energy_axis) < 9999
    assert "falling back to native spacing" in log_text


def test_too_fine_bin_count_warning_says_it_is_kept_when_forced(caplog):
    bin_energy_axis, log_text = _bin_finer_than_native(True, caplog)

    assert len(bin_energy_axis) == 10000
    assert "keeping it because Force NEnergyBins is on" in log_text
    assert "falling back" not in log_text
