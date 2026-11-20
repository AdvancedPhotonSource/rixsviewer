# Copyright © UChicago Argonne LLC
# See LICENSE file for details
import numpy as np
import pytest
from rixsviewer.model.scan_dataset import (
    ENERGY_LABEL,
    MONITOR_DESCRIPTION,
    RESULT_COLUMN_DESCRIPTIONS,
    RESULT_COLUMNS,
    RixsEnergyScanDataset,
    RixsSnapshotScanDataset,
)
from rixsviewer.model.spec_reader import SpecReader
from rixsviewer.model.spec_table import RixsSpecTable

from conftest import FakeBeamline, POINTS


class TestSpecTableDispatchForSnapshotScan:
    def test_snapshot_scan_row_gets_snapshot_dataset(self, tmp_path):
        beamline = FakeBeamline(str(tmp_path))
        beamline.run_scan(1)
        beamline.run_snapshot_scan(2)

        table = RixsSpecTable(beamline.spec, beamline.workdir, save_filename=None)

        assert isinstance(table.record[1], RixsEnergyScanDataset)
        assert isinstance(table.record[2], RixsSnapshotScanDataset)


class TestSupportsCalibration:
    def test_energy_scan_supports_calibration(self, tmp_path):
        beamline = FakeBeamline(str(tmp_path))
        beamline.run_scan(1)
        table = RixsSpecTable(beamline.spec, beamline.workdir, save_filename=None)
        assert table.record[1].supports_calibration() is True

    def test_snapshot_scan_has_no_calibration_methods(self, tmp_path):
        beamline = FakeBeamline(str(tmp_path))
        beamline.run_snapshot_scan(1)
        table = RixsSpecTable(beamline.spec, beamline.workdir, save_filename=None)
        dset = table.record[1]

        assert dset.supports_calibration() is False
        assert not hasattr(dset, "fit_pixel_size_wrap")
        assert not hasattr(dset, "linesearch_to_optimize_parameter")


class TestSupportsRxesMap:
    def test_energy_scan_does_not_support_rxes_map(self, tmp_path):
        beamline = FakeBeamline(str(tmp_path))
        beamline.run_scan(1)
        table = RixsSpecTable(beamline.spec, beamline.workdir, save_filename=None)
        assert table.record[1].supports_rxes_map() is False

    def test_snapshot_scan_does_not_support_rxes_map(self, tmp_path):
        beamline = FakeBeamline(str(tmp_path))
        beamline.run_snapshot_scan(1)
        table = RixsSpecTable(beamline.spec, beamline.workdir, save_filename=None)
        assert table.record[1].supports_rxes_map() is False


class TestEnergyScanBinning:
    def test_bin_data_wrap_gives_every_frame_a_finite_energy_axis(self, tmp_path):
        # Regression test for a code-review finding: the fixture's E0 must
        # satisfy merixE >= Eb (the Rowland near-backscattering formula's
        # physical precondition), or a frame anchored below Eb gets an
        # arcsin domain error -> a silently all-NaN local energy axis for
        # that frame instead of a loud failure. Check each frame's own
        # pre-aggregation axis directly, rather than aggregate bin
        # coverage -- adjacent frames' narrow Rowland windows are not
        # guaranteed to overlap in the same bin at all (they're often
        # disjoint), so a per-bin coverage count isn't the right signal
        # for "did every frame compute cleanly".
        beamline = FakeBeamline(str(tmp_path))
        beamline.run_scan(1)
        table = RixsSpecTable(beamline.spec, beamline.workdir, save_filename=None)
        dset = table.record[1]

        result = dset.bin_data_wrap(metadata_source="SpecFile")

        raw_lines = result["rawdata_lines"]
        assert len(raw_lines) == POINTS
        for energy_axis, _intensity in raw_lines:
            assert np.isfinite(energy_axis).all()
        assert np.isfinite(result["intensity_norm"]).all()


class TestSnapshotScanBinning:
    def test_bin_data_wrap_populates_summed_image(self, tmp_path):
        beamline = FakeBeamline(str(tmp_path))
        beamline.run_snapshot_scan(1)
        table = RixsSpecTable(beamline.spec, beamline.workdir, save_filename=None)
        dset = table.record[1]

        result = dset.bin_data_wrap(metadata_source="SpecFile")

        assert result["summed_data"] is not None
        assert result["levels"] is not None


class TestSavedFileColumns:
    def _save_scan(self, tmp_path, snapshot):
        beamline = FakeBeamline(str(tmp_path))
        if snapshot:
            beamline.run_snapshot_scan(1)
        else:
            beamline.run_scan(1)
        table = RixsSpecTable(beamline.spec, beamline.workdir, save_filename=None)
        dset = table.record[1]
        dset.bin_data_wrap(metadata_source="SpecFile")
        out = tmp_path / "saved.spec"
        dset.save_to_file(str(out))
        return dset, out

    @pytest.mark.parametrize("snapshot", [False, True], ids=["EnergyScan", "SnapshotScan"])
    def test_columns_are_the_energy_axis_then_the_shared_result_columns(self, tmp_path, snapshot):
        dset, out = self._save_scan(tmp_path, snapshot)

        scan = SpecReader(str(out))[0]

        assert scan.number == 1
        # the energy column carries its unit, like the RXES axes do
        assert scan.labels == ["Energy_keV"] + list(RESULT_COLUMNS.values())
        assert ENERGY_LABEL == "Energy_keV"
        np.testing.assert_allclose(scan.data[0], dset.bin_result["energy_axis"])
        for column, key in zip(scan.data[1:], RESULT_COLUMNS):
            np.testing.assert_allclose(column, dset.bin_result[key])

    @pytest.mark.parametrize("snapshot", [False, True], ids=["EnergyScan", "SnapshotScan"])
    def test_header_describes_every_saved_column(self, tmp_path, snapshot):
        _, out = self._save_scan(tmp_path, snapshot)

        header = [line for line in out.read_text().splitlines() if line.startswith("#")]
        start = header.index("#C Columns:")
        end = header.index("#N 9")
        assert header[start + 1 : end] == [  # noqa: E203
            "#C   Energy_keV: Bin energy in keV",
            *(f"#C   {label}: {text}" for label, text in RESULT_COLUMN_DESCRIPTIONS.items()),
            f"#C   i2, i0, mmepin1, mmepin2: {MONITOR_DESCRIPTION}",
        ]
