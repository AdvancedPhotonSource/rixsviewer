# Copyright © UChicago Argonne LLC
# See LICENSE file for details
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from os import cpu_count

import numpy as np
import tifffile

from .scan_dataset import TiffScanDatasetMixin
from .spec_parsers import tiff_point_index
from .utils import _preprocess_frames, apply_subpixel_shear_3d, compute_frame_energy_axis, fix_bad_pixels, percentile_clip

logger = logging.getLogger(__name__)


class RixsRxesScanDataset(TiffScanDatasetMixin):
    """Incremental 2D (incident energy x emission energy) map builder for
    an ``RXESScan``.

    Unlike :class:`~.scan_dataset.BufferedTiffScanDatasetMixin`
    (used by :class:`~.scan_dataset.RixsEnergyScanDataset` and
    :class:`~.scan_dataset.RixsSnapshotScanDataset`), this class never
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

    def _calibration_key(self, merged_kwargs):
        """Hashable snapshot of the calibration kwargs, rounded so that
        last-digit jitter in PV readbacks doesn't trigger a spurious full
        accumulator reset/replay on every poll."""
        key = []
        for name in self._CALIBRATION_KEYS:
            value = merged_kwargs.get(name)
            if isinstance(value, float):
                value = round(value, 6)
            key.append(value)
        return tuple(key)

    def _merge_binning_kwargs(self, metadata_source, kwargs):
        """Merge caller kwargs with SpecFile metadata, matching
        :meth:`~.scan_dataset.BufferedTiffScanDatasetMixin._prepare_inputs`'s
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

    def bin_data_wrap(self, metadata_source="SpecFile", progress_callback=None, **kwargs):
        """(Re)process any newly-arrived frames into the 2D RXES map.

        Parameters
        ----------
        metadata_source : {'SpecFile', 'PV', 'USER'}
            Source of instrument parameters, matching
            :meth:`~.scan_dataset.BufferedTiffScanDatasetMixin.bin_data_wrap`.
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

        start_time = time.perf_counter()
        merged_kwargs = self._merge_binning_kwargs(metadata_source, kwargs)
        key = self._calibration_key(merged_kwargs)
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
        filenames = self.scan_info["filenames"]
        # Filenames are numbered from an arbitrary start (e.g. "_point001"
        # in production, "_point0000" in tests) -- normalize against the
        # first file actually on record so frame_position is always a
        # correct 0-based grid index regardless of that convention.
        point_offset = tiff_point_index(filenames[0]) if filenames else 0

        to_process = list(self.unloaded_filenames)
        self.unloaded_filenames = []
        n_total_for_progress = max(total_points, 1)

        def _read_frame(fname):
            return tifffile.imread(fname).astype(np.float32)

        raw_frames = []
        if to_process:
            with ThreadPoolExecutor(
                max_workers=min(len(to_process), max(1, (cpu_count() or 2) // 2))
            ) as ex:
                raw_frames = list(ex.map(_read_frame, to_process))

        for fname, raw_frame in zip(to_process, raw_frames):
            # Position comes from the filename itself, not from a counter of
            # frames seen so far: a counter desynchronizes from the true
            # grid position after any dropped/re-queued file (see below),
            # silently writing later frames into the wrong column and
            # anchoring them on the wrong merixE value.
            frame_position = tiff_point_index(fname) - point_offset
            self._n_processed += 1
            if frame_position < 0 or frame_position >= total_points:
                logger.warning(
                    "Scan %d: frame position %d (from %s) is outside the "
                    "expected grid size (%d); skipping",
                    self.scan_index, frame_position, fname, total_points,
                )
                continue
            if frame_position >= len(merixE_col):
                # SPEC hasn't flushed this row yet even though the TIFF has
                # landed (detector can outrun the SPEC writer); re-queue for
                # the next poll instead of dropping it or crashing.
                logger.debug(
                    "Scan %d: scandata row for frame position %d not yet "
                    "available; re-queueing %s",
                    self.scan_index, frame_position, fname,
                )
                self.unloaded_filenames.append(fname)
                continue

            j = frame_position % n_incident
            merix_value = merixE_col[frame_position]

            raw = fix_bad_pixels(raw_frame[np.newaxis])
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

        if to_process:
            logger.info(
                "Scan %d: processed %d frame(s) in %.3fs",
                self.scan_index, len(to_process), time.perf_counter() - start_time,
            )

        self.bin_result = {
            "kind": "rxes_map",
            "emission_axis": self.emission_axis,
            "incident_axis": self.incident_axis,
            "intensity": self.intensity.copy(),
            "sample": self.sample.copy(),
            "intensity_norm": intensity_norm,
            "energy_resolution": round(float(self.emission_axis[1] - self.emission_axis[0]) * 1e6, 3),
        }
        return self.bin_result

    def get_data_for_display(self, frame_index=-1, percentile_cutoff=99.0, TiltAngle=0, **kwargs):
        """
        Load one raw detector frame from disk for browsing.

        Unlike :meth:`~.scan_dataset.BufferedTiffScanDatasetMixin.get_data_for_display`,
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

    def has_loaded_frames(self):
        """Whether at least one frame has been reduced into the accumulator yet."""
        return self._n_processed > 0

    def supports_calibration(self):
        """Pixel-size/tilt calibration is not implemented for RXES scans."""
        return False

    def supports_rxes_map(self):
        """RXES scans produce a 2D incident x emission energy map."""
        return True

    def release_data(self):
        """No large buffer is ever retained for RXES scans; nothing to release."""
        pass

    def save_to_file(self, fname=None, force=False):
        """RXES map persistence is not implemented yet (deferred by design)."""
        logger.info(
            "Scan %d: RXES map persistence is not implemented yet; skipping save.",
            self.scan_index,
        )
