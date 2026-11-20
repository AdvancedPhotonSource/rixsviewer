# EnergyScan / SnapshotScan dataset class split — design

## Background

`RixsRxesScanDataset` (added in a prior increment) gave `RXESScan` its own
dedicated dataset class, because its processing model is fundamentally
different from the other scan types (incremental 2D accumulation,
discard-per-frame memory model). `EnergyScan` and `SnapshotScan`, by
contrast, still share a single class, `RixsScanTiffDataset`
(`scan_dataset.py`), which keeps a full raw TIFF stack in memory and
delegates reduction to shared pure functions in `utils.py`
(`bin_rixs_data`, `_compute_energy_axis`, `fit_pixel_size`). Those
functions branch internally on `scan_type == "SnapshotScan"` in three
places rather than living in separate classes.

This document covers splitting `RixsScanTiffDataset` into
`RixsEnergyScanDataset` and `RixsSnapshotScanDataset`, mirroring the
"dedicated class per scan type" shape `RixsRxesScanDataset` already
established, while reusing code across all three classes wherever the
underlying behavior is genuinely shared.

## What's actually shared vs. divergent (as found by reading the current code)

Every method currently on `RixsScanTiffDataset` — `_prepare_inputs`,
`bin_data_wrap`, `save_to_file`, `get_data_for_display`, `read_tiff_data`,
`release_data` — is scan-type-agnostic at the wrapper level: none of them
branch on `scan_type` directly, they just forward `self.scan_info` (which
carries `scan_type`) down to the shared pure functions in `utils.py`. The
only real divergence lives inside those pure functions:

