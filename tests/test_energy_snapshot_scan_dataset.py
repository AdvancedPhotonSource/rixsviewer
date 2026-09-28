# Copyright © UChicago Argonne LLC
# See LICENSE file for details
from rixsviewer.model.scan_dataset import RixsEnergyScanDataset, RixsSnapshotScanDataset
from rixsviewer.model.spec_table import RixsSpecTable

from conftest import FakeBeamline


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


class TestSnapshotScanBinning:
    def test_bin_data_wrap_populates_summed_image(self, tmp_path):
        beamline = FakeBeamline(str(tmp_path))
        beamline.run_snapshot_scan(1)
        table = RixsSpecTable(beamline.spec, beamline.workdir, save_filename=None)
        dset = table.record[1]

        result = dset.bin_data_wrap(metadata_source="SpecFile")

        assert result["summed_data"] is not None
        assert result["levels"] is not None
