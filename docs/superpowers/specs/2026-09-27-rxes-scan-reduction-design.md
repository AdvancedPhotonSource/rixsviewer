# RXES scan data reduction — design

## Background

RixsViewer is gaining support for `RXESScan`: a nested 2D mesh scan (SPEC
macro `rxesamesh`) covering incident energy × emission/analyzer energy,
whose reduced output is a 2D RXES map (incident energy vs. emission
energy vs. intensity).

Prior to this design, the following groundwork was already completed and
committed:

- `get_scan_header()` (`spec_parsers.py`) recognizes the `rxesamesh merixE
  ... kohzuE ...` header and classifies it as `RXESScan`.
- `RixsSpecTable` accepts `RXESScan` rows so they show up in the scan
  list table (SpecPoints/TiffPoints populate correctly).
- TIFF filename sorting was fixed to use a natural numeric sort
  (`tiff_point_index`) instead of lexicographic sort, which silently
  scrambled frame order for any scan exceeding ~100 points.
- **Axis semantics, confirmed with beamline staff:** `merixE` is the
  analyzer/**emission** energy (outer, slow loop — it sits near the
  `Eb` analyzer backscattering constant, which is why near-backscattering
  crystal optics only allow it to be tuned in a narrow window).
  `kohzuE` is the **incident** energy (inner, fast loop). The scan
  strategy is: for each analyzer/emission setting, sweep incident energy
  rapidly — i.e. many constant-emission-energy scans stitched into a map.
  The regex/field names in `spec_parsers.py` already reflect this
  (`incident_*` ← `kohzuE`, `emission_*` ← `merixE`). Per beamline staff,
  the incident-energy field to standardize on is `kohzuE`, not `MMonoE`
  (`MMonoE` isn't always present) — the current implementation already
  only reads `kohzuE`/`merixE` from the header line, never `MMonoE`.
- Confirmed the scan is a **raster**, not a snake: `kohzuE` (inner loop)
  always resets to its start value and sweeps low→high at every `merixE`
  step. Frame linear index `k` maps to grid coordinates via
  `i, j = divmod(k, n_incident_points)` (`i` = emission row, `j` =
  incident column).

This document covers the **data reduction/processing architecture**
for turning a stream of RXES frames into a 2D map, including real-time
(incremental) updates during acquisition. Visualization (a 2D map view
in the GUI) and result persistence are explicitly **out of scope** —
see "Out of scope" below.

## Motivating constraint: memory and recompute cost at RXES scale

`EnergyScan`/`SnapshotScan` today keep the *entire* raw TIFF stack
resident in RAM (`RixsScanTiffDataset._buffer`) and, in "real-time"
auto-update mode, fully **re-run the whole reduction pipeline from
scratch** every time new frames arrive (`process_binning()` calls
`bin_data_wrap()` on the full accumulated stack; if more files arrived
while that ran, it reinvokes itself). This is acceptable at the current
scale (tens of frames, tens of MB).

RXES scans are far larger: scan 11 in the reference dataset
(`23Sept2026c`) has 2620 frames at 256×256 px, i.e. **~655 MB** as
float32 for the full raw stack — 15-40× the size that caused the OOM bug
fixed in `9485cd4`. Naively extending the existing full-recompute
pattern to RXES would reintroduce that failure mode at a larger scale,
and would also mean redoing the full-stack shear/ROI/Rowland/interpolation
pipeline on a growing stack every poll (worst-case ~O(N²) total work
over a scan's lifetime).

Key realization that unlocks a better approach: computing one frame's
local emission-energy axis only requires **that frame's own `merixE`
value** — the same Rowland formula `_compute_energy_axis` already
applies per-frame for `EnergyScan`. And the map's shared emission axis
range (`emission_start`/`emission_end`) and grid shape
(`incident_points × emission_points`) are known **from the SPEC header
alone**, before any frame arrives. So each frame can be reduced and its
raw pixels discarded **immediately and independently**, accumulating
into a preallocated 2D array — no need to batch by column or retain
siblings in memory.

## Component structure

`RixsSpecTable.process_spec_file()` currently always constructs a
`RixsScanTiffDataset` for any recognized scan type. It will instead
construct a new **`RixsRxesScanDataset`** (new class, structurally
parallel to `RixsScanTiffDataset`, not a subclass of it — the internal
memory/accumulation model is fundamentally different) when
`scan_type == "RXESScan"`.

Both classes implement the same minimal interface that
`RixsSpecTable`/`RixsViewerGUI` call generically, so no new
`isinstance`/`scan_type` branching is needed at those call sites:

- `scan_info` (dict attribute)
- `row_position` (attribute)
- `update_scan_info(scan_pack)`
- `refresh_tiff_filenames()`
- `is_complete()`
- `get_qtableview_display_data(col)`
- `get_table_model()`
- `get_data_for_display(frame_index, ...)`
- `release_data()`
- `save_to_file(fname, force=False)`
- `bin_data_wrap(metadata_source=..., progress_callback=..., **kwargs)`

Several of these (filename globbing/diffing, `is_complete()`, the
table-column display) are pure `scan_info`-lookups independent of
accumulation strategy — these will be shared via a small mixin or plain
helper functions at implementation time rather than duplicated.

`bin_data_wrap()` keeps the **same call signature** as
`RixsScanTiffDataset.bin_data_wrap()`, so
`RixsViewerGUI.process_binning()`'s call site needs no change. The one
GUI touchpoint that does need a small branch is `process_binning()`'s
`on_result(result)` callback, which today always calls
`self.view.plot_binned_data(...)` (a 1D plot) — it will need to route to
a different (future) view method when the result is a 2D map. This is a
presentation-routing decision, not reduction logic.

## Data flow

**At construction** (as soon as the header is parsed), `RixsRxesScanDataset`:
1. Computes the shared emission-energy axis:
   `linspace(emission_start, emission_end, N)`, using the same
   native-pixel-spacing heuristic `_compute_energy_axis` already uses
   for `EnergyScan`.
2. Preallocates the 2D accumulator: `intensity`, `sample` (coverage
   count), `intensity_norm` arrays of shape
   `(n_emission_bins, n_incident_points)`, initialized to zero/NaN.

**Per newly-arrived frame** (detected via the existing
`update_scan_info()`/`unloaded_filenames` filename-diffing, unchanged
from today):
1. Locate `(i, j) = divmod(frame_position, n_incident_points)`.
   This relies on positional alignment between sorted TIFF filename
   order and `scandata` row order — the *same* assumption
   `EnergyScan`/`bin_rixs_data` already make (no value-based join
   exists today). Flagged as a known, pre-existing limitation, not
   something new introduced here: a skipped/retried acquisition point
   would misalign. Not solved in this pass.
2. Reduce the single frame: ROI-sum (`_preprocess_frames`) + the
   Rowland pixel→energy formula anchored on *that frame's own* `merixE`
   value. This formula will be **extracted from `_compute_energy_axis`
   into a small shared pure function** (e.g. `_frame_energy_axis(...)`)
   used by both the existing `EnergyScan` path and the new RXES path,
   rather than duplicated.
3. Interpolate the frame's narrow local spectrum onto the shared
   emission axis and accumulate into column `j`
   (`intensity[:, j] += ...`, `sample[:, j] += coverage_mask`) — the
   same nansum-with-coverage-count pattern `_reduce_frames` already uses
   for combining multiple frames, just indexed into a column.
4. Discard the raw frame immediately.

This is O(1) work per incoming frame with no growing raw-data
footprint, and the map is meaningfully viewable (if partially filled)
throughout acquisition.

## Real-time integration & recalibration

- `_evict_scan_data()`/`release_data()` become close to a no-op for
  `RixsRxesScanDataset` — there is no large buffer to free, since raw
  frames are discarded per-frame as they're processed.
- `get_data_for_display()` (browsing one raw detector frame) re-reads
  that single TIFF from disk on demand rather than slicing a resident
  buffer.
- **Recalibration:** when a calibration parameter changes (DeltaD,
  TiltAngle, RefL, etc.), the accumulator is zeroed and replayed by
  re-reading every file already listed in `scan_info["filenames"]` from
  disk, through the same per-frame reduction path. This trades instant
  recalibration (which `EnergyScan` gets for free by keeping the raw
  stack resident) for a bounded disk-read pass, in exchange for not
  holding a ~650MB+ buffer per active RXES scan.

## Persistence

**Explicitly deferred.** `RixsRxesScanDataset.save_to_file()` is a
no-op (log-only) for this phase — no file format is defined yet for the
2D map result. Known consequence: `RixsSpecTable.get_unprocessed_scans()`
checks the saved-results file to know what's already been processed;
since RXES scans are never written there, completed RXES scans will
keep re-appearing in the backfill/catch-up queue on every check. This is
harmless (idempotent recompute) but not free, given RXES frame counts.
Persistence format is a follow-up decision (candidates: one SPEC-style
block per incident-energy column stacked in one file, `.npz`/HDF5 array
dump, or whatever downstream analysis already expects) — to be decided
when visualization/export is designed.

## Error handling

- Frame-read failures surface through the existing `Worker` error
  signal → `on_error` → status bar/log, same mechanism as today. No new
  error-handling path is introduced.
- An aborted RXES scan simply leaves the preallocated accumulator
  partially filled (NaN/zero elsewhere); `is_complete()` still correctly
  reports `False`; nothing crashes.
- If actual frame count ever exceeds the expected grid size (e.g. a
  scan restart with a changed point count), the frame is skipped (not
  accumulated) and a warning is logged, rather than letting `(i, j)`
  index out of bounds or silently clamping into an edge column.

## Testing

This project has no test suite yet. The pieces introduced here are pure
numpy/logic and testable without Qt:
- The extracted shared Rowland formula helper — verify it reproduces
  the pre-refactor `EnergyScan`/`_compute_energy_axis` output exactly,
  as a regression guard for the extraction.
- The accumulator's frame→grid-index math and column accumulation, on
  synthetic data.
- `_RXES_SCAN_PATTERN`/`tiff_point_index` parsing (already hand-verified
  against the real `23Sept2026c` file; worth turning into a permanent
  regression test, especially given the sorting bug this already caught
  once).

## Out of scope (follow-up items)

- 2D map visualization in the GUI (a new view/plot method; `on_result`
  routing to it).
- Result persistence format and `save_to_file()` implementation for
  RXES.
- Support for the single-axis `ascan kohzuE ...` / `cscan kohzuE ...`
  scan pattern seen in the reference file (scans 2, 6, 7, 8) — currently
  classified `Unknown`. This looks like a constant-incident-energy XES
  scan and may warrant its own scan-type support later, but is unrelated
  to the 2D mesh case.
- Value-based (rather than positional) alignment between TIFF frames and
  `scandata` rows, for robustness against skipped/retried scan points.
