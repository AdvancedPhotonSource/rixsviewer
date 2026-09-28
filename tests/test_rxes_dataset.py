# Copyright © UChicago Argonne LLC
# See LICENSE file for details
import numpy as np
from silx.io.specfile import SpecFile

from rixsviewer.model.rxes_dataset import RixsRxesScanDataset

from conftest import FakeBeamline, XB_FIELDS


def _scan_pack(spec_path, scan_no):
    for scan in SpecFile(spec_path):
        if scan.number == scan_no:
            return scan
    raise ValueError(f"scan {scan_no} not found in {spec_path}")


def _make_dataset(tmp_path, n_emission=2, n_incident=2, n_points=None):
    beamline = FakeBeamline(str(tmp_path))
    beamline.start_rxes_scan(1, n_emission=n_emission, n_incident=n_incident)
    total = n_emission * n_incident
    for pt in range(total if n_points is None else n_points):
        beamline.add_rxes_point(1, pt)

    dset = RixsRxesScanDataset(0, beamline.spec, beamline.workdir, 1)
    dset.update_scan_info(_scan_pack(beamline.spec, 1))
    return dset, beamline


SPECFILE_KWARGS = dict(metadata_source="SpecFile")


class TestConstruction:
    def test_scan_info_reflects_rxes_scan_type(self, tmp_path):
        dset, _ = _make_dataset(tmp_path, n_points=1)
        assert dset.scan_info["scan_type"] == "RXESScan"
        assert dset.bin_result is None
        assert dset.emission_axis is None  # not built until first bin_data_wrap call


class TestAccumulatorReset:
    def test_reset_builds_axes_and_zeroed_arrays(self, tmp_path):
        dset, _ = _make_dataset(tmp_path, n_emission=3, n_incident=2, n_points=0)
        merged = dset._merge_binning_kwargs(
            "SpecFile", {}
        )
        dset._reset_accumulator(merged)

        assert dset.incident_axis.shape == (2,)
        np.testing.assert_allclose(dset.incident_axis[0], 12.650)
        np.testing.assert_allclose(dset.incident_axis[-1], 12.660)
        assert dset.intensity.shape[1] == 2
        assert dset.sample.shape == dset.intensity.shape
        assert np.all(dset.sample == 0)
        assert np.all(dset.intensity == 0)
        assert dset.emission_axis.min() <= 11.190
        assert dset.emission_axis.max() >= 11.200


class TestIsComplete:
    def test_false_while_grid_partially_filled(self, tmp_path):
        dset, _ = _make_dataset(tmp_path, n_emission=2, n_incident=2, n_points=2)
        assert dset.is_complete() is False

    def test_true_once_full_grid_has_arrived(self, tmp_path):
        dset, _ = _make_dataset(tmp_path, n_emission=2, n_incident=2, n_points=4)
        assert dset.is_complete() is True
