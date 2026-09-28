# EnergyScan/SnapshotScan Dataset Class Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `RixsScanTiffDataset` into dedicated `RixsEnergyScanDataset` and `RixsSnapshotScanDataset` classes (mirroring the existing `RixsRxesScanDataset`), sharing the ~95% identical buffered-TIFF behavior via a new mixin, with no changes to the underlying `utils.py` reduction functions.

**Architecture:** A new `BufferedTiffScanDatasetMixin(TiffScanDatasetMixin)` carries everything currently on `RixsScanTiffDataset` that doesn't depend on scan type (`_prepare_inputs`, `bin_data_wrap`, `save_to_file`, `get_data_for_display`, `read_tiff_data`, `release_data`, `has_loaded_frames`, plus a new `supports_calibration()` defaulting to `False`). `RixsEnergyScanDataset` adds `fit_pixel_size_wrap`/`linesearch_to_optimize_parameter` and overrides `supports_calibration()` to `True`; `RixsSnapshotScanDataset` adds nothing. `RixsSpecTable` dispatches all three scan types via a dict lookup; the GUI's calibration gate becomes a polymorphic predicate call instead of a scan-type string check.

**Tech Stack:** Python, NumPy, pandas, PySide6/Qt, pytest.

**Spec:** `docs/superpowers/specs/2026-09-27-energy-snapshot-scan-dataset-split-design.md`

## Global Constraints

- No changes to `utils.py`'s pure functions (`bin_rixs_data`, `_compute_energy_axis`, `fit_pixel_size`, `_preprocess_frames`, `_reduce_frames`, `compute_frame_energy_axis`) — their internal `scan_type` branching is out of scope; the spec found the divergence too small to be worth splitting further.
- Every method moved from `RixsScanTiffDataset` into `BufferedTiffScanDatasetMixin` moves **verbatim** — this is a structural refactor with an existing regression suite, not new logic.
- `RixsScanTiffDataset.__len__` (references `self.fnames`, which is never set — dead code, confirmed unused anywhere) is dropped, not carried forward.
- `RixsRxesScanDataset` is otherwise untouched except for adding `supports_calibration() -> False`.
- Each task must leave the full test suite green — `RixsSpecTable` imports `scan_dataset.py`, so the class rename/split and its dispatch update cannot land in separate commits without an intermediate broken-import state.

## Review Focus

