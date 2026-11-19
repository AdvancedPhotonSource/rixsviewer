# Copyright © UChicago Argonne LLC
# See LICENSE file for details
"""Regression tests for auto-update memory growth (OOM kill after long sessions).

Root cause (2026-08): the auto-update timer slot ``update_spec_record`` switched
``current_rixs_dset`` to each new scan without releasing the previous scan's
loaded TIFF stack (``_data``, a full float32 volume).  The only eviction lived
in ``on_selection_changed`` (manual row click), so an unattended auto-update
session retained every scan's stack until the OS OOM-killed the app.

The production change that makes the RED test below pass: ``update_spec_record``
must evict the previous dataset's stack when the current dataset changes.
"""

import numpy as np

from conftest import POINTS, W


def _fill_scan1_and_switch(gui):
    """Run scan 1, let its stack load, then let scan 2 arrive."""
    gui.beamline.run_scan(1)
    gui.update_spec_record()
    d1 = gui.current_rixs_dset
    assert d1 is not None
    d1.read_tiff_data()  # what the binning worker / update_image do
    assert d1._data is not None

    gui.beamline.start_scan(2)
    gui.beamline.add_point(2, 0)
    gui.update_spec_record()
    return d1


class TestAutoUpdateEviction:
    def test_previous_scan_stack_evicted_when_new_scan_arrives(self, gui):
        d1 = _fill_scan1_and_switch(gui)

        assert gui.current_rixs_dset is not d1
        assert d1._data is None, "previous scan's TIFF stack must be released on scan switch"
        assert d1._buffer is None, "eviction must free the preallocated buffer, not just the view"

    def test_evicted_scan_can_reload_from_disk(self, gui):
        d1 = _fill_scan1_and_switch(gui)

        assert d1.unloaded_filenames == list(d1.scan_info["filenames"])
        reloaded = d1.read_tiff_data()
        assert reloaded is not None and len(reloaded) == POINTS

    def test_current_scan_stack_not_evicted(self, gui):
        _fill_scan1_and_switch(gui)
        d2 = gui.current_rixs_dset
        d2.read_tiff_data()
        assert d2._data is not None


class TestManualSelectionEviction:
    def test_switching_rows_manually_still_evicts_previous_stack(self, gui):
        gui.beamline.run_scan(1)
        gui.beamline.run_scan(2)
        gui.update_spec_record()

        gui.ui.tableView_scan.selectRow(0)
        d1 = gui.current_rixs_dset
        assert d1 is not None and d1._data is not None  # update_image loaded it

        gui.ui.tableView_scan.selectRow(1)
        assert gui.current_rixs_dset is not d1
        assert d1._data is None


class TestEvictionDeferredDuringBinning:
    """If a background worker is still reading a dataset's buffer
    (process_binning -> bin_data_wrap -> read_tiff_data), evicting that
    buffer from the main thread would race the worker. Eviction must be
    deferred until the worker's on_finished callback runs."""

    def test_eviction_deferred_while_binning_active(self, gui):
        gui.beamline.run_scan(1)
        gui.update_spec_record()
        d1 = gui.current_rixs_dset
        d1.read_tiff_data()
        assert d1._data is not None

        # simulate process_binning() having started a worker on d1
        gui._binning_active = True
        gui._binning_dset = d1

        gui.beamline.start_scan(2)
        gui.beamline.add_point(2, 0)
        gui.update_spec_record()

        assert gui.current_rixs_dset is not d1
        assert d1._data is not None, "must not evict while a worker may still be using the buffer"
        assert d1._buffer is not None
        assert gui._pending_evict is d1

    def test_deferred_eviction_flushed_on_finished(self, gui):
        gui.beamline.run_scan(1)
        gui.update_spec_record()
        d1 = gui.current_rixs_dset
        d1.read_tiff_data()

        gui._binning_active = True
        gui._binning_dset = d1
        gui.beamline.start_scan(2)
        gui.beamline.add_point(2, 0)
        gui.update_spec_record()
        assert d1._data is not None  # still deferred

        # simulate on_finished(): clear the active flag and flush the
        # pending eviction, as process_binning's worker completion does
        gui._binning_active = False
        gui._binning_dset = None
        if gui._pending_evict is not None:
            pending = gui._pending_evict
            gui._pending_evict = None
            gui._evict_scan_data(pending)

        assert d1._data is None
        assert d1._buffer is None


class TestPreallocatedStack:
    """Frames must be appended in place into a preallocated buffer so that
    incremental loads during a live scan never reallocate (2x peak)."""

    def test_append_does_not_reallocate_buffer(self, gui):
        gui.beamline.start_scan(1)
        gui.beamline.add_point(1, 0)
        gui.update_spec_record()
        d1 = gui.current_rixs_dset
        d1.read_tiff_data()
        base = d1._data.base
        assert base is not None, "stack should be a view into a preallocated buffer"

        gui.beamline.add_point(1, 1)
        gui.update_spec_record()
        d1.read_tiff_data()

        assert d1._data.base is base, "appending frames must not reallocate the buffer"
        assert len(d1._data) == 2
        assert np.all(d1._data[1][:, W // 2] == 60000), "new frame must land in the next slot"

    def test_capacity_covers_spec_points_but_len_matches_loaded(self, gui):
        # #S line declares 3 steps -> spec_points 4, but only POINTS (3) tiffs exist
        gui.beamline.run_scan(1)
        gui.update_spec_record()
        d1 = gui.current_rixs_dset
        d1.read_tiff_data()

        assert len(d1._data) == POINTS
        assert d1._data.base is not None
        assert d1._data.base.shape[0] >= 4, "buffer should be preallocated to spec_points"

    def test_release_data_frees_buffer(self, gui):
        gui.beamline.run_scan(1)
        gui.update_spec_record()
        d1 = gui.current_rixs_dset
        d1.read_tiff_data()
        assert d1._data is not None

        d1.release_data()
        assert d1._buffer is None
        assert d1._data is None

        reloaded = d1.read_tiff_data()
        assert reloaded is not None and len(reloaded) == POINTS

    def test_regrow_when_tiffs_exceed_spec_points(self, gui):
        gui.beamline.start_scan(1)
        for pt in range(POINTS + 2):  # 5 tiffs > spec_points (4)
            gui.beamline.add_point(1, pt)
        gui.update_spec_record()
        d1 = gui.current_rixs_dset
        d1.read_tiff_data()

        assert len(d1._data) == POINTS + 2
        assert np.all(d1._data[POINTS + 1][:, W // 2] == 60000)