- `fit_pixel_size()`: early-returns the unchanged `DeltaD` for
  `SnapshotScan` (pixel-size fitting isn't supported).
- `_compute_energy_axis()`: two small branches — whether `e_min`/`e_max`
  come from the scan's `start`/`end` or from the actual data range, and
  whether `SnapshotScan` skips energy rebinning entirely (native pixel
  axis).
- `bin_rixs_data()`: additionally computes a summed raw image + display
  levels for `SnapshotScan`.

None of these are large enough to justify duplicating the surrounding
~150-line reduction pipeline into two separate functions. They stay
exactly as they are, shared and parameterized by `scan_type` — this is
already the "reuse layer," and `RixsRxesScanDataset` already reuses
`_preprocess_frames`, `compute_frame_energy_axis`, `fix_bad_pixels`, and
`apply_subpixel_shear_3d` from the same module. **No changes to
`utils.py` are part of this plan.**

## Component structure

```
TiffScanDatasetMixin (existing, unchanged)
        │
BufferedTiffScanDatasetMixin (NEW, extends TiffScanDatasetMixin)
   __init__, get_data_for_display, _prepare_inputs, bin_data_wrap,
   save_to_file, read_tiff_data, release_data, has_loaded_frames,
   supports_calibration() -> False   (default)
        │                              │
RixsEnergyScanDataset           RixsSnapshotScanDataset
  + fit_pixel_size_wrap()         (nothing added — pure marker class,
  + linesearch_to_optimize_          inherits everything from the mixin)
    parameter()
  + supports_calibration()
    -> True
```

`RixsRxesScanDataset` is untouched by this plan — it already has its own
memory model and doesn't relate to `BufferedTiffScanDatasetMixin`.

Every method listed under `BufferedTiffScanDatasetMixin` moves **verbatim**
from `RixsScanTiffDataset` — this is a structural move, not a rewrite.
Because neither concrete class needs any state or behavior beyond what's
already in the current constructor, the mixin owns a complete `__init__`
(unlike `TiffScanDatasetMixin`, which only documents a contract, since its
three host classes need different additional state). `RixsSnapshotScanDataset`
ends up with no body beyond a docstring.

`supports_calibration()` is a new predicate, defaulting to `False` on the
mixin (covering `SnapshotScan`) and overridden to `True` on
`RixsEnergyScanDataset`. `RixsRxesScanDataset` doesn't inherit from this
mixin (different memory model entirely), but the GUI's calibration gate
calls `self.current_rixs_dset.supports_calibration()` unconditionally,
whatever the current dataset's type — so `RixsRxesScanDataset` needs its
own `supports_calibration() -> False` too, or that call would raise
`AttributeError` for an in-progress RXES scan. This is a one-line
addition directly on `RixsRxesScanDataset`, not a shared-mixin concern.

`RixsScanTiffDataset` is deleted once the split lands — nothing references
it afterward (verified: its only non-docstring references are the
`RixsSpecTable` dispatch, three test files constructing it directly for
generic-behavior tests, and stale unrelated docstring cross-references in
`view/view.py` pointing at a nonexistent `specfile_reader` module, which
predate this work and are out of scope).

## Found while reading: a pre-existing dead method

`RixsScanTiffDataset.__len__` references `self.fnames`, which is never
set anywhere in the class — this would raise `AttributeError` if ever
called. No test or GUI code calls `len()` on a dataset object. This method
is dropped rather than carried forward, per "if you are certain something
is unused, delete it" — it is not moved into the new mixin.

## File organization

`scan_dataset.py` keeps its name and becomes home to:
`TiffScanDatasetMixin`, `BufferedTiffScanDatasetMixin`,
`RixsEnergyScanDataset`, `RixsSnapshotScanDataset`, `RixsScanImageTable`.
No new files — each concrete class is now thin enough (a handful of lines
or empty) that splitting into per-class files would fragment more than it
clarifies, unlike RXES, which warranted its own file for a genuinely large,
self-contained accumulator implementation.

## Naming

The user's phrasing was `EnergyScanDataset`/`SnapshotScanDataset`; this
spec uses `RixsEnergyScanDataset`/`RixsSnapshotScanDataset` to match the
existing `Rixs`-prefixed naming convention for model classes
(`RixsScanTiffDataset`, `RixsRxesScanDataset`, `RixsSpecTable`,
`RixsBinningModel`).

## Migration impact

- **`RixsSpecTable.process_spec_file()`**: the current
  `RixsRxesScanDataset if scan_type == "RXESScan" else RixsScanTiffDataset`
  ternary becomes a 3-entry dict lookup:
  `{"EnergyScan": RixsEnergyScanDataset, "SnapshotScan": RixsSnapshotScanDataset, "RXESScan": RixsRxesScanDataset}[scan_type]`.
- **`rixsviewer_gui.py:calibrate_parameters()`**: the
  `if self.current_rixs_dset.scan_info["scan_type"] != "EnergyScan":`
  check becomes `if not self.current_rixs_dset.supports_calibration():`.
  The warning dialog's message text can still name `EnergyScan`
  explicitly — that's user-facing copy, not a type check.
- **`rixsviewer_gui.py:_evict_scan_data()`**: its docstring's
  `dset : RixsScanTiffDataset or None` parameter doc updates to reflect
  that any scan dataset class is accepted (the method already only calls
  interface methods common to all of them).
- **Three existing test files construct `RixsScanTiffDataset` directly**
  for generic/shared-behavior tests (filename tracking, eviction,
  `is_complete()`, buffer preallocation) — `test_backfill_unprocessed_scans.py`,
  `test_tiff_scan_dataset_mixin.py`, `test_spec_table_rxes.py`. These
  move to `RixsEnergyScanDataset`, since the scans they construct (via
  `FakeBeamline.run_scan`/`start_scan`, `ascan merixE ...` headers) are
  genuinely `EnergyScan` type. `test_spec_table_rxes.py`'s
  `isinstance(table.record[2], RixsScanTiffDataset)` becomes
  `isinstance(table.record[2], RixsEnergyScanDataset)`.

## New test coverage (closing a pre-existing gap)

No test in the suite currently exercises `SnapshotScan` classification or
behavior at all. Since this plan touches exactly the code path that would
regress silently if `SnapshotScan` were mishandled, it adds:

- A `FakeBeamline` helper for snapshot scans — the minimal change is
  parameterizing the existing `start_scan(scan_no, e0=E0, e1=E1)` with
  optional start/end overrides (default unchanged, so no existing caller
  is affected), plus a thin `run_snapshot_scan(scan_no)` that calls it
  with `e0 == e1` (triggering `SnapshotScan` classification via
  `get_scan_header`'s existing `math.isclose` check) and adds points.
- `RixsSpecTable` dispatches a snapshot-scan row to
  `RixsSnapshotScanDataset` (parallel to the existing RXES dispatch test).
- `RixsSnapshotScanDataset.supports_calibration()` is `False`, and it has
  no `fit_pixel_size_wrap`/`linesearch_to_optimize_parameter` methods at
  all (`hasattr` is `False`, not "exists but no-ops").
- A `SnapshotScan` scan run through `bin_data_wrap()` produces a non-`None`
  `summed_data`/`levels` in the result (the one behavioral branch in
  `bin_rixs_data()` that's specific to this type and previously untested).

## Testing approach

Same conventions as the rest of the suite: real `FakeBeamline`-written
SPEC text and TIFFs, no mocks, `pytest tests/` from the repo root, TDD
(failing test before each change). The moved-verbatim methods on
`BufferedTiffScanDatasetMixin` are already covered by the existing tests
(once repointed at `RixsEnergyScanDataset`) — this is a refactor with a
regression suite already in place, not new logic needing new tests, aside
from the `SnapshotScan` coverage gap called out above and the new
`supports_calibration()` predicate itself.

## Out of scope

- No changes to `utils.py`'s pure functions (`bin_rixs_data`,
  `_compute_energy_axis`, `fit_pixel_size`) — their internal
  `scan_type`-branching stays as-is; see "What's actually shared vs.
  divergent" above for why.
- No changes to `RixsRxesScanDataset` beyond adding the one-line
  `supports_calibration() -> False` predicate for interface uniformity.
- The stale `specfile_reader.RixsScanTiffDataset` docstring
  cross-references in `view/view.py` are pre-existing and unrelated to
  this split; not touched here.
- Support for the single-axis `ascan kohzuE ...` scan pattern (still
  classified `Unknown`) remains a separate, previously-identified future
  item, unrelated to this split.
