# Copyright © UChicago Argonne LLC
# See LICENSE file for details
import logging

import numpy as np
import tifffile

from .scan_dataset import TiffScanDatasetMixin
from .utils import _preprocess_frames, apply_subpixel_shear_3d, compute_frame_energy_axis, fix_bad_pixels

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
