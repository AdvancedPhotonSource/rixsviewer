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
