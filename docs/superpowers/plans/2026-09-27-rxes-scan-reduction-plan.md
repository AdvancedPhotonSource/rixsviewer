# RXES Scan Data Reduction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add incremental, memory-bounded data reduction for `RXESScan` (nested incident×emission energy mesh) scans, producing a 2D RXES map that updates in real time as frames arrive during acquisition.

**Architecture:** A new `RixsRxesScanDataset` class, structurally parallel to (not a subclass of) `RixsScanTiffDataset`, sharing common scan-metadata/filename-tracking behavior via a new `TiffScanDatasetMixin`. Each newly-arrived TIFF is reduced (ROI-sum + Rowland pixel→energy mapping anchored on that frame's own `merixE` value — extracted from the existing `_compute_energy_axis` into a shared pure function) and immediately accumulated into a preallocated 2D array, then its raw pixels are discarded. `RixsSpecTable` picks the right dataset class per scan type; `bin_data_wrap()` keeps the same call signature so `RixsViewerGUI.process_binning()` needs no change except a small routing guard for the differently-shaped result.

**Tech Stack:** Python, NumPy, pandas, silx (SpecFile), tifffile, PySide6/Qt, pytest.

**Spec:** `docs/superpowers/specs/2026-09-27-rxes-scan-reduction-design.md`

## Global Constraints

- The Rowland pixel→energy formula extraction (Task 1) must not change `EnergyScan`/`SnapshotScan` output — it is a pure refactor, verified by a regression test before and after.
- RXES scans must never hold a resident raw-frame buffer proportional to scan size — memory stays at the size of the reduced 2D accumulator (tens of KB–few MB) regardless of frame count, per the design's ~655MB-stack finding for scan 11.
- `RixsRxesScanDataset.bin_data_wrap(metadata_source=..., progress_callback=..., **kwargs)` must keep the exact call signature `RixsScanTiffDataset.bin_data_wrap()` uses today, so `RixsViewerGUI.process_binning()`'s call site requires no change.
- Axis roles are fixed and confirmed by beamline staff: incident energy = `kohzuE`, emission/analyzer energy = `merixE`. Do not swap these.
- `save_to_file()` on `RixsRxesScanDataset` is a no-op (log-only) for this phase — no persistence format is defined yet. Do not implement one.
- Positional alignment between sorted TIFF filename order and `scandata` row order is a known, pre-existing, accepted limitation (shared with `EnergyScan`) — not solved in this plan.
- This project's environment for running tests is `/home/beams/MQICHU/.conda/envs/d2603_rixs` (per `AGENTS.md`); tests run via `pytest tests/` from the repo root.

## Review Focus

- An `RXESScan` header is recognized (and `process_binning` fires) before any scandata rows exist yet — must raise the same `"...no scandata rows..."` message the GUI's existing `on_error` handler already treats as a benign warning, not crash differently.
- An RXES scan is aborted/stalls partway through the grid — the accumulator stays partially filled and `is_complete()` correctly reports `False`; nothing crashes.
- More frames arrive than the header's declared grid size (e.g. a restarted scan with a changed point count) — the extra frame is skipped and logged, never written out of bounds or into the wrong column.
- A calibration parameter (`DeltaD`, `TiltAngle`, etc.) changes mid-scan after frames have already been accumulated — the accumulator resets and replays every already-known file exactly once, not double-counted.
- `RixsViewerGUI.process_binning()`'s result handler receives a 2D-map-shaped result instead of a 1D spectrum — it routes away from the 1D plot call instead of crashing on a shape mismatch.

---

## File Structure

- Modify: `src/rixsviewer/model/utils.py` — extract `compute_frame_energy_axis()`.
- Modify: `src/rixsviewer/model/scan_dataset.py` — extract `TiffScanDatasetMixin`.
- Modify: `src/rixsviewer/model/spec_parsers.py` — propagate incident/emission header fields into `parse_single_scan()`'s return dict.
- Create: `src/rixsviewer/model/rxes_dataset.py` — new `RixsRxesScanDataset` class.
- Modify: `src/rixsviewer/model/spec_table.py` — construct `RixsRxesScanDataset` for `RXESScan` rows.
- Modify: `src/rixsviewer/rixsviewer_gui.py` — guard `process_binning()`'s result routing.
- Modify: `tests/conftest.py` — add `FakeBeamline.start_rxes_scan()`/`add_rxes_point()`/`run_rxes_scan()`.
- Create: `tests/test_frame_energy_axis.py`
- Create: `tests/test_tiff_scan_dataset_mixin.py`
- Create: `tests/test_rxes_dataset.py`
- Create: `tests/test_spec_table_rxes.py`

---

### Task 1: Extract the shared Rowland pixel→energy formula

**Files:**
- Modify: `src/rixsviewer/model/utils.py:521-528` (inside `_compute_energy_axis`)
- Test: `tests/test_frame_energy_axis.py`

**Interfaces:**
- Produces: `compute_frame_energy_axis(energy_ref, xaxis, Eb, Ra, DeltaD) -> np.ndarray` shape `(n, width)`, unsorted, in `src/rixsviewer/model/utils.py`. `energy_ref` is array-like shape `(n,)` (per-frame analyzer/reference energy, keV); `xaxis` is `(width,)` (pixel offsets from the reference pixel); `Eb`, `Ra`, `DeltaD` are floats. Used by Task 4.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_frame_energy_axis.py
import numpy as np

from rixsviewer.model.utils import compute_frame_energy_axis


def test_matches_hand_computed_rowland_formula():
    # Values must satisfy Eb <= energy_ref (near-backscattering geometry).
    energy_ref = np.array([11.190, 11.195])
    xaxis = np.array([-2.0, -1.0, 0.0, 1.0, 2.0])
    Eb = 11.184
    Ra = 1998.0
    DeltaD = 0.022

    theta_b = np.arcsin(Eb / energy_ref)
    scale = Eb / (2 * Ra) / np.tan(theta_b)
    expected = energy_ref.reshape(-1, 1) - np.outer(scale, xaxis) * DeltaD

    result = compute_frame_energy_axis(energy_ref, xaxis, Eb, Ra, DeltaD)

    np.testing.assert_allclose(result, expected)


def test_single_frame_shape():
    result = compute_frame_energy_axis(
        [11.190], np.arange(5) - 2, 11.184, 1998.0, 0.022
    )
    assert result.shape == (1, 5)


def test_accepts_plain_list_input():
    result = compute_frame_energy_axis(
        [11.190, 11.195], [-1.0, 0.0, 1.0], 11.184, 1998.0, 0.022
    )
    assert result.shape == (2, 3)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_frame_energy_axis.py -v`
Expected: FAIL with `ImportError: cannot import name 'compute_frame_energy_axis'`

- [ ] **Step 3: Implement the function**

In `src/rixsviewer/model/utils.py`, add this function directly above `def _compute_energy_axis(`:

```python
def compute_frame_energy_axis(energy_ref, xaxis, Eb, Ra, DeltaD):
    """Map detector pixel offsets to photon energy via Rowland-circle geometry.

    Parameters
    ----------
    energy_ref : array-like, shape (n,)
        Per-frame analyzer/reference energy (keV) -- the physical energy
        the reference pixel (offset 0 in *xaxis*) corresponds to for that
        frame.
    xaxis : array-like, shape (width,)
        Pixel offset from the reference pixel.
    Eb : float
        Analyzer backscattering energy (keV).
    Ra : float
        Rowland circle radius (mm).
    DeltaD : float
        Nominal pixel pitch (mm).

    Returns
    -------
    ndarray, shape (n, width)
        Per-frame energy axis (keV), in the same (unsorted) pixel order
        as *xaxis*.
    """
    energy_ref = np.asarray(energy_ref, dtype=float)
    xaxis = np.asarray(xaxis, dtype=float)
    theta_b = np.arcsin(Eb / energy_ref)
    energy_cen = energy_ref.reshape(-1, 1)
    scale = Eb / (2 * Ra) / np.tan(theta_b)
    return energy_cen - np.outer(scale, xaxis) * DeltaD
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_frame_energy_axis.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Refactor `_compute_energy_axis` to use the new function**

In `src/rixsviewer/model/utils.py`, replace this block inside `_compute_energy_axis` (currently lines ~521-525):

```python
    theta_b = np.arcsin(Eb / merixE)
    energy_cen = merixE.reshape(-1, 1)
    scale = Eb / (2 * Ra) / np.tan(theta_b)

    energy_axis = energy_cen - np.outer(scale, xaxis) * DeltaD
    idx = np.argsort(energy_axis, axis=1)
```

with:

```python
    energy_axis = compute_frame_energy_axis(merixE, xaxis, Eb, Ra, DeltaD)
    idx = np.argsort(energy_axis, axis=1)
```

- [ ] **Step 6: Run the full test suite to confirm no regression**

Run: `pytest tests/ -v`
Expected: PASS (all existing tests, plus the 3 new ones)

- [ ] **Step 7: Commit**

```bash
git add src/rixsviewer/model/utils.py tests/test_frame_energy_axis.py
git commit -m "refactor: extract compute_frame_energy_axis for reuse by RXES reduction"
```

---

### Task 2: Extract `TiffScanDatasetMixin`

**Files:**
- Modify: `src/rixsviewer/model/scan_dataset.py`
- Test: `tests/test_tiff_scan_dataset_mixin.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `TiffScanDatasetMixin` class in `src/rixsviewer/model/scan_dataset.py`, providing `update_scan_info(scan_pack)`, `refresh_tiff_filenames()`, `get_qtableview_display_data(col)`, `is_complete()`, `apply_tilt_angle(data, tilt_angle=0, tilt_order=1)`, `get_table_model()`. Host classes (`RixsScanTiffDataset`, and `RixsRxesScanDataset` in Task 3) must set in their own `__init__`: `scan_index`, `spec_fname`, `tif_folder`, `scan_info=None`, `unloaded_filenames=[]`, `_saved=False`, `_model=None`. Used by Task 3.

This task moves six existing, already-working methods out of `RixsScanTiffDataset` into a new mixin, verbatim (no behavior change). `is_complete()` already has test coverage in `tests/test_backfill_unprocessed_scans.py::TestIsComplete` — that suite passing after the move is part of this task's verification.

- [ ] **Step 1: Write regression tests for the currently-untested mixin methods**

```python
# tests/test_tiff_scan_dataset_mixin.py
from rixsviewer.model.scan_dataset import RixsScanTiffDataset


def _dset_with_scan_info(scan_info):
    dset = RixsScanTiffDataset(0, "fake.spec", "/tmp", 1)
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
        dset = RixsScanTiffDataset(0, spec_path, str(tmp_path), 1)
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
```

- [ ] **Step 2: Run tests to verify they pass against the current (pre-refactor) code**

Run: `pytest tests/test_tiff_scan_dataset_mixin.py -v`
Expected: PASS (5 tests) — this pins current behavior before moving it.

- [ ] **Step 3: Extract the mixin**

In `src/rixsviewer/model/scan_dataset.py`, add a new class right after the imports/logger (before `class RixsScanTiffDataset`):

```python
class TiffScanDatasetMixin:
    """Shared scan-metadata/filename-tracking behavior for scan-dataset
    classes that read TIFF files named ``<basename>_scan<N>_point<k>.tif``.

    Host classes must set, in their own ``__init__``: ``scan_index``,
    ``spec_fname``, ``tif_folder``, ``scan_info`` (``None`` initially),
    ``unloaded_filenames`` (``[]`` initially), ``_saved`` (``False``
    initially), ``_model`` (``None`` initially).
    """

    def update_scan_info(self, scan_pack):
        """
        Refresh scan metadata and track newly-arrived TIFF files.

        If the TIFF point count has changed since the last update,
        :attr:`unloaded_filenames` is populated with the filenames not
        yet present in the cached data so that a subsequent read can
        load only the new frames.

        Parameters
        ----------
        scan_pack : silx.io.specfile.Scan
            Current state of the scan from the SPEC file.
        """
        scan_info = parse_single_scan(
            scan_pack,
            self.spec_fname,
            self.tif_folder,
        )
        n_new_spec_rows = len(scan_info["scandata"])
        n_old_spec_rows = len(self.scan_info["scandata"]) if self.scan_info is not None else -1
        if (
            self.scan_info is None
            or self.scan_info["tiff_points"] != scan_info["tiff_points"]
            or n_new_spec_rows != n_old_spec_rows
        ):
            prev_filenames = (
                [] if self.scan_info is None else self.scan_info["filenames"]
            )
            unloaded_filenames = [
                fn for fn in scan_info["filenames"] if fn not in prev_filenames
            ]
            self.unloaded_filenames = unloaded_filenames
            self.scan_info = scan_info
            if unloaded_filenames or n_new_spec_rows > n_old_spec_rows:
                self._saved = False  # new data arrived; previous save is stale

    def refresh_tiff_filenames(self):
        """Re-glob tiff files to pick up NFS-lagged files when SPEC is already done.

        Returns True if new files were found, False otherwise.
        Stops early once tiff_points >= spec_points (all expected files have landed).
        """
        if self.scan_info is None:
            return False
        if self.scan_info["tiff_points"] >= self.scan_info["spec_points"]:
            return False
        basename = Path(self.spec_fname).name
        filenames = sorted(
            (str(p) for p in Path(self.tif_folder).glob(f"{basename}_scan{self.scan_index}_point*.tif")),
            key=tiff_point_index,
        )
        new_files = [fn for fn in filenames if fn not in self.scan_info["filenames"]]
        if not new_files:
            return False
        self.unloaded_filenames.extend(new_files)
        self.scan_info["filenames"] = filenames
        self.scan_info["tiff_points"] = len(filenames)
        self._saved = False  # new tiff files arrived; previous save is stale
        return True

    def get_qtableview_display_data(self, col):
        """
        Return the display value for a specific table column.

        Column mapping:

        =====  ==============
        Index  Field
        =====  ==============
        0      scan_number
        1      scan_type
        2      spec_points
        3      tiff_points
        =====  ==============

        Parameters
        ----------
        col : int
            Zero-based column index.

        Returns
        -------
        object
            The corresponding value from :attr:`scan_info`.
        """
        key = {
            0: "scan_number",
            1: "scan_type",
            2: "spec_points",
            3: "tiff_points",
        }[col]
        return self.scan_info[key]

    def is_complete(self):
        """Whether every expected SPEC row and TIFF frame has arrived for this scan."""
        si = self.scan_info
        if si is None:
            return False
        return (
            si["tiff_points"] > 0
            and si["tiff_points"] == si["spec_points"]
            and len(si["scandata"]) == si["spec_points"]
        )

    def apply_tilt_angle(self, data, tilt_angle=0, tilt_order=1):
        Ylow, Yhigh = (
            self.scan_info["metadata"]["Ylow"],
            self.scan_info["metadata"]["Yhigh"],
        )
        if data.ndim == 2:
            return apply_subpixel_shear_3d(
                data[np.newaxis, :, :], Ylow, Yhigh, tilt_angle, tilt_order
            )[0]
        else:
            return apply_subpixel_shear_3d(
                data[np.newaxis, :, :], Ylow, Yhigh, tilt_angle, tilt_order
            )

    def get_table_model(self):
        """
        Return (or lazily create) the :class:`RixsScanImageTable` for this scan.

        Returns
        -------
        RixsScanImageTable
            Qt table model listing the TIFF filenames for this scan.
        """
        if self._model is None:
            self._model = RixsScanImageTable(self.scan_info["filenames"])
        else:
            self._model.update_fnames(self.scan_info["filenames"])
        return self._model
```

Then delete these six method bodies from `RixsScanTiffDataset` (they now live only in the mixin), and change the class declaration:

```python
class RixsScanTiffDataset(TiffScanDatasetMixin):
```

`RixsScanTiffDataset` keeps: `__init__`, `get_data_for_display`, `_prepare_inputs`, `bin_data_wrap`, `save_to_file`, `fit_pixel_size_wrap`, `linesearch_to_optimize_parameter`, `__len__`, `read_tiff_data`, `release_data`.

- [ ] **Step 4: Run tests to verify they still pass after the move**

Run: `pytest tests/ -v`
Expected: PASS (all tests, including `tests/test_tiff_scan_dataset_mixin.py` and the pre-existing `TestIsComplete` in `tests/test_backfill_unprocessed_scans.py`)

- [ ] **Step 5: Commit**

```bash
git add src/rixsviewer/model/scan_dataset.py tests/test_tiff_scan_dataset_mixin.py
git commit -m "refactor: extract TiffScanDatasetMixin for reuse by RXES dataset"
```

---

### Task 3: Propagate RXES header fields + `RixsRxesScanDataset` skeleton

**Files:**
- Modify: `src/rixsviewer/model/spec_parsers.py` (`parse_single_scan`)
- Create: `src/rixsviewer/model/rxes_dataset.py`
- Modify: `tests/conftest.py`
- Test: `tests/test_rxes_dataset.py`

**Interfaces:**
- Consumes: `TiffScanDatasetMixin` (Task 2), `tiff_point_index`, `parse_single_scan` from `spec_parsers.py`.
- Produces: `scan_info["incident_start"]`, `scan_info["incident_end"]`, `scan_info["incident_points"]`, `scan_info["emission_start"]`, `scan_info["emission_end"]`, `scan_info["emission_points"]` (all `None` for non-RXES scan types). `RixsRxesScanDataset(row_position, spec_fname, tif_folder, scan_index)` class in `src/rixsviewer/model/rxes_dataset.py`, implementing the `TiffScanDatasetMixin` interface plus `bin_data_wrap()` (built in Task 4). This task builds the constructor and the accumulator-reset machinery only. Used by Task 4 and Task 5.

- [ ] **Step 1: Write the failing test for header field propagation**

```python
# add to tests/test_spec_parsers.py
from silx.io.specfile import SpecFile

from rixsviewer.model.spec_parsers import get_scan_header, parse_single_scan, tiff_point_index


def test_get_scan_header_classifies_rxesamesh_as_rxesscan(tmp_path):
    spec_path = tmp_path / "fake.spec"
    spec_path.write_text(
        "#F fake session\n"
        "#S 1  rxesamesh merixE 11.216 11.2134 72 kohzuE 12.652 12.66 18 1\n"
        "#D 2026-09-23 12:00:00\n"
        "#N 5\n"
        "#L KohzuE merixE i0 i2 mmepin1\n"
    )
    scan = next(iter(SpecFile(str(spec_path))))

    header = get_scan_header(scan)

    assert header["scan_type"] == "RXESScan"
    assert header["incident_start"] == 12.652
    assert header["incident_end"] == 12.66
    assert header["incident_points"] == 19
    assert header["emission_start"] == 11.216
    assert header["emission_end"] == 11.2134
    assert header["emission_points"] == 73
    assert header["steps"] == 19 * 73


def test_tiff_point_index_sorts_numerically_past_three_digits():
    # Regression test for the bug fixed in commit history: filenames are
    # zero-padded to 3 digits only (point001..point999, then point1000
    # unpadded), so a plain lexicographic sort silently reorders frames
    # once a scan exceeds ~100 points -- e.g. "..._point182.tif" would
    # sort between "..._point1819.tif" and "..._point1820.tif".
    names = [
        "23Sept2026c_scan11_point1819.tif",
        "23Sept2026c_scan11_point182.tif",
        "23Sept2026c_scan11_point1820.tif",
        "23Sept2026c_scan11_point001.tif",
        "23Sept2026c_scan11_point099.tif",
        "23Sept2026c_scan11_point100.tif",
    ]

    ordered = sorted(names, key=tiff_point_index)

    assert ordered == [
        "23Sept2026c_scan11_point001.tif",
        "23Sept2026c_scan11_point099.tif",
        "23Sept2026c_scan11_point100.tif",
        "23Sept2026c_scan11_point182.tif",
        "23Sept2026c_scan11_point1819.tif",
        "23Sept2026c_scan11_point1820.tif",
    ]


def _write_rxes_spec(tmp_path):
    spec_path = tmp_path / "fake.spec"
    spec_path.write_text(
        "#F fake session\n"
        "#S 1  rxesamesh merixE 11.190 11.200 2 kohzuE 12.650 12.660 3 0.1\n"
        "#D 2026-09-27 12:00:00\n"
        "#N 5\n"
        "#L KohzuE merixE i0 i2 mmepin1\n"
        "#B Analyzer_EB_keV = 11.184\n"
    )
    return str(spec_path)


def test_parse_single_scan_propagates_rxes_axis_fields(tmp_path):
    spec_path = _write_rxes_spec(tmp_path)
    scan = next(iter(SpecFile(spec_path)))

    info = parse_single_scan(scan, spec_path, str(tmp_path))

    assert info["incident_start"] == 12.650
    assert info["incident_end"] == 12.660
    assert info["incident_points"] == 4
    assert info["emission_start"] == 11.190
    assert info["emission_end"] == 11.200
    assert info["emission_points"] == 3


def test_parse_single_scan_leaves_rxes_fields_none_for_energy_scan(tmp_path):
    spec_path = tmp_path / "fake.spec"
    spec_path.write_text(
        "#F fake session\n"
        "#S 1  ascan  merixE 11.190 11.200  2 0.1\n"
        "#D 2026-09-27 12:00:00\n"
        "#N 5\n"
        "#L merixE i0 i2 mmepin1\n"
        "#B Analyzer_EB_keV = 11.184\n"
    )
    scan = next(iter(SpecFile(str(spec_path))))

    info = parse_single_scan(scan, str(spec_path), str(tmp_path))

    assert info["incident_points"] is None
    assert info["emission_points"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_spec_parsers.py -v`
Expected: `test_get_scan_header_classifies_rxesamesh_as_rxesscan` and
`test_tiff_point_index_sorts_numerically_past_three_digits` PASS immediately
(pinning already-working behavior from earlier work); `test_parse_single_scan_propagates_rxes_axis_fields`
and `test_parse_single_scan_leaves_rxes_fields_none_for_energy_scan` FAIL with `KeyError: 'incident_start'`

- [ ] **Step 3: Propagate the fields**

In `src/rixsviewer/model/spec_parsers.py`, in `parse_single_scan`'s return dict, add:

```python
    return {
        "scan_number": scan.number,
        "scan_type": header["scan_type"],
        "spec_points": header["steps"],
        "exposure_time": header["exposure_time"],
        "start": header["start"],
        "end": header["end"],
        "tiff_points": len(filenames),
        "metadata": _get_metadata(metadata_str),
        "scandata": _get_scandata(scan),
        "filenames": filenames,
        "incident_start": header.get("incident_start"),
        "incident_end": header.get("incident_end"),
        "incident_points": header.get("incident_points"),
        "emission_start": header.get("emission_start"),
        "emission_end": header.get("emission_end"),
        "emission_points": header.get("emission_points"),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_spec_parsers.py -v`
Expected: PASS (all 4 new tests, plus the 2 pre-existing `_get_metadata` tests)

- [ ] **Step 5: Commit**

```bash
git add src/rixsviewer/model/spec_parsers.py tests/test_spec_parsers.py
git commit -m "test: pin RXES header parsing behavior; propagate incident/emission axis fields"
```

- [ ] **Step 6: Add RXES scan helpers to the shared test fixture**

In `tests/conftest.py`, add near the top (alongside `E0, E1, POINTS`):

```python
RXES_EMISSION_START, RXES_EMISSION_END = 11.190, 11.200  # merixE (analyzer/emission)
RXES_INCIDENT_START, RXES_INCIDENT_END = 12.650, 12.660  # kohzuE (incident)
```

Add these methods to `FakeBeamline` (after `run_scan`):

```python
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
```

- [ ] **Step 7: Write the failing test for the `RixsRxesScanDataset` skeleton**

```python
# tests/test_rxes_dataset.py
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
```

- [ ] **Step 8: Run test to verify it fails**

Run: `pytest tests/test_rxes_dataset.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rixsviewer.model.rxes_dataset'`

- [ ] **Step 9: Implement the `RixsRxesScanDataset` skeleton**

Create `src/rixsviewer/model/rxes_dataset.py`:

```python
# Copyright © UChicago Argonne LLC
# See LICENSE file for details
import logging

import numpy as np

from .scan_dataset import TiffScanDatasetMixin
from .utils import compute_frame_energy_axis

logger = logging.getLogger(__name__)


class RixsRxesScanDataset(TiffScanDatasetMixin):
    """Incremental 2D (incident energy x emission energy) map builder for
    an ``RXESScan``.

    Unlike :class:`~.scan_dataset.RixsScanTiffDataset`, this class never
    keeps a resident raw TIFF stack: each newly-arrived frame is reduced
    (ROI-sum + Rowland pixel-to-energy mapping anchored on that frame's
    own ``merixE`` value) and accumulated into a small persistent 2D map,
    then its raw pixels are discarded. See
    ``docs/superpowers/specs/2026-09-27-rxes-scan-reduction-design.md``.

    Parameters
    ----------
    row_position : int
        Zero-based row index of this scan in the parent
        :class:`~.spec_table.RixsSpecTable` model.
    spec_fname : str
        Path to the SPEC data file.
    tif_folder : str
        Directory containing the TIFF image files.
    scan_index : int
        Scan index in the SPEC file.
    """

    #: calibration kwargs that require rebuilding the accumulator when changed
    _CALIBRATION_KEYS = (
        "DeltaD", "RefL", "Eb", "Ra", "Ylow", "Yhigh", "Acrystalsize",
        "TiltAngle", "TiltOrder", "NEnergyBins", "force_NEnergyBins",
    )

    def __init__(self, row_position, spec_fname, tif_folder, scan_index):
        self.row_position = row_position
        self.scan_index = scan_index
        self.spec_fname = spec_fname
        self.tif_folder = tif_folder
        self.scan_info = None
        self.unloaded_filenames = []
        self._saved = False
        self._model = None
        self.bin_result = None

        self._n_processed = 0
        self._map_key = None
        self._xsize = None
        self.emission_axis = None
        self.incident_axis = None
        self.intensity = None
        self.sample = None

    def _merge_binning_kwargs(self, metadata_source, kwargs):
        """Merge caller kwargs with SpecFile metadata, matching
        :meth:`~.scan_dataset.RixsScanTiffDataset._prepare_inputs`'s
        merge order and force-override behavior."""
        assert metadata_source in ("SpecFile", "PV", "USER"), (
            "metadata_source not supported."
        )
        merged = dict(kwargs)
        if metadata_source == "SpecFile":
            merged.update(self.scan_info["metadata"])
            if kwargs.get("force_NEnergyBins") and "NEnergyBins" in kwargs:
                merged["NEnergyBins"] = kwargs["NEnergyBins"]
        return merged

    def _reset_accumulator(self, merged_kwargs):
        """(Re)build the shared emission axis and zero the 2D accumulator.

        Also marks every currently-known file as unloaded, so the next
        :meth:`bin_data_wrap` call replays the whole scan under the new
        calibration.
        """
        si = self.scan_info
        emission_start, emission_end = si["emission_start"], si["emission_end"]
        incident_start, incident_end = si["incident_start"], si["incident_end"]
        n_incident = si["incident_points"]

        DeltaD = merged_kwargs["DeltaD"]
        Eb = merged_kwargs["Eb"]
        Ra = merged_kwargs["Ra"]
        Acrystalsize = merged_kwargs["Acrystalsize"]
        NEnergyBins = merged_kwargs.get("NEnergyBins") or 0
        force_NEnergyBins = merged_kwargs.get("force_NEnergyBins", False)

        xsize = int(Acrystalsize / DeltaD)
        if xsize <= 0:
            raise ValueError(
                f"xsize must be positive, check Acrystalsize {Acrystalsize} and DeltaD {DeltaD}"
            )
        probe_xaxis = np.arange(-xsize, xsize + 1)
        probe_energy = np.array([(emission_start + emission_end) / 2.0])
        probe_axis = compute_frame_energy_axis(probe_energy, probe_xaxis, Eb, Ra, DeltaD)
        delta_native = float(np.mean(np.abs(np.diff(probe_axis, axis=1))))

        e_min, e_max = min(emission_start, emission_end), max(emission_start, emission_end)
        if NEnergyBins >= 1:
            delta = (e_max - e_min) / NEnergyBins
            if delta < delta_native and not force_NEnergyBins:
                delta = delta_native
        else:
            delta = delta_native

        n_bins = int((e_max - e_min) / delta) + 1
        self.emission_axis = np.linspace(e_min, e_max, n_bins)
        self.incident_axis = np.linspace(
            min(incident_start, incident_end), max(incident_start, incident_end), n_incident
        )
        self.intensity = np.zeros((n_bins, n_incident))
        self.sample = np.zeros((n_bins, n_incident))
        self._xsize = xsize
        self._n_processed = 0
        self.unloaded_filenames = list(si["filenames"])
        logger.info(
            "Scan %d: RXES accumulator (re)built: %d emission bins x %d incident columns",
            self.scan_index, n_bins, n_incident,
        )
```

- [ ] **Step 10: Run test to verify it passes**

Run: `pytest tests/test_rxes_dataset.py -v`
Expected: PASS (4 tests: `TestConstruction`, `TestAccumulatorReset`, and the two
`TestIsComplete` cases, which exercise the mixin's already-implemented
`is_complete()` against RXES-shaped `scan_info` for the first time)

- [ ] **Step 11: Commit**

```bash
git add src/rixsviewer/model/rxes_dataset.py tests/test_rxes_dataset.py tests/conftest.py
git commit -m "feat: add RixsRxesScanDataset skeleton with accumulator reset"
```

---

### Task 4: Incremental frame processing in `bin_data_wrap`

**Files:**
- Modify: `src/rixsviewer/model/rxes_dataset.py`
- Test: `tests/test_rxes_dataset.py`

**Interfaces:**
- Consumes: `_preprocess_frames`, `fix_bad_pixels`, `apply_subpixel_shear_3d` from `.utils`; `compute_frame_energy_axis` (Task 1); `_merge_binning_kwargs`/`_reset_accumulator` (Task 3).
- Produces: `RixsRxesScanDataset.bin_data_wrap(metadata_source="SpecFile", progress_callback=None, **kwargs) -> dict` with keys `kind` (`"rxes_map"`), `emission_axis`, `incident_axis`, `intensity`, `sample`, `intensity_norm`. Also sets `self.bin_result` to this dict. Used by Task 5 (GUI routing) and Task 6 (`RixsSpecTable` wiring, indirectly via real usage).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_rxes_dataset.py`:

```python
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
        # points 0,1 = emission row i=0, both incident columns j=0,1
        assert list(dset.sample.sum(axis=0)) == [1.0, 1.0]
        assert dset._n_processed == 2

    def test_second_call_only_processes_newly_arrived_frames(self, tmp_path):
        dset, beamline = _make_dataset(tmp_path, n_emission=2, n_incident=2, n_points=2)
        dset.bin_data_wrap(**SPECFILE_KWARGS)
        assert dset.unloaded_filenames == []

        beamline.add_rxes_point(1, 2)
        beamline.add_rxes_point(1, 3)
        dset.update_scan_info(_scan_pack(beamline.spec, 1))
        assert len(dset.unloaded_filenames) == 2

        dset.bin_data_wrap(**SPECFILE_KWARGS)

        assert dset._n_processed == 4
        assert list(dset.sample.sum(axis=0)) == [2.0, 2.0]


class TestRecalibration:
    def test_changing_deltad_resets_and_replays_without_double_counting(self, tmp_path):
        dset, beamline = _make_dataset(tmp_path, n_emission=2, n_incident=2, n_points=4)
        dset.bin_data_wrap(**SPECFILE_KWARGS)
        assert dset._n_processed == 4

        kwargs = dict(dset.scan_info["metadata"])
        kwargs["DeltaD"] = kwargs["DeltaD"] * 2
        dset.bin_data_wrap(metadata_source="USER", **kwargs)

        assert dset._n_processed == 4
        assert list(dset.sample.sum(axis=0)) == [2.0, 2.0]


class TestOutOfRangeFrame:
    def test_extra_frame_beyond_grid_size_is_skipped_not_crashed(self, tmp_path):
        dset, beamline = _make_dataset(tmp_path, n_emission=2, n_incident=2, n_points=4)
        beamline.add_rxes_point(1, 4)  # 5th point exceeds the declared 2x2 grid
        dset.update_scan_info(_scan_pack(beamline.spec, 1))

        result = dset.bin_data_wrap(**SPECFILE_KWARGS)  # must not raise

        assert result["kind"] == "rxes_map"
        assert dset._n_processed == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_rxes_dataset.py -v`
Expected: FAIL with `AttributeError: 'RixsRxesScanDataset' object has no attribute 'bin_data_wrap'`

- [ ] **Step 3: Implement `bin_data_wrap`**

In `src/rixsviewer/model/rxes_dataset.py`, replace the top of the import block:

```python
import logging

import numpy as np

from .scan_dataset import TiffScanDatasetMixin
from .utils import compute_frame_energy_axis
```

with:

```python
import logging

import numpy as np
import tifffile

from .scan_dataset import TiffScanDatasetMixin
from .utils import _preprocess_frames, apply_subpixel_shear_3d, compute_frame_energy_axis, fix_bad_pixels
```

Add this method to `RixsRxesScanDataset`, after `_reset_accumulator`:

```python
    def bin_data_wrap(self, metadata_source="SpecFile", progress_callback=None, **kwargs):
        """(Re)process any newly-arrived frames into the 2D RXES map.

        Parameters
        ----------
        metadata_source : {'SpecFile', 'PV', 'USER'}
            Source of instrument parameters, matching
            :meth:`~.scan_dataset.RixsScanTiffDataset.bin_data_wrap`.
        progress_callback : callable, optional
            Called with an integer percent-complete (0-100).
        **kwargs
            Additional/override keyword arguments (calibration params
            when *metadata_source* is not ``'SpecFile'``).

        Returns
        -------
        dict
            Keys: ``kind`` (``'rxes_map'``), ``emission_axis``,
            ``incident_axis``, ``intensity``, ``sample``, ``intensity_norm``.
        """
        if self.scan_info is None or self.scan_info["scandata"].empty:
            raise ValueError(
                f"Scan {self.scan_index} has no scandata rows; "
                "cannot run processing on an empty dataset."
            )

        merged_kwargs = self._merge_binning_kwargs(metadata_source, kwargs)
        key = tuple(merged_kwargs.get(k) for k in self._CALIBRATION_KEYS)
        if key != self._map_key or self.emission_axis is None:
            self._reset_accumulator(merged_kwargs)
            self._map_key = key

        Ylow = merged_kwargs["Ylow"]
        Yhigh = merged_kwargs["Yhigh"]
        RefL = merged_kwargs["RefL"]
        Eb = merged_kwargs["Eb"]
        Ra = merged_kwargs["Ra"]
        DeltaD = merged_kwargs["DeltaD"]
        TiltAngle = merged_kwargs.get("TiltAngle", 0)
        TiltOrder = merged_kwargs.get("TiltOrder", 1)

        n_incident = self.scan_info["incident_points"]
        total_points = self.scan_info["incident_points"] * self.scan_info["emission_points"]
        merixE_col = np.asarray(self.scan_info["scandata"]["merixE"], dtype=float)

        to_process = list(self.unloaded_filenames)
        self.unloaded_filenames = []
        n_total_for_progress = max(total_points, 1)

        for fname in to_process:
            frame_position = self._n_processed
            self._n_processed += 1
            if frame_position >= total_points:
                logger.warning(
                    "Scan %d: frame position %d exceeds the expected grid size "
                    "(%d); skipping %s",
                    self.scan_index, frame_position, total_points, fname,
                )
                continue

            j = frame_position % n_incident
            merix_value = merixE_col[frame_position]

            raw = tifffile.imread(fname).astype(np.float32)[np.newaxis]
            raw = fix_bad_pixels(raw)
            raw = apply_subpixel_shear_3d(raw, Ylow, Yhigh, TiltAngle, TiltOrder)
            data_2d, xaxis, _, _ = _preprocess_frames(raw, Ylow, Yhigh, RefL, self._xsize)

            local_axis = compute_frame_energy_axis(
                np.array([merix_value]), xaxis, Eb, Ra, DeltaD
            )[0]
            sort_idx = np.argsort(local_axis)
            local_axis = local_axis[sort_idx]
            local_intensity = data_2d[0][sort_idx]

            interp_vals = np.interp(
                self.emission_axis, local_axis, local_intensity, left=np.nan, right=np.nan
            )
            valid = ~np.isnan(interp_vals)
            self.intensity[valid, j] += interp_vals[valid]
            self.sample[valid, j] += 1

            if progress_callback is not None:
                progress_callback(int(100 * self._n_processed / n_total_for_progress))

        with np.errstate(invalid="ignore", divide="ignore"):
            intensity_norm = self.intensity / np.clip(self.sample, 1, None)

        self.bin_result = {
            "kind": "rxes_map",
            "emission_axis": self.emission_axis,
            "incident_axis": self.incident_axis,
            "intensity": self.intensity.copy(),
            "sample": self.sample.copy(),
            "intensity_norm": intensity_norm,
        }
        return self.bin_result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_rxes_dataset.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (no regressions elsewhere)

- [ ] **Step 6: Commit**

```bash
git add src/rixsviewer/model/rxes_dataset.py tests/test_rxes_dataset.py
git commit -m "feat: incremental per-frame RXES map accumulation with recalibration replay"
```

---

### Task 5: Frame display, no-op save, and `RixsSpecTable` wiring

**Files:**
- Modify: `src/rixsviewer/model/rxes_dataset.py`
- Modify: `src/rixsviewer/model/spec_table.py`
- Test: `tests/test_rxes_dataset.py`, `tests/test_spec_table_rxes.py`

**Interfaces:**
- Produces: `RixsRxesScanDataset.get_data_for_display(frame_index=-1, percentile_cutoff=99.0, TiltAngle=0, **kwargs)`, `release_data()`, `save_to_file(fname=None, force=False)`. `RixsSpecTable.process_spec_file()` constructs `RixsRxesScanDataset` for `RXESScan` rows and `RixsScanTiffDataset` for everything else.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_rxes_dataset.py`:

```python
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
```

Create `tests/test_spec_table_rxes.py`:

```python
# Copyright © UChicago Argonne LLC
# See LICENSE file for details
from rixsviewer.model.rxes_dataset import RixsRxesScanDataset
from rixsviewer.model.scan_dataset import RixsScanTiffDataset
from rixsviewer.model.spec_table import RixsSpecTable

from conftest import FakeBeamline


def test_spec_table_constructs_rxes_dataset_for_rxesscan_rows(tmp_path):
    beamline = FakeBeamline(str(tmp_path))
    beamline.run_rxes_scan(1, n_emission=2, n_incident=2)
    beamline.run_scan(2)

    table = RixsSpecTable(beamline.spec, beamline.workdir, save_filename=None)

    assert isinstance(table.record[1], RixsRxesScanDataset)
    assert isinstance(table.record[2], RixsScanTiffDataset)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_rxes_dataset.py tests/test_spec_table_rxes.py -v`
Expected: FAIL — `get_data_for_display`/`release_data`/`save_to_file` don't exist yet, and `RixsSpecTable` always constructs `RixsScanTiffDataset` today.

- [ ] **Step 3: Implement the three methods**

In `src/rixsviewer/model/rxes_dataset.py`, replace the `.utils` import line:

```python
from .utils import _preprocess_frames, apply_subpixel_shear_3d, compute_frame_energy_axis, fix_bad_pixels
```

with:

```python
from .utils import _preprocess_frames, apply_subpixel_shear_3d, compute_frame_energy_axis, fix_bad_pixels, percentile_clip
```

Add these methods to `RixsRxesScanDataset`, after `bin_data_wrap`:

```python
    def get_data_for_display(self, frame_index=-1, percentile_cutoff=99.0, TiltAngle=0, **kwargs):
        """
        Load one raw detector frame from disk for browsing.

        Unlike :meth:`~.scan_dataset.RixsScanTiffDataset.get_data_for_display`,
        this always reads directly from disk -- no raw stack is ever
        retained for RXES scans.
        """
        if self.scan_info is None or not self.scan_info["filenames"]:
            logger.debug("Scan %d has no TIFF frames yet; skipping display.", self.scan_index)
            return None

        filenames = self.scan_info["filenames"]
        num_frames = len(filenames)
        if frame_index == -2:
            frame_index = num_frames // 2
        elif frame_index == -1:
            frame_index = num_frames - 1
        frame_index = max(0, min(frame_index, num_frames - 1))

        frame = tifffile.imread(filenames[frame_index]).astype(np.float32)
        frame = fix_bad_pixels(frame[np.newaxis])[0]
        levels = percentile_clip(frame, percentile_cutoff)

        scandata = self.scan_info["scandata"]
        if scandata.empty:
            logger.debug("Scan %d has no scandata rows yet; skipping display.", self.scan_index)
            return None
        frame_metadata = self.scan_info["metadata"].copy()
        scandata_index = min(frame_index, len(scandata) - 1)
        frame_metadata["E"] = scandata["merixE"].iloc[scandata_index]
        frame_metadata["ThetaB"] = (
            np.arcsin(frame_metadata["Eb"] / frame_metadata["E"]) * 1e6
        )

        frame = self.apply_tilt_angle(frame, TiltAngle)

        return {
            "data": frame,
            "levels": levels,
            "num_frames": num_frames,
            "frame_metadata": frame_metadata,
            "scan_index": self.scan_index,
            "frame_index": frame_index,
        }

    def release_data(self):
        """No large buffer is ever retained for RXES scans; nothing to release."""
        pass

    def save_to_file(self, fname=None, force=False):
        """RXES map persistence is not implemented yet (deferred by design)."""
        logger.info(
            "Scan %d: RXES map persistence is not implemented yet; skipping save.",
            self.scan_index,
        )
```

- [ ] **Step 4: Wire `RixsSpecTable` to construct the right class**

In `src/rixsviewer/model/spec_table.py`, add the import:

```python
from .rxes_dataset import RixsRxesScanDataset
```

Replace this block in `process_spec_file`:

```python
            if get_scan_header(scan_pack)["scan_type"] in ["EnergyScan", "SnapshotScan", "RXESScan"]:
                if scan_number in self.record:
```

with:

```python
            scan_type = get_scan_header(scan_pack)["scan_type"]
            if scan_type in ["EnergyScan", "SnapshotScan", "RXESScan"]:
                if scan_number in self.record:
```

And replace this line (inside the `else:` branch that creates a new dataset):

```python
                    scan_dset = RixsScanTiffDataset(
                        row, self.spec_fname, self.tif_folder, scan_number
                    )
```

with:

```python
                    dataset_cls = (
                        RixsRxesScanDataset if scan_type == "RXESScan" else RixsScanTiffDataset
                    )
                    scan_dset = dataset_cls(
                        row, self.spec_fname, self.tif_folder, scan_number
                    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_rxes_dataset.py tests/test_spec_table_rxes.py -v`
Expected: PASS (all tests)

- [ ] **Step 6: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (no regressions)

- [ ] **Step 7: Commit**

```bash
git add src/rixsviewer/model/rxes_dataset.py src/rixsviewer/model/spec_table.py tests/test_rxes_dataset.py tests/test_spec_table_rxes.py
git commit -m "feat: wire RixsSpecTable to build RixsRxesScanDataset for RXESScan rows"
```

---

### Task 6: Guard the GUI's result routing against 2D-map results

**Files:**
- Modify: `src/rixsviewer/rixsviewer_gui.py`
- Test: `tests/test_process_binning_result_routing.py`

**Interfaces:**
- Consumes: the `"kind"` key on `bin_data_wrap()`'s return dict (present as `"rxes_map"` from Task 4; absent/not `"rxes_map"` for the existing 1D `bin_rixs_data()` result).
- Produces: `RixsViewerGUI.process_binning()`'s `on_result` no longer calls `self.view.plot_binned_data(...)` when the result is a 2D map; it updates the status bar instead. No other behavior changes.

This is the one place the two reduction pipelines meet in the GUI. Visualization of the 2D map itself is out of scope (per the design doc) — this step only prevents a crash/bad call when auto-update processes an `RXESScan` row.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_process_binning_result_routing.py
"""process_binning's on_result must route a 2D RXES map result away from
the 1D plot call (which expects 1D energy_axis/intensity_norm arrays and
would break on 2D-shaped ones), instead of crashing."""
import numpy as np


def test_rxes_map_result_does_not_call_plot_binned_data(gui, monkeypatch):
    called = []
    monkeypatch.setattr(gui.view, "plot_binned_data", lambda *a, **k: called.append(True))

    gui.beamline.run_rxes_scan(1, n_emission=2, n_incident=2)
    gui.update_spec_record()  # populates gui.current_rixs_dset via the stubbed process_binning
    dset = gui.current_rixs_dset
    result = dset.bin_data_wrap(metadata_source="SpecFile")

    # exercise the real routing method directly, bypassing the fixture's
    # no-op process_binning stub (which exists to isolate other tests
    # from the QThreadPool worker)
    gui._route_binning_result(result, show_rawdata=False, plot_target="intensity_norm")

    assert called == []


def test_spectrum_result_still_calls_plot_binned_data(gui, monkeypatch):
    called = []
    monkeypatch.setattr(gui.view, "plot_binned_data", lambda *a, **k: called.append(True))

    spectrum_result = {"energy_axis": np.array([1.0, 2.0]), "intensity_norm": np.array([0.1, 0.2])}
    gui._route_binning_result(spectrum_result, show_rawdata=False, plot_target="intensity_norm")

    assert called == [True]
```

Note: the `gui` fixture's `process_binning` is stubbed to a no-op by `conftest.py` for other tests' isolation — these two tests call the new `_route_binning_result` helper directly rather than going through the stubbed `process_binning`, so they exercise the real routing logic regardless.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_process_binning_result_routing.py -v`
Expected: FAIL with `AttributeError: 'RixsViewerGUI' object has no attribute '_route_binning_result'`

- [ ] **Step 3: Extract and guard the routing logic**

In `src/rixsviewer/rixsviewer_gui.py`, inside `process_binning()`, replace:

```python
        def on_result(result):
            self.view.plot_binned_data(
                result, show_rawdata, plot_target=plot_target, hdl_target="plot"
            )
            if result.get("warning"):
                self.statusBar().showMessage(f"Warning: {result['warning']}", 5000)
```

with:

```python
        def on_result(result):
            self._route_binning_result(result, show_rawdata, plot_target)
```

Then add this new method on `RixsViewerGUI`, near `process_binning`:

```python
    def _route_binning_result(self, result, show_rawdata, plot_target):
        """
        Route a ``bin_data_wrap()`` result to the right presentation.

        A 2D RXES map (``result["kind"] == "rxes_map"``) has no view yet
        (visualization is a follow-up); a 1D spectrum result is plotted
        as before.
        """
        if result.get("kind") == "rxes_map":
            filled = int(np.sum(result["sample"] > 0))
            total = result["sample"].size
            self.statusBar().showMessage(
                f"RXES map updated: {filled}/{total} cells filled", 3000
            )
            return

        self.view.plot_binned_data(
            result, show_rawdata, plot_target=plot_target, hdl_target="plot"
        )
        if result.get("warning"):
            self.statusBar().showMessage(f"Warning: {result['warning']}", 5000)
```

Confirm `numpy` is already imported in `rixsviewer_gui.py` (as `np`); if not, add `import numpy as np` near the top with the other imports.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_process_binning_result_routing.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (no regressions)

- [ ] **Step 6: Commit**

```bash
git add src/rixsviewer/rixsviewer_gui.py tests/test_process_binning_result_routing.py
git commit -m "fix: route RXES map results away from the 1D plot call in process_binning"
```

---

## End-to-end manual verification

After all six tasks are complete and committed, manually verify against the real reference dataset (as done earlier in this conversation):

```bash
/home/beams/MQICHU/.conda/envs/d2603_rixs/bin/python -c "
import sys; sys.path.insert(0, 'src')
from rixsviewer.model.spec_table import RixsSpecTable
from rixsviewer.model.rxes_dataset import RixsRxesScanDataset

t = RixsSpecTable('/home/beams/RIXS/Data/2026-3/slot1/23Sept2026c', '/net/s27data/export/sector27/lambda/2026-3/slot1/cray_clean', save_filename=None)
dset = t.record[1]
assert isinstance(dset, RixsRxesScanDataset)
result = dset.bin_data_wrap(metadata_source='SpecFile')
print(result['kind'], result['intensity_norm'].shape, 'filled cells:', (result['sample'] > 0).sum())
"
```

Then launch the real app (`launch_rixsviewer_dev --specfile ... --tiff-folder ...`) with auto-update enabled against a live or replayed RXES scan and confirm the status bar reports increasing "cells filled" counts without the app crashing or growing unbounded memory (spot-check with `ps`/`top` on the process RSS).
