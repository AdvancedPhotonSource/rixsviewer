# Copyright © UChicago Argonne LLC
# See LICENSE file for details
"""Catch up on scans that were binned in a previous session but never got
saved -- e.g. because RixsViewer crashed before reaching them.  When
"Auto-update" is (re-)checked, already-saved scans must be skipped,
complete-but-unsaved scans must be processed, then live polling resumes.
"""

import os

import numpy as np
import pandas as pd
import tifffile

from rixsviewer.model.scan_dataset import RixsScanTiffDataset
from rixsviewer.model.spec_table import RixsSpecTable

from conftest import FakeBeamline, E0, E1, H, W, XB_FIELDS

FILE_SAVE_KEYS = [
    "energy_axis",
    "intensity_norm",
    "intensity_norm_err",
    "intensity_raw",
    "sample",
    "i2",
    "i0",
    "mmepin1",
    "mmepin2",
]


def _fake_bin_result(n_points=3):
    return {key: np.zeros(n_points) for key in FILE_SAVE_KEYS}


def _write_complete_scan(spec_path, workdir, scan_no, n_points=3):
    """Write a SPEC scan + matching TIFFs with tiff_points == spec_points exactly."""
    with open(spec_path, "a") as f:
        f.write(f"#S {scan_no} ascan merixE {E0} {E1} {n_points - 1} 0.1\n")
        f.write("#N 5\n")
        f.write("#L merixE i0 i2 mmepin1 mmepin2\n")
        f.write(f"#B {' '.join(XB_FIELDS)}\n")
        f.write("#D 2026-08-27 12:00:00\n")
        for pt in range(n_points):
            e = E0 + (E1 - E0) * pt / max(n_points - 1, 1)
            f.write(f"{e:.6f} 1.0 100.0 10.0 10.0\n")
    for pt in range(n_points):
        img = np.zeros((H, W), dtype=np.uint16)
        img[:, W // 2] = 60000
        tifffile.imwrite(
            os.path.join(workdir, f"fake.spec_scan{scan_no}_point{pt:04d}.tif"), img
        )


class TestIsComplete:
    def test_true_when_tiff_points_match_spec_points_and_scandata_full(self):
        dset = RixsScanTiffDataset(0, "fake.spec", "/tmp", 1)
        dset.scan_info = {
            "tiff_points": 3,
            "spec_points": 3,
            "scandata": pd.DataFrame({"merixE": [1, 2, 3]}),
        }
        assert dset.is_complete() is True

    def test_false_when_tiff_points_less_than_spec_points(self):
        dset = RixsScanTiffDataset(0, "fake.spec", "/tmp", 1)
        dset.scan_info = {
            "tiff_points": 2,
            "spec_points": 3,
            "scandata": pd.DataFrame({"merixE": [1, 2]}),
        }
        assert dset.is_complete() is False

    def test_false_when_scan_info_is_none(self):
        dset = RixsScanTiffDataset(0, "fake.spec", "/tmp", 1)
        assert dset.is_complete() is False


class TestGetUnprocessedScans:
    def test_returns_all_complete_scans_when_no_save_file_exists_yet(self, tmp_path):
        beamline = FakeBeamline(str(tmp_path))
        _write_complete_scan(beamline.spec, beamline.workdir, 1)
        _write_complete_scan(beamline.spec, beamline.workdir, 2)
        save_filename = os.path.join(str(tmp_path), "fake_bindata_rixsviewer.spec")

        table = RixsSpecTable(beamline.spec, beamline.workdir, save_filename)

        assert [d.scan_index for d in table.get_unprocessed_scans()] == [1, 2]

    def test_scans_already_saved_are_skipped(self, tmp_path):
        beamline = FakeBeamline(str(tmp_path))
        _write_complete_scan(beamline.spec, beamline.workdir, 1)
        _write_complete_scan(beamline.spec, beamline.workdir, 2)
        _write_complete_scan(beamline.spec, beamline.workdir, 3)
        save_filename = os.path.join(str(tmp_path), "fake_bindata_rixsviewer.spec")

        table = RixsSpecTable(beamline.spec, beamline.workdir, save_filename)
        table.record[1].bin_result = _fake_bin_result()
        table.record[1].save_to_file(save_filename)

        assert [d.scan_index for d in table.get_unprocessed_scans()] == [2, 3]

    def test_incomplete_scan_is_excluded(self, tmp_path):
        beamline = FakeBeamline(str(tmp_path))
        _write_complete_scan(beamline.spec, beamline.workdir, 1, n_points=3)
        _write_complete_scan(beamline.spec, beamline.workdir, 2, n_points=3)
        # scan 2's data rows are all in the SPEC file, but 2 of its 3 tiffs
        # never landed on disk -- simulates a stalled/interrupted scan.
        os.remove(os.path.join(beamline.workdir, "fake.spec_scan2_point0001.tif"))
        os.remove(os.path.join(beamline.workdir, "fake.spec_scan2_point0002.tif"))
        save_filename = os.path.join(str(tmp_path), "fake_bindata_rixsviewer.spec")

        table = RixsSpecTable(beamline.spec, beamline.workdir, save_filename)

        assert [d.scan_index for d in table.get_unprocessed_scans()] == [1]


class TestAutoUpdateBackfill:
    def test_checking_autoupdate_with_nothing_unprocessed_starts_timer_directly(self, gui):
        gui.beamline.start_scan(1)
        gui.beamline.add_point(1, 0)  # scan still in progress -> incomplete
        gui.update_spec_record()

        gui.ui.checkBox_autoupdate.setChecked(True)

        assert gui.timer.isActive()
        assert gui._backfill_queue == []
        assert gui._catching_up is False

    def test_checking_autoupdate_processes_missed_scans_before_polling(self, gui):
        _write_complete_scan(gui.beamline.spec, gui.beamline.workdir, 1)
        _write_complete_scan(gui.beamline.spec, gui.beamline.workdir, 2)
        _write_complete_scan(gui.beamline.spec, gui.beamline.workdir, 3)
        gui.update_spec_record()

        processed_order = []

        def fake_process_binning():
            dset = gui.current_rixs_dset
            dset.bin_result = _fake_bin_result()
            dset.save_to_file(gui.save_filename)
            processed_order.append(dset.scan_index)
            if gui._catching_up:
                gui._advance_backfill_queue()

        gui.process_binning = fake_process_binning

        gui.ui.checkBox_autoupdate.setChecked(True)

        assert processed_order == [1, 2, 3]
        assert gui.timer.isActive()
        assert gui._catching_up is False
        assert gui.scan_model.record[1]._saved
        assert gui.scan_model.record[2]._saved
        assert gui.scan_model.record[3]._saved

    def test_unchecking_autoupdate_clears_backfill_state(self, gui):
        gui.ui.checkBox_autoupdate.setChecked(True)
        gui._catching_up = True
        gui._backfill_queue = [object()]

        gui.ui.checkBox_autoupdate.setChecked(False)

        assert gui._catching_up is False
        assert gui._backfill_queue == []
        assert not gui.timer.isActive()
