# Copyright © UChicago Argonne LLC
# See LICENSE file for details
from rixsviewer.model.scan_dataset import RixsEnergyScanDataset


def _dset_with_scan_info(scan_info):
    dset = RixsEnergyScanDataset(0, "fake.spec", "/tmp", 1)
    dset.scan_info = scan_info
    return dset


class TestGetQtableviewDisplayData:
    def test_returns_scan_number_type_points_by_column(self):
        dset = _dset_with_scan_info(
            {
                "scan_number": 5,
                "scan_type": "EnergyScan",
                "spec_points": 10,
                "tiff_points": 8,
            }
        )
        assert dset.get_qtableview_display_data(0) == 5
        assert dset.get_qtableview_display_data(1) == "EnergyScan"
        assert dset.get_qtableview_display_data(2) == 10
        assert dset.get_qtableview_display_data(3) == 8


class TestGetTableModel:
    def test_lists_filenames_and_caches_model(self):
        dset = _dset_with_scan_info({"filenames": ["/a/one.tif", "/a/two.tif"]})
        model = dset.get_table_model()
        assert model.rowCount() == 2
        assert dset.get_table_model() is model  # cached, same instance

    def test_update_fnames_refreshes_existing_model(self):
        dset = _dset_with_scan_info({"filenames": ["/a/one.tif"]})
        model = dset.get_table_model()
        dset.scan_info["filenames"] = ["/a/one.tif", "/a/two.tif"]
        updated = dset.get_table_model()
        assert updated is model
        assert updated.rowCount() == 2


class TestApplyTiltAngle:
    def test_zero_tilt_is_a_no_op(self):
        import numpy as np

        dset = _dset_with_scan_info({"metadata": {"Ylow": 0, "Yhigh": 4}})
        frame = np.arange(16, dtype=np.float32).reshape(4, 4)
        result = dset.apply_tilt_angle(frame, tilt_angle=0)
        np.testing.assert_array_equal(result, frame)


class TestRefreshTiffFilenames:
    def test_picks_up_nfs_lagged_files(self, tmp_path):
        import numpy as np
        import tifffile

        spec_path = str(tmp_path / "fake.spec")
        (tmp_path / "fake.spec_scan1_point0000.tif")  # not written yet
        dset = RixsEnergyScanDataset(0, spec_path, str(tmp_path), 1)
        dset.scan_info = {
            "tiff_points": 0,
            "spec_points": 2,
            "filenames": [],
        }

        tifffile.imwrite(
            str(tmp_path / "fake.spec_scan1_point0000.tif"),
            np.zeros((4, 4), dtype=np.uint16),
        )

        found_new = dset.refresh_tiff_filenames()

        assert found_new is True
        assert dset.scan_info["tiff_points"] == 1
        assert dset._saved is False
