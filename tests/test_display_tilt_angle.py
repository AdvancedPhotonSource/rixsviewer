# Copyright © UChicago Argonne LLC
# See LICENSE file for details
"""Regression test: in SpecFile mode, update_image() sheared the displayed
frame with the parameter tree's TiltAngle *before* copying the newly
selected scan's SPEC metadata into the tree -- so the first frame shown
after switching scans used the previous scan's tilt angle.
"""
import numpy as np


def test_switching_scans_displays_frame_with_the_new_scans_tilt_angle(gui):
    assert gui.ui.comboBox_metasource.currentText() == "SpecFile"
    gui.beamline.run_snapshot_scan(1, tilt_angle=0.0)
    gui.beamline.run_snapshot_scan(2, tilt_angle=5.0)
    gui.update_spec_record()

    gui.ui.tableView_scan.selectRow(0)  # scan 1, untilted
    gui.ui.tableView_scan.selectRow(1)  # scan 2, tilted 5 deg
    assert gui.current_rixs_dset.scan_index == 2

    img = gui.view.img2d_hdl.image
    # Each TIFF is a vertical line at column 128 spanning all 256 rows
    # (Ylow=0, Yhigh=256). A 5 deg shear shifts row y by
    # sin(5 deg) * (y - 127.5), i.e. ~11 px one way on the top row and
    # ~11 px the other way on the bottom row: ~22 px apart. Unsheared,
    # both rows peak in the same column.
    spread = abs(int(np.argmax(img[0])) - int(np.argmax(img[-1])))
    assert 20 <= spread <= 24