- `RixsSpecTable.process_spec_file()` must route a `SnapshotScan` header to `RixsSnapshotScanDataset`, not silently fall through to `RixsEnergyScanDataset` (the old two-way ternary's implicit "else" default) — the dict-based dispatch must have an explicit entry for every recognized type, not a catch-all.
- A `SnapshotScan` dataset must have no `fit_pixel_size_wrap`/`linesearch_to_optimize_parameter` methods at all (not stubs that warn) — a test that only checks `supports_calibration() is False` would miss a leftover stub method still being callable.
- `RixsRxesScanDataset.supports_calibration()` must exist and return `False` — the GUI's calibration gate calls this unconditionally on whatever `self.current_rixs_dset` currently is, including a mid-scan RXES dataset; a missing method here reintroduces the same class of `AttributeError` fixed for `has_loaded_frames()` in the prior increment.
- The `SnapshotScan` branch in `bin_rixs_data()` (computing `summed_data`/`levels`) has zero existing test coverage — a change here should be provably exercised, not just assumed to work because it's unchanged.
- The three existing test files that construct `RixsScanTiffDataset` directly test *generic* (type-agnostic) behavior — repointing them to `RixsEnergyScanDataset` must not silently narrow what they're actually verifying (e.g. `is_complete()`, eviction, buffer preallocation are not `EnergyScan`-specific, and the tests should keep reading that way).

---

## File Structure

- Modify: `src/rixsviewer/model/scan_dataset.py` — add `BufferedTiffScanDatasetMixin`, `RixsEnergyScanDataset`, `RixsSnapshotScanDataset`; remove `RixsScanTiffDataset`.
- Modify: `src/rixsviewer/model/spec_table.py` — 3-way dataset-class dispatch; docstring updates.
- Modify: `src/rixsviewer/model/rxes_dataset.py` — add `supports_calibration()`.
- Modify: `src/rixsviewer/rixsviewer_gui.py` — `calibrate_parameters()` gate; `_evict_scan_data` docstring.
- Modify: `tests/conftest.py` — parameterize `FakeBeamline.start_scan`/`add_point`; add `run_snapshot_scan`.
- Modify: `tests/test_backfill_unprocessed_scans.py`, `tests/test_tiff_scan_dataset_mixin.py`, `tests/test_spec_table_rxes.py` — repoint from `RixsScanTiffDataset` to `RixsEnergyScanDataset`.
- Create: `tests/test_energy_snapshot_scan_dataset.py`

---

### Task 1: Split `RixsScanTiffDataset` into `RixsEnergyScanDataset`/`RixsSnapshotScanDataset`, wire dispatch

**Files:**
- Modify: `src/rixsviewer/model/scan_dataset.py`
- Modify: `src/rixsviewer/model/spec_table.py`
- Modify: `tests/test_backfill_unprocessed_scans.py`, `tests/test_tiff_scan_dataset_mixin.py`, `tests/test_spec_table_rxes.py`

**Interfaces:**
- Consumes: `TiffScanDatasetMixin` (existing).
- Produces: `BufferedTiffScanDatasetMixin(TiffScanDatasetMixin)`, `RixsEnergyScanDataset(BufferedTiffScanDatasetMixin)`, `RixsSnapshotScanDataset(BufferedTiffScanDatasetMixin)` in `src/rixsviewer/model/scan_dataset.py`. `RixsSpecTable.process_spec_file()` constructs the matching class per `scan_type`. Used by Task 2 (GUI gate, `RixsRxesScanDataset.supports_calibration()`) and Task 3 (new test coverage).

- [ ] **Step 1: Repoint the three existing test files to the not-yet-existing `RixsEnergyScanDataset`**

In `tests/test_backfill_unprocessed_scans.py`, replace:

```python
from rixsviewer.model.scan_dataset import RixsScanTiffDataset
```

with:

```python
from rixsviewer.model.scan_dataset import RixsEnergyScanDataset
```

Then replace all three occurrences of `RixsScanTiffDataset(0, "fake.spec", "/tmp", 1)` with `RixsEnergyScanDataset(0, "fake.spec", "/tmp", 1)` (lines 58, 67, 76 — use `replace_all`).

In `tests/test_tiff_scan_dataset_mixin.py`, replace:

```python
from rixsviewer.model.scan_dataset import RixsScanTiffDataset
```

with:

```python
from rixsviewer.model.scan_dataset import RixsEnergyScanDataset
```

Then replace both occurrences of `RixsScanTiffDataset(` with `RixsEnergyScanDataset(` (line 7's `RixsScanTiffDataset(0, "fake.spec", "/tmp", 1)` and line 61's `RixsScanTiffDataset(0, spec_path, str(tmp_path), 1)` — use `replace_all`).

In `tests/test_spec_table_rxes.py`, replace:

```python
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

with:

```python
from rixsviewer.model.rxes_dataset import RixsRxesScanDataset
from rixsviewer.model.scan_dataset import RixsEnergyScanDataset
from rixsviewer.model.spec_table import RixsSpecTable

from conftest import FakeBeamline


def test_spec_table_constructs_rxes_dataset_for_rxesscan_rows(tmp_path):
    beamline = FakeBeamline(str(tmp_path))
    beamline.run_rxes_scan(1, n_emission=2, n_incident=2)
    beamline.run_scan(2)

    table = RixsSpecTable(beamline.spec, beamline.workdir, save_filename=None)

    assert isinstance(table.record[1], RixsRxesScanDataset)
    assert isinstance(table.record[2], RixsEnergyScanDataset)
```

- [ ] **Step 2: Run the three files to verify they fail**

Run: `pytest tests/test_backfill_unprocessed_scans.py tests/test_tiff_scan_dataset_mixin.py tests/test_spec_table_rxes.py -v`
Expected: FAIL with `ImportError: cannot import name 'RixsEnergyScanDataset' from 'rixsviewer.model.scan_dataset'` (all three files error at collection)

- [ ] **Step 3: Replace `RixsScanTiffDataset` with the mixin + two classes**

In `src/rixsviewer/model/scan_dataset.py`, replace everything from `class RixsScanTiffDataset(TiffScanDatasetMixin):` through the end of its `release_data` method (i.e. replace the entire class, stopping right before `class RixsScanImageTable(QAbstractTableModel):`) with:

```python
class BufferedTiffScanDatasetMixin(TiffScanDatasetMixin):
    """
    Shared behavior for scan-dataset classes that keep the entire raw TIFF
    stack resident in memory, as opposed to
    :class:`~.rxes_dataset.RixsRxesScanDataset`, which discards each frame
    after reducing it. Used by :class:`RixsEnergyScanDataset` and
    :class:`RixsSnapshotScanDataset`.

    Parameters
    ----------
    row_position : int
        Zero-based row index of this scan in the parent
        :class:`RixsSpecTable` model.
    spec_fname : str
        Path to the SPEC data file.
    tif_folder : str
        Directory containing the TIFF image files.
    """

    def __init__(self, row_position, spec_fname, tif_folder, scan_index):
        """
        Initialise dataset with file paths; no images are loaded yet.

        Parameters
        ----------
        row_position : int
            Row index in the parent table model.
        spec_fname : str
            Path to the SPEC data file.
        tif_folder : str
            Directory containing the TIFF image files.
        scan_index : int
            Scan index in the SPEC file.
        """
        self.row_position = row_position
        self.scan_index = scan_index
        self.spec_fname = spec_fname
        self.tif_folder = tif_folder
        self._model = None
        self._buffer = None
        self._n_filled = 0
        self._data = None
        self.unloaded_filenames = []
        self.scan_info = None
        self.bin_result = None
        self.bin_kwargs = None
        self._saved = False
        self.file_save_keys = {
            "energy_axis": "Energy",
            "intensity_norm": "Intensity_norm",
            "intensity_norm_err": "Intensity_norm_err",
            "intensity_raw": "Intensity_raw",
            "sample": "A",
            "i2": "i2",
            "i0": "i0",
            "mmepin1": "mmepin1",
            "mmepin2": "mmepin2",
        }

    def supports_calibration(self):
        """Whether pixel-size/tilt calibration is meaningful for this scan type."""
        return False

    def get_data_for_display(
        self, frame_index=-1, percentile_cutoff=99.0, TiltAngle=0, **kwargs
    ):
        """
        Load the TIFF stack and compute display intensity limits.

        Parameters
        ----------
        frame_index : int, optional
            Frame to display.  Negative values resolve to ``num_frames // 2``
            (the middle frame).  Default ``-1``.
        percentile_cutoff : float, optional
            Upper percentile used for colour-scale clipping.  Default ``99.0``.
        **kwargs
            Reserved for future use; not currently forwarded.

        Returns
        -------
        dict with keys:
            ``data``          — 2-D frame array (``float32``).
            ``levels``        — ``(vmin, vmax)`` colour-scale limits.
            ``num_frames``    — total number of frames in the stack.
            ``frame_metadata``— instrument parameters for this frame.
            ``scan_index``    — scan number.
            ``frame_index``   — resolved (non-negative) frame index.
        """
        self._data = self.read_tiff_data()
        if self._data is None or len(self._data) == 0:
            logger.debug(
                "Scan %d has no TIFF frames yet; skipping display.", self.scan_index
            )
            return None

        scandata = self.scan_info["scandata"]
        if scandata.empty:
            logger.debug(
                "Scan %d has no scandata rows yet; skipping display.", self.scan_index
            )
            return None

        num_frames = len(self._data)
        if frame_index == -2:
            frame_index = num_frames // 2
        elif frame_index == -1:
            frame_index = num_frames - 1
        frame_index = max(0, min(frame_index, num_frames - 1))

        levels = percentile_clip(self._data[frame_index], percentile_cutoff)

        frame_metadata = self.scan_info["metadata"].copy()
        scandata_index = min(frame_index, len(scandata) - 1)
        frame_metadata["E"] = scandata["merixE"].iloc[scandata_index]
        frame_metadata["ThetaB"] = (
            np.arcsin(frame_metadata["Eb"] / frame_metadata["E"]) * 1e6
        )  # micro-radian

        frame = self._data[frame_index]
        frame = self.apply_tilt_angle(frame, TiltAngle)

        return {
            "data": frame,
            "levels": levels,
            "num_frames": num_frames,
            "frame_metadata": frame_metadata,
            "scan_index": self.scan_index,
            "frame_index": frame_index,
        }

    def _prepare_inputs(self, metadata_source, kwargs):
        """
        Validate metadata source, merge instrument parameters, and resolve data.

        This helper encapsulates logic common to several processing wrappers.
        It returns a *new* dict that merges *kwargs* with any SpecFile metadata,
        leaving the caller's original dict unmodified.

        Parameters
        ----------
        metadata_source : {'SpecFile', 'PV', 'USER'}
            Source of instrument parameters.
        kwargs : dict
            Base keyword arguments from the caller.

        Returns
        -------
        data : numpy.ndarray
            Full TIFF image stack.
        merged_kwargs : dict
            A new dict containing *kwargs* merged with SpecFile metadata
            (when applicable). The caller's original dict is not modified.
        """
        assert metadata_source in ["SpecFile", "PV", "USER"], (
            "metadata_source not supported."
        )

        # Build a merged copy so the caller's dict is never mutated
        merged_kwargs = dict(kwargs)
        if metadata_source == "SpecFile":
            # SpecFile metadata wins over caller kwargs
            merged_kwargs.update(self.scan_info["metadata"])
            # Caller-forced overrides survive the SpecFile merge
            if kwargs.get("force_NEnergyBins") and "NEnergyBins" in kwargs:
                merged_kwargs["NEnergyBins"] = kwargs["NEnergyBins"]
        merged_kwargs.setdefault("start", self.scan_info.get("start"))
        merged_kwargs.setdefault("end", self.scan_info.get("end"))

        # Resolve self-dependent context and pass as plain data
        data = self.read_tiff_data()
        if data is None or len(data) == 0:
            raise ValueError(
                f"Scan {self.scan_index} has no TIFF frames loaded; "
                "cannot run processing on an empty dataset."
            )
        scandata = self.scan_info["scandata"]
        if scandata.empty:
            raise ValueError(
                f"Scan {self.scan_index} has no scandata rows; "
                "cannot run processing on an empty dataset."
            )
        return data, merged_kwargs

    def bin_data_wrap(
        self,
        metadata_source="SpecFile",
        progress_callback=None,
        **kwargs,
    ):
        """High-level wrapper that delegates to :func:`~.utils.bin_rixs_data`.

        Resolves all ``self``-dependent data (image stack, incident energies,
        scan type) and merges instrument parameters, then calls the pure
        function so that the computation has no dependency on this object.

        Parameters
        ----------
        metadata_source : {'SpecFile', 'PV', 'USER'}
            Source of instrument parameters:

            ``'SpecFile'``  — use parameters parsed from the SPEC ``#B`` header.
            ``'PV'``        — use parameters from EPICS PVs.
            ``'USER'``      — use parameters from the GUI parameter tree.
        **kwargs
            Additional keyword arguments forwarded verbatim to
            :func:`~.utils.bin_rixs_data` (e.g. ``noise_model``).
            When *metadata_source* is not ``'SpecFile'``, these kwargs
            should also contain the instrument parameters (``DeltaD``,
            ``RefL``, ``Eb``, ``rowland_radius``, etc.).

        Returns
        -------
        dict
            Result dictionary from :func:`~.utils.bin_rixs_data`.
        """
        data, merged_kwargs = self._prepare_inputs(metadata_source, kwargs)
        self.bin_result = bin_rixs_data(
            data, self.scan_info, progress_callback=progress_callback, **merged_kwargs
        )
        return self.bin_result

    def save_to_file(self, fname=None, force=False):
        if self.bin_result is None or (self._saved and not force):
            return
        self._saved = True

        if fname is None:
            fname = "./test_rixsviewer_saving.spec"

        res = self.bin_result

        with open(fname, "a") as f:
            f.write(f"\n#S {self.scan_index} {self.scan_info['scan_type']}\n")
            f.write(f"#D {np.datetime64('now')}\n")
            f.write(f"#C RixsViewerVersion = {__version__}\n")
            for key, value in self.scan_info["metadata"].items():
                unit = unit_map.get(key, "")
                f.write(f"#C {key} = {value}{unit}\n")
            f.write(f"#N {len(self.file_save_keys)}\n")
            header = "#L  " + "  ".join(list(self.file_save_keys.values()))
            f.write(header + "\n")
            data = np.column_stack([res[key] for key in self.file_save_keys.keys()])
            np.savetxt(f, data, fmt="%.18e")
            f.write("\n")

    def read_tiff_data(self):
        """
        Load any pending TIFF files and return the complete image stack.

        Only the filenames in :attr:`unloaded_filenames` are read from
        disk.  New frames are appended in place into a preallocated
        buffer so incremental loads during a live scan never reallocate
        the whole stack; :attr:`_data` is a view into that buffer.

        Bad pixels listed in :mod:`bad_pixels` are zeroed out after loading.

        Returns
        -------
        numpy.ndarray
            3-D array of shape ``(n_frames, height, width)`` with dtype
            ``float32``, or ``None`` if no files have been loaded yet.
        """
        if len(self.unloaded_filenames) > 0:
            n_files = len(self.unloaded_filenames)
            t0 = time.perf_counter()

            def _read_frame(fname):
                return tifffile.imread(fname).astype(np.float32)

            with ThreadPoolExecutor(max_workers=min(n_files, (cpu_count() or 2) // 2)) as ex:
                frames = list(ex.map(_read_frame, self.unloaded_filenames))
            chunk = fix_bad_pixels(np.stack(frames))

            if self._buffer is None:
                height, width = chunk.shape[1], chunk.shape[2]
                capacity = n_files
                if self.scan_info is not None:
                    capacity = max(
                        capacity,
                        self.scan_info.get("spec_points", 0),
                        self.scan_info.get("tiff_points", 0),
                    )
                self._buffer = np.empty((max(1, capacity), height, width), dtype=np.float32)
                self._n_filled = 0

            needed = self._n_filled + chunk.shape[0]
            if needed > self._buffer.shape[0]:
                # more frames than preallocated (e.g. snapshot scans or
                # stray tiffs); regrow once and copy the filled portion
                new_capacity = max(needed, 2 * self._buffer.shape[0])
                grown = np.empty((new_capacity, *self._buffer.shape[1:]), dtype=np.float32)
                grown[: self._n_filled] = self._buffer[: self._n_filled]
                self._buffer = grown

            self._buffer[self._n_filled : needed] = chunk  # noqa: E203
            self._n_filled = needed
            self._data = self._buffer[: self._n_filled]
            self.unloaded_filenames = []
            logger.info(f"Scan {self.scan_index}: Read {n_files} tiff file(s) in {time.perf_counter() - t0:.2f}s")
        return self._data

    def has_loaded_frames(self):
        """Whether any TIFF data is currently resident in memory for this scan."""
        return self._data is not None

    def release_data(self):
        """
        Release the loaded frame buffer so memory returns to ~zero.

        The frames can be reloaded from disk on demand:
        :attr:`unloaded_filenames` is restored so the next
        :meth:`read_tiff_data` call rebuilds the stack.
        """
        if self._data is not None:
            logger.debug(f"Scan {self.scan_index}: evicting {self._data.nbytes // (1024 * 1024)} MB from memory")
        self._buffer = None
        self._data = None
        self._n_filled = 0
        if self.scan_info is not None:
            self.unloaded_filenames = list(self.scan_info["filenames"])


class RixsEnergyScanDataset(BufferedTiffScanDatasetMixin):
    """
    Dataset container for ``EnergyScan`` scans (1D scan over ``merixE``).

    Adds pixel-size/tilt-angle calibration on top of the shared buffered
    scan-dataset behavior in :class:`BufferedTiffScanDatasetMixin`.
    """

    def supports_calibration(self):
        return True

    def fit_pixel_size_wrap(
        self,
        metadata_source="SpecFile",
        **kwargs,
    ):
        """High-level wrapper that delegates to :func:`~.utils.fit_pixel_size`.

        Resolves all ``self``-dependent data (image stack, incident energies,
        scan type) and merges instrument parameters, then calls the pure
        function.

        Parameters
        ----------
        metadata_source : {'SpecFile', 'PV', 'USER'}
            Source of instrument parameters:

            ``'SpecFile'``  — use parameters parsed from the SPEC ``#B`` header.
            ``'PV'``        — use parameters from EPICS PVs.
            ``'USER'``      — use parameters from the GUI parameter tree.
        **kwargs
            Additional keyword arguments forwarded verbatim to
            :func:`~.utils.fit_pixel_size` (e.g. ``center_method``).
            When *metadata_source* is not ``'SpecFile'``, these kwargs
            should also contain the instrument parameters (``DeltaD``,
            ``RefL``, ``Eb``, ``rowland_radius``, etc.).

        Returns
        -------
        float
            Effective pixel size in mm.
        """
        data, merged_kwargs = self._prepare_inputs(metadata_source, kwargs)
        merixE = np.asarray(self.scan_info["scandata"]["merixE"], dtype=float)
        scan_type = self.scan_info["scan_type"]

        effective_pixel_size = fit_pixel_size(data, merixE, scan_type, **merged_kwargs)
        merged_kwargs["DeltaD"] = effective_pixel_size
        result = self.bin_data_wrap(metadata_source="USER", **merged_kwargs)
        return effective_pixel_size, result

    def linesearch_to_optimize_parameter(
        self,
        target="DeltaD",
        metadata_source="SpecFile",
        n_steps=51,
        progress_callback=None,
        **kwargs,
    ):
        """Sweep ``DeltaD`` over ``[0.5, 1.5] × effective_pixel_size`` and collect FWHM.

        First the effective pixel size is determined via
        :meth:`fit_pixel_size_wrap`; then ``DeltaD`` is varied uniformly from
        ``0.5 × effective_pixel_size`` to ``1.5 × effective_pixel_size`` in
        *n_steps* steps.  At each step :meth:`bin_data_wrap` is called and the
        resulting FWHM is recorded.

        Parameters
        ----------
        metadata_source : {'SpecFile', 'PV', 'USER'}, optional
            Source of instrument parameters passed to
            :meth:`fit_pixel_size_wrap` and :meth:`bin_data_wrap`.
        n_steps : int, optional
            Number of uniformly-spaced ``DeltaD`` values to evaluate,
            by default 20.
        **kwargs
            Additional keyword arguments forwarded verbatim to both
            :meth:`fit_pixel_size_wrap` and :meth:`bin_data_wrap`.

        Returns
        -------
        linesearch_table : list of (float, float)
            List of ``(DeltaD, FWHM)`` pairs for every evaluated step,
            sorted by ascending ``DeltaD``.
        best_result : dict
            The full :meth:`bin_data_wrap` result dict obtained at the
            ``DeltaD`` value that yielded the smallest FWHM.
        best_deltad : float
            The ``DeltaD`` value that minimised the FWHM.
        """
        # Step 1 – resolve inputs once, then determine the reference pixel size
        org_value = kwargs[target]
        logger.info(f"Linesearch to optimize {target}, org_value: {org_value}")
        data, base_kwargs = self._prepare_inputs(metadata_source, kwargs)
        merixE = np.asarray(self.scan_info["scandata"]["merixE"], dtype=float)
        scan_type = self.scan_info["scan_type"]

        # Step 2 – determine line search grid
        assert target in ("DeltaD", "TiltAngle")
        if target == "DeltaD":
            # use least-squares fit to determine the reference pixel size
            lsq_value = fit_pixel_size(data, merixE, scan_type, **base_kwargs)
            # Step 2 – build the search grid
            val_low = 0.5 * lsq_value
            val_high = 1.5 * lsq_value
            val_list = np.linspace(val_low, val_high, n_steps)
        elif target == "TiltAngle":
            lsq_value = base_kwargs[target]
            val_low = -8
            val_high = 8
            val_list = np.linspace(val_low, val_high, n_steps)

        # Step 3 – sweep
        lns_table = []
        best_fwhm = np.inf
        lns_result = None
        lns_value = lsq_value

        for i, val in enumerate(val_list):
            sweep_kwargs = dict(base_kwargs)
            sweep_kwargs[target] = float(val)
            result = bin_rixs_data(
                data, self.scan_info, compute_fwhm=True, **sweep_kwargs
            )
            fwhm = result.get("fwhm", np.nan)
            lns_table.append((float(val), float(fwhm)))
            if np.isfinite(fwhm) and fwhm < best_fwhm:
                best_fwhm = fwhm
                lns_result = result
                lns_value = float(val)

            if progress_callback is not None:
                progress_callback(int((i + 1) / n_steps * 100))

        # Step 4 – binning at the reference point for overlay comparison
        original_kwargs = dict(base_kwargs)
        original_kwargs[target] = float(org_value)
        org_result = bin_rixs_data(
            data, self.scan_info, compute_fwhm=True, **original_kwargs
        )

        return {
            "target": target,
            "lns_table": lns_table,
            "lns_result": lns_result,
            "lns_value": lns_value,
            "org_value": org_value,
            "org_result": org_result,
        }


class RixsSnapshotScanDataset(BufferedTiffScanDatasetMixin):
    """
    Dataset container for ``SnapshotScan`` scans (repeat exposures at a
    fixed incident energy). Uses :class:`BufferedTiffScanDatasetMixin`
    unchanged -- the ``SnapshotScan``-specific branches (native pixel
    axis, summed display image) live in the shared ``utils.py`` reduction
    pipeline, not in this class. Pixel-size calibration is not supported
    (see :meth:`BufferedTiffScanDatasetMixin.supports_calibration`), so
    unlike :class:`RixsEnergyScanDataset` this class has no
    ``fit_pixel_size_wrap``/``linesearch_to_optimize_parameter`` methods.
    """
```

- [ ] **Step 4: Wire `RixsSpecTable`'s dispatch to the two new classes**

In `src/rixsviewer/model/spec_table.py`, replace the import:

```python
from .rxes_dataset import RixsRxesScanDataset
from .scan_dataset import RixsScanTiffDataset
from .spec_parsers import get_scan_header
```

with:

```python
from .rxes_dataset import RixsRxesScanDataset
from .scan_dataset import RixsEnergyScanDataset, RixsSnapshotScanDataset
from .spec_parsers import get_scan_header

_DATASET_CLASSES = {
    "EnergyScan": RixsEnergyScanDataset,
    "SnapshotScan": RixsSnapshotScanDataset,
    "RXESScan": RixsRxesScanDataset,
}
```

Then replace:

```python
                    dataset_cls = (
                        RixsRxesScanDataset if scan_type == "RXESScan" else RixsScanTiffDataset
                    )
                    scan_dset = dataset_cls(
                        row, self.spec_fname, self.tif_folder, scan_number
                    )
```

with:

```python
                    scan_dset = _DATASET_CLASSES[scan_type](
                        row, self.spec_fname, self.tif_folder, scan_number
                    )
```

Also update the three docstring references to `RixsScanTiffDataset` elsewhere in this file (in `get_unprocessed_scans` and `get_selected_dataset`'s docstrings) to say `RixsEnergyScanDataset, RixsSnapshotScanDataset, or RixsRxesScanDataset` instead.

- [ ] **Step 5: Run the three repointed test files to verify they pass**

Run: `pytest tests/test_backfill_unprocessed_scans.py tests/test_tiff_scan_dataset_mixin.py tests/test_spec_table_rxes.py -v`
Expected: PASS (all tests in all three files)

- [ ] **Step 6: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (no regressions)

- [ ] **Step 7: Commit**

```bash
git add src/rixsviewer/model/scan_dataset.py src/rixsviewer/model/spec_table.py tests/test_backfill_unprocessed_scans.py tests/test_tiff_scan_dataset_mixin.py tests/test_spec_table_rxes.py
git commit -m "refactor: split RixsScanTiffDataset into RixsEnergyScanDataset/RixsSnapshotScanDataset"
```

---

### Task 2: `supports_calibration()` on `RixsRxesScanDataset`; move the GUI's calibration gate off scan-type strings

**Files:**
- Modify: `src/rixsviewer/model/rxes_dataset.py`
- Modify: `src/rixsviewer/rixsviewer_gui.py`
- Test: `tests/test_rxes_dataset.py`, `tests/test_rxes_gui_integration.py`

**Interfaces:**
- Consumes: `RixsEnergyScanDataset.supports_calibration()`/`RixsSnapshotScanDataset.supports_calibration()` (Task 1).
- Produces: `RixsRxesScanDataset.supports_calibration() -> False`. `RixsViewerGUI.calibrate_parameters()` gates on `dset.supports_calibration()` instead of a scan-type string.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_rxes_dataset.py` (place near `TestHasLoadedFrames`):

```python
class TestSupportsCalibration:
    def test_rxes_dataset_does_not_support_calibration(self, tmp_path):
        dset, _ = _make_dataset(tmp_path, n_points=1)
        assert dset.supports_calibration() is False
```

This one has a plain RED/GREEN pair: `supports_calibration()` doesn't
exist yet on `RixsRxesScanDataset`, so it fails with `AttributeError`
before Step 3 and passes after.

The GUI-level change is a different situation worth being explicit
about: today's `calibrate_parameters()` check
(`scan_type != "EnergyScan"`) already happens to warn correctly for
every current scan type, including RXES — it's being replaced for
architectural reasons (the GUI shouldn't need to know scan-type names),
not because it currently misbehaves. That means there is no
before/after difference in *observable* behavior (warn-or-not) to assert
on here — asserting `warned == [True]` alone would pass equally well
before and after Step 3, so it wouldn't be a real RED/GREEN pair. What
*does* change is which mechanism decides — this can only be pinned by
observing that `supports_calibration()` is actually the method
consulted. Add this to `tests/test_rxes_gui_integration.py`:

```python
def test_calibrate_parameters_consults_supports_calibration_predicate(gui, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    warned = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: warned.append(True))

    gui.beamline.run_rxes_scan(1, n_emission=2, n_incident=2)
    gui.update_spec_record()
    dset = gui.current_rixs_dset

    calls = []
    original = dset.supports_calibration
    def spy():
        calls.append(True)
        return original()
    monkeypatch.setattr(dset, "supports_calibration", spy)

    gui.calibrate_parameters()

    assert calls == [True]  # the gate actually consulted the predicate
    assert warned == [True]  # ...and correctly denied calibration for RXES
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_rxes_dataset.py -v -k SupportsCalibration`
Expected: FAIL with `AttributeError: 'RixsRxesScanDataset' object has no attribute 'supports_calibration'`

Run: `pytest tests/test_rxes_gui_integration.py -v -k consults_supports_calibration`
Expected: FAIL with `AttributeError: 'RixsRxesScanDataset' object has no
attribute 'supports_calibration'` raised by the test's own
`original = dset.supports_calibration` line (there is nothing to spy on
yet), confirming the *old* `calibrate_parameters()` doesn't call this
method at all.

- [ ] **Step 3: Implement**

In `src/rixsviewer/model/rxes_dataset.py`, add this method to `RixsRxesScanDataset`, near `has_loaded_frames`:

```python
    def supports_calibration(self):
        """Pixel-size/tilt calibration is not implemented for RXES scans."""
        return False
```

In `src/rixsviewer/rixsviewer_gui.py`, replace:

```python
        if self.current_rixs_dset.scan_info["scan_type"] != "EnergyScan":
            QMessageBox.warning(
                self,
                "Warning",
                "Effective pixel size can only be fitted for EnergyScan",
            )
            return
```

with:

```python
        if not self.current_rixs_dset.supports_calibration():
            QMessageBox.warning(
                self,
                "Warning",
                "Effective pixel size can only be fitted for EnergyScan",
            )
            return
```

Also update `_evict_scan_data`'s docstring parameter doc:

```python
        dset : RixsScanTiffDataset or None
            The dataset to release. ``None`` is a no-op.
```

to:

```python
        dset : RixsEnergyScanDataset, RixsSnapshotScanDataset, RixsRxesScanDataset, or None
            The dataset to release. ``None`` is a no-op.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_rxes_dataset.py tests/test_rxes_gui_integration.py -v`
Expected: PASS (all tests in both files, including the two new ones)

- [ ] **Step 5: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (no regressions)

- [ ] **Step 6: Commit**

```bash
git add src/rixsviewer/model/rxes_dataset.py src/rixsviewer/rixsviewer_gui.py tests/test_rxes_dataset.py tests/test_rxes_gui_integration.py
git commit -m "refactor: move calibration gate off scan-type strings onto supports_calibration()"
```

---

### Task 3: Close the `SnapshotScan` test-coverage gap

**Files:**
- Modify: `tests/conftest.py`
- Create: `tests/test_energy_snapshot_scan_dataset.py`

**Interfaces:**
- Produces: `FakeBeamline.start_scan(scan_no, e0=None, e1=None)` (backward-compatible — `None` falls back to the module-level `E0`/`E1`), `FakeBeamline.run_snapshot_scan(scan_no, energy=E0)`.

- [ ] **Step 1: Write the failing tests**

In `tests/conftest.py`, replace:

```python
    def start_scan(self, scan_no):
        with open(self.spec, "a") as f:
            f.write(f"#S {scan_no} ascan merixE {E0} {E1} {POINTS} 0.1\n")
            f.write("#N 5\n")
            f.write("#L merixE i0 i2 mmepin1 mmepin2\n")
            f.write(f"#B {' '.join(XB_FIELDS)}\n")
            f.write("#D 2026-08-27 12:00:00\n")

    def add_point(self, scan_no, pt):
        e = E0 + (E1 - E0) * pt / (POINTS - 1)
        with open(self.spec, "a") as f:
            f.write(f"{e:.6f} 1.0 100.0 10.0 10.0\n")
        img = np.zeros((H, W), dtype=np.uint16)
        img[:, W // 2] = 60000
        tifffile.imwrite(os.path.join(self.workdir, f"fake.spec_scan{scan_no}_point{pt:04d}.tif"), img)

    def run_scan(self, scan_no):
        self.start_scan(scan_no)
        for pt in range(POINTS):
            self.add_point(scan_no, pt)
```

with:

```python
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
```

Create `tests/test_energy_snapshot_scan_dataset.py`:

```python
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
```

- [ ] **Step 2: Run the new file**

Run: `pytest tests/test_energy_snapshot_scan_dataset.py -v`
Expected: `TestSpecTableDispatchForSnapshotScan` and both
`TestSupportsCalibration` tests PASS immediately — Task 1 and Task 2
already implemented dispatch and the calibration predicate correctly;
what this step confirms is that they generalize to `SnapshotScan` once
the new `run_snapshot_scan()` fixture (added earlier in this same step)
can express that scenario at all. This is expected, not a sign the test
is wrong — a passing test here is a genuine finding, not a formality, per
the same principle as watching a test fail: don't skip running it just
because you expect it to pass.
`TestSnapshotScanBinning::test_bin_data_wrap_populates_summed_image` is
different: it exercises `bin_rixs_data()`'s `SnapshotScan` branch, which
is pre-existing and unchanged by this plan but has never had test
coverage before now. If it fails, use systematic-debugging to determine
whether it's revealing a real pre-existing bug in that branch or a
mistake in the test/fixture — do not adjust the assertion to match
whatever the code happens to output.

- [ ] **Step 3: Run the full test suite to confirm the `conftest.py` change didn't affect existing scans**

Run: `pytest tests/ -v`
Expected: PASS (all tests, including every existing test that calls `FakeBeamline.start_scan`/`run_scan`/`add_point` with no `e0`/`e1` arguments — these must be completely unaffected, since the new parameters default to `None` and fall back to the original module-level `E0`/`E1`)

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py tests/test_energy_snapshot_scan_dataset.py
git commit -m "test: add SnapshotScan dispatch, calibration-gate, and binning coverage"
```

---

## End-to-end manual verification

After both tasks are complete, sanity-check the split against the real reference dataset used throughout this project (any `EnergyScan`/`SnapshotScan` row from `23Sept2026c`):

```bash
/home/beams/MQICHU/.conda/envs/d2603_rixs/bin/python -c "
import sys; sys.path.insert(0, 'src')
from rixsviewer.model.spec_table import RixsSpecTable
from rixsviewer.model.scan_dataset import RixsEnergyScanDataset, RixsSnapshotScanDataset

t = RixsSpecTable('/home/beams/RIXS/Data/2026-3/slot1/23Sept2026c', '/net/s27data/export/sector27/lambda/2026-3/slot1/cray_clean', save_filename=None)
for num, dset in t.record.items():
    print(num, type(dset).__name__, dset.scan_info['scan_type'], 'supports_calibration=', dset.supports_calibration() if hasattr(dset, 'supports_calibration') else 'N/A')
"
```

Confirm every `EnergyScan` row reports `RixsEnergyScanDataset` / `supports_calibration=True`, every `SnapshotScan` row reports `RixsSnapshotScanDataset` / `supports_calibration=False`, and `RXESScan` rows are unaffected (`RixsRxesScanDataset` / `supports_calibration=False`).
