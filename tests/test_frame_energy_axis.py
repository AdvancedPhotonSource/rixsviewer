# Copyright © UChicago Argonne LLC
# See LICENSE file for details
import numpy as np

from rixsviewer.model.utils import compute_frame_energy_axis


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
