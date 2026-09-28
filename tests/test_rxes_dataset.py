# Copyright © UChicago Argonne LLC
# See LICENSE file for details
import numpy as np
from silx.io.specfile import SpecFile

from rixsviewer.model.rxes_dataset import RixsRxesScanDataset
from rixsviewer.model.spec_parsers import tiff_point_index

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


class TestHasLoadedFrames:
    def test_false_before_any_frame_processed(self, tmp_path):
        dset, _ = _make_dataset(tmp_path, n_points=1)
        assert dset.has_loaded_frames() is False

    def test_true_after_processing_a_frame(self, tmp_path):
        dset, _ = _make_dataset(tmp_path, n_points=1)
        dset.bin_data_wrap(metadata_source="SpecFile")
        assert dset.has_loaded_frames() is True


class TestProcessingTimeLogging:
    def test_logs_elapsed_time_when_frames_are_processed(self, caplog, tmp_path):
        dset, _ = _make_dataset(tmp_path, n_points=1)

        with caplog.at_level("INFO"):
            dset.bin_data_wrap(metadata_source="SpecFile")

        assert "processed 1 frame" in caplog.text

    def test_does_not_log_timing_when_nothing_new_to_process(self, caplog, tmp_path):
        dset, _ = _make_dataset(tmp_path, n_points=1)
        dset.bin_data_wrap(metadata_source="SpecFile")
        caplog.clear()

        with caplog.at_level("INFO"):
            dset.bin_data_wrap(metadata_source="SpecFile")  # nothing new queued

        assert "processed" not in caplog.text


class TestSupportsCalibration:
    def test_rxes_dataset_does_not_support_calibration(self, tmp_path):
        dset, _ = _make_dataset(tmp_path, n_points=1)
        assert dset.supports_calibration() is False


class TestSupportsRxesMap:
    def test_rxes_dataset_supports_rxes_map(self, tmp_path):
        dset, _ = _make_dataset(tmp_path, n_points=1)
        assert dset.supports_rxes_map() is True


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


class TestFramePositionFromFilename:
    def test_position_derived_from_filename_not_processing_order(self, tmp_path):
        dset, beamline = _make_dataset(tmp_path, n_emission=2, n_incident=2, n_points=4)
        # Pre-warm the accumulator (as the first bin_data_wrap call normally
        # would) so the manual unloaded_filenames override below survives --
        # bin_data_wrap's own reset-on-first-call would otherwise clobber it
        # back to the full file list.
        merged = dset._merge_binning_kwargs("SpecFile", {})
        dset._reset_accumulator(merged)
        dset._map_key = dset._calibration_key(merged)

        # Only queue points 2,3 (emission row i=1, anchored near the HIGH
        # end of the emission axis at merixE=11.200) for processing --
        # simulating an out-of-order arrival (e.g. NFS lag) where these
        # land before points 0,1. A counter that numbers whatever it's
        # given starting from 0 would wrongly anchor these on i=0's merixE
        # (11.190, the LOW end) instead of their true i=1 value.
        dset.unloaded_filenames = [
            f for f in dset.scan_info["filenames"] if tiff_point_index(f) in (2, 3)
        ]
        dset.bin_data_wrap(**SPECFILE_KWARGS)

        touched_bins = np.where(dset.sample[:, 0] > 0)[0]
        assert len(touched_bins) > 0
        touched_energies = dset.emission_axis[touched_bins]
        # i=0's and i=1's windows are far apart and disjoint (see
        # TestRecalibration's docstring reasoning) -- only i=1's frames
        # should ever appear here.
        assert touched_energies.min() > 11.195


class TestTiffAheadOfScandata:
    def test_frame_beyond_scandata_rows_is_requeued_not_crashed(self, tmp_path):
        import os

        import tifffile

        dset, beamline = _make_dataset(tmp_path, n_emission=2, n_incident=2, n_points=1)
        dset.bin_data_wrap(**SPECFILE_KWARGS)  # pre-warm; processes point 0
        assert dset._n_processed == 1

        # Simulate the detector outrunning SPEC's row flush: a TIFF for
        # point 1 lands on disk, but scan_info["scandata"] still only has
        # 1 row (as refresh_tiff_filenames()'s NFS-lag catch-up can produce).
        fn = os.path.join(beamline.workdir, "fake.spec_scan1_point0001.tif")
        tifffile.imwrite(fn, np.zeros((256, 256), dtype=np.uint16))
        dset.scan_info["filenames"] = dset.scan_info["filenames"] + [fn]
        dset.scan_info["tiff_points"] = len(dset.scan_info["filenames"])
        dset.unloaded_filenames = [fn]

        dset.bin_data_wrap(**SPECFILE_KWARGS)  # must not raise IndexError

        assert dset.unloaded_filenames == [fn]  # re-queued for the next poll, not dropped


class TestCalibrationKeyTolerance:
    def test_tiny_float_jitter_does_not_trigger_a_replay(self, tmp_path):
        dset, beamline = _make_dataset(tmp_path, n_emission=2, n_incident=2, n_points=2)
        dset.bin_data_wrap(**SPECFILE_KWARGS)
        assert dset._n_processed == 2

        # Simulates a PV readback returning a value that differs only in
        # the last few significant digits from a previous read -- should
        # not be treated as a real calibration change.
        kwargs = dict(dset.scan_info["metadata"])
        kwargs["DeltaD"] = kwargs["DeltaD"] + 1e-10
        dset.bin_data_wrap(metadata_source="USER", **kwargs)

        assert dset._n_processed == 2  # no replay: nothing was re-queued or reprocessed

    def test_meaningful_change_still_triggers_reset(self, tmp_path):
        dset, beamline = _make_dataset(tmp_path, n_emission=2, n_incident=2, n_points=2)
        dset.bin_data_wrap(**SPECFILE_KWARGS)
        assert dset._n_processed == 2

        kwargs = dict(dset.scan_info["metadata"])
        kwargs["DeltaD"] = kwargs["DeltaD"] * 2
        dset.bin_data_wrap(metadata_source="USER", **kwargs)

        assert dset._n_processed == 2  # reset-and-replayed the 2 known files, not skipped


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


class TestGetDataForDisplay:
    def test_returns_last_frame_by_default(self, tmp_path):
        dset, beamline = _make_dataset(tmp_path, n_emission=2, n_incident=2, n_points=3)

        result = dset.get_data_for_display()

        assert result is not None
        assert result["frame_index"] == 2
        assert result["num_frames"] == 3
        assert result["data"].shape == (256, 256)

    def test_returns_none_when_no_files_yet(self, tmp_path):
        dset, _ = _make_dataset(tmp_path, n_points=0)
        assert dset.get_data_for_display() is None


class TestReleaseData:
    def test_release_data_is_a_harmless_no_op(self, tmp_path):
        dset, _ = _make_dataset(tmp_path, n_points=2)
        dset.bin_data_wrap(**SPECFILE_KWARGS)
        dset.release_data()  # must not raise or clear the accumulator
        assert dset.intensity is not None


class TestSaveToFile:
    def test_save_to_file_is_a_no_op(self, tmp_path):
        dset, _ = _make_dataset(tmp_path, n_points=2)
        dset.bin_data_wrap(**SPECFILE_KWARGS)
        dset.save_to_file(str(tmp_path / "out.spec"))  # must not raise
        assert not (tmp_path / "out.spec").exists()
