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


class TestIncrementalAccumulation:
    def test_raises_on_empty_scandata(self, tmp_path):
        import pytest

        dset, _ = _make_dataset(tmp_path, n_points=0)
        with pytest.raises(ValueError, match="no scandata rows"):
            dset.bin_data_wrap(**SPECFILE_KWARGS)

    def test_partial_scan_only_touches_arrived_columns(self, tmp_path):
        dset, beamline = _make_dataset(tmp_path, n_emission=2, n_incident=2, n_points=2)

        result = dset.bin_data_wrap(**SPECFILE_KWARGS)

        assert result["kind"] == "rxes_map"
        assert result["intensity_norm"].shape[1] == 2
        assert dset._n_processed == 2
        # points 0,1 share the same emission row (i=0) -> identical, positive
        # coverage in both incident columns; no single bin sees more than
        # the one frame contributed to that column.
        col_sums = dset.sample.sum(axis=0)
        assert col_sums[0] > 0
        assert col_sums[0] == col_sums[1]
        assert dset.sample.max() <= 1

    def test_second_call_only_processes_newly_arrived_frames(self, tmp_path):
        dset, beamline = _make_dataset(tmp_path, n_emission=2, n_incident=2, n_points=2)
        dset.bin_data_wrap(**SPECFILE_KWARGS)
        assert dset.unloaded_filenames == []
        first_call_sum = dset.sample.sum(axis=0).copy()

        beamline.add_rxes_point(1, 2)
        beamline.add_rxes_point(1, 3)
        dset.update_scan_info(_scan_pack(beamline.spec, 1))
        assert len(dset.unloaded_filenames) == 2

        dset.bin_data_wrap(**SPECFILE_KWARGS)

        assert dset._n_processed == 4
        second_call_sum = dset.sample.sum(axis=0)
        # the new emission row's frame added real coverage on top of the
        # first call's, symmetrically across both incident columns, and no
        # bin was ever touched by more than one of the two per-column frames
        # (which would indicate a stale frame got reprocessed).
        assert second_call_sum[0] > first_call_sum[0]
        assert second_call_sum[0] == second_call_sum[1]
        assert dset.sample.max() <= 1


class TestRecalibration:
    def test_changing_deltad_resets_and_replays_without_double_counting(self, tmp_path):
        dset, beamline = _make_dataset(tmp_path, n_emission=2, n_incident=2, n_points=4)
        dset.bin_data_wrap(**SPECFILE_KWARGS)
        assert dset._n_processed == 4

        kwargs = dict(dset.scan_info["metadata"])
        kwargs["DeltaD"] = kwargs["DeltaD"] * 2
        dset.bin_data_wrap(metadata_source="USER", **kwargs)

        assert dset._n_processed == 4
        # each incident column only ever receives 2 frames (i=0 and i=1);
        # if the reset-and-replay had failed to reset (double-accumulating
        # onto the pre-recalibration arrays), some bin would see more than
        # one of the two frames' disjoint windows.
        assert dset.sample.max() <= 1
        col_sums = dset.sample.sum(axis=0)
        assert col_sums[0] > 0
        assert col_sums[0] == col_sums[1]


class TestOutOfRangeFrame:
    def test_extra_frame_beyond_grid_size_is_skipped_not_crashed(self, tmp_path):
        dset, beamline = _make_dataset(tmp_path, n_emission=2, n_incident=2, n_points=4)
        beamline.add_rxes_point(1, 4)  # 5th point exceeds the declared 2x2 grid
        dset.update_scan_info(_scan_pack(beamline.spec, 1))

        result = dset.bin_data_wrap(**SPECFILE_KWARGS)  # must not raise

        assert result["kind"] == "rxes_map"
        assert dset._n_processed == 5
