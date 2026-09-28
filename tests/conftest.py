# Copyright © UChicago Argonne LLC
# See LICENSE file for details
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# same suppression used in rixsviewer_gui.main()
os.environ.setdefault("QT_LOGGING_RULES", "qt.core.qobject.connect=false")

import numpy as np  # noqa: E402
import pytest  # noqa: E402
import tifffile  # noqa: E402

# 256x256 keeps every coordinate in the global BAD_PIXELS list in-bounds
# (fix_bad_pixels crashes on out-of-range bad pixels) while staying tiny.
H = W = 256
E0, E1 = 11.190, 11.200
POINTS = 3

RXES_EMISSION_START, RXES_EMISSION_END = 11.190, 11.200  # merixE (analyzer/emission)
RXES_INCIDENT_START, RXES_INCIDENT_END = 12.650, 12.660  # kohzuE (incident)

# metadata the parser requires, consistent with the H x W test detector
XB_FIELDS = [
    "Analyzer_EB_keV = 11.184",
    "Rowland_Radius_m = 1998",
    "Center_x_pixel = 128",
    "Low_y_pixel = 0",
    "High_y_pixel = 256",
    "Analyzer_Crystal_Size_mm = 1.3",
    "Lambda_Strip_Size_mm = 0.022",
    "N_Energy_Bins = 512",
]


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


class FakeBeamline:
    """Appends to a SPEC file and writes TIFFs like live acquisition would."""

    def __init__(self, workdir):
        self.workdir = workdir
        self.spec = os.path.join(workdir, "fake.spec")
        with open(self.spec, "w") as f:
            f.write("#F fake session\n")

    def start_scan(self, scan_no, e0=None, e1=None):
        e0 = E0 if e0 is None else e0
        e1 = E1 if e1 is None else e1
        if not hasattr(self, "_scan_energy_range"):
            self._scan_energy_range = {}
        self._scan_energy_range[scan_no] = (e0, e1)
        with open(self.spec, "a") as f:
            f.write(f"#S {scan_no} ascan merixE {e0} {e1} {POINTS} 0.1\n")
            f.write("#N 5\n")
            f.write("#L merixE i0 i2 mmepin1 mmepin2\n")
            f.write(f"#B {' '.join(XB_FIELDS)}\n")
            f.write("#D 2026-08-27 12:00:00\n")

    def add_point(self, scan_no, pt):
        e0, e1 = getattr(self, "_scan_energy_range", {}).get(scan_no, (E0, E1))
        e = e0 + (e1 - e0) * pt / (POINTS - 1)
        with open(self.spec, "a") as f:
            f.write(f"{e:.6f} 1.0 100.0 10.0 10.0\n")
        img = np.zeros((H, W), dtype=np.uint16)
        img[:, W // 2] = 60000
        tifffile.imwrite(os.path.join(self.workdir, f"fake.spec_scan{scan_no}_point{pt:04d}.tif"), img)

    def run_scan(self, scan_no):
        self.start_scan(scan_no)
        for pt in range(POINTS):
            self.add_point(scan_no, pt)

    def run_snapshot_scan(self, scan_no, energy=E0):
        self.start_scan(scan_no, e0=energy, e1=energy)
        for pt in range(POINTS):
            self.add_point(scan_no, pt)

    def start_rxes_scan(self, scan_no, n_emission=2, n_incident=2):
        """Write an ``rxesamesh`` header: outer loop merixE (emission,
        analyzer), inner loop kohzuE (incident) -- matches the real
        beamline's raster order (kohzuE resets and sweeps low->high at
        every merixE step)."""
        if not hasattr(self, "_rxes_grids"):
            self._rxes_grids = {}
        self._rxes_grids[scan_no] = (n_emission, n_incident)
        with open(self.spec, "a") as f:
            f.write(
                f"#S {scan_no} rxesamesh merixE {RXES_EMISSION_START} {RXES_EMISSION_END} "
                f"{n_emission - 1} kohzuE {RXES_INCIDENT_START} {RXES_INCIDENT_END} "
                f"{n_incident - 1} 0.1\n"
            )
            f.write("#N 5\n")
            f.write("#L KohzuE merixE i0 i2 mmepin1\n")
            f.write(f"#B {' '.join(XB_FIELDS)}\n")
            f.write("#D 2026-09-27 12:00:00\n")

    def add_rxes_point(self, scan_no, point_index):
        """Append the scandata row + TIFF for one raster point (0-based,
        row-major: point_index = i * n_incident + j, i=emission row,
        j=incident column)."""
        n_emission, n_incident = self._rxes_grids[scan_no]
        i, j = divmod(point_index, n_incident)
        merixE = RXES_EMISSION_START + (RXES_EMISSION_END - RXES_EMISSION_START) * i / max(n_emission - 1, 1)
        kohzuE = RXES_INCIDENT_START + (RXES_INCIDENT_END - RXES_INCIDENT_START) * j / max(n_incident - 1, 1)
        with open(self.spec, "a") as f:
            f.write(f"{kohzuE:.6f} {merixE:.6f} 1.0 100.0 10.0\n")
        img = np.zeros((H, W), dtype=np.uint16)
        img[:, W // 2] = 60000
        tifffile.imwrite(
            os.path.join(self.workdir, f"fake.spec_scan{scan_no}_point{point_index:04d}.tif"), img
        )

    def run_rxes_scan(self, scan_no, n_emission=2, n_incident=2):
        self.start_rxes_scan(scan_no, n_emission=n_emission, n_incident=n_incident)
        for pt in range(n_emission * n_incident):
            self.add_rxes_point(scan_no, pt)


@pytest.fixture()
def gui(qapp, tmp_path, monkeypatch):
    from rixsviewer.model import user_settings
    from rixsviewer.model.binning_model import RixsBinningModel
    from rixsviewer.rixsviewer_gui import RixsViewerGUI

    # RixsViewerGUI unconditionally reads/writes $HOME/.rixsviewer/settings.json
    # (splitter sizes, last-used spec file/TIFF folder) -- redirect it to a
    # throwaway path so tests never clobber the real user's settings.
    settings_dir = tmp_path / ".rixsviewer"
    monkeypatch.setattr(user_settings, "SETTINGS_DIR", settings_dir)
    monkeypatch.setattr(user_settings, "SETTINGS_FILE", settings_dir / "settings.json")

    beamline = FakeBeamline(str(tmp_path))

    # EPICS connectivity is irrelevant to dataset eviction; skip the CA timeout
    original = RixsBinningModel.check_pv_connection
    RixsBinningModel.check_pv_connection = lambda self, timeout=0.5: False
    try:
        g = RixsViewerGUI(spec_filename=beamline.spec, tiff_folder=beamline.workdir)
    finally:
        RixsBinningModel.check_pv_connection = original

    # process_binning launches a QThreadPool worker; these tests exercise the
    # controller's dataset-switching logic, so keep the worker out of the loop.
    g.process_binning = lambda: None
    g.beamline = beamline
    return g
