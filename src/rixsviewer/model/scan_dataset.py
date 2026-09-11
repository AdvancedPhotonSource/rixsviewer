# Copyright © UChicago Argonne LLC
# See LICENSE file for details
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from os import cpu_count
from pathlib import Path

import numpy as np
import tifffile
from PySide6.QtCore import QAbstractTableModel, Qt

from .spec_parsers import parse_single_scan
from .utils import (
    bin_rixs_data,
    percentile_clip,
    fit_pixel_size,
    apply_subpixel_shear_3d,
    fix_bad_pixels,
)
from .process_parameters import unit_map
from .. import __version__

logger = logging.getLogger(__name__)


class RixsScanTiffDataset:
    """
    Container for scan metadata and lazily-loaded TIFF image data.

    Holds the parsed scan information and provides methods for loading
    the associated TIFF stack, displaying it, and computing the binned
    RIXS spectrum.

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

    def update_scan_info(self, scan_pack):
        """
        Refresh scan metadata and track newly-arrived TIFF files.

        If the TIFF point count has changed since the last update,
        :attr:`unloaded_filenames` is populated with the filenames not
        yet present in the cached data so that :meth:`read_tiff_data` can
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
            str(p) for p in Path(self.tif_folder).glob(f"{basename}_scan{self.scan_index}_point*.tif")
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

    # def calibrate_parameters(self, method="AlignCenter", meta_source="SpecFile", **kwargs):
    #     assert method in ("AlignCenter", "OptmizeFWHM"), "unsupported method"
    #     if method == "AlignCenter":
    #         return self.bin_data_wrap(metadata_source, fit_pixel_size=True, **kwargs)
    #     elif method == "OptimizeFWHM":
    #         return

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

    def __len__(self):
        return len(self.fnames)

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

    def read_tiff_data(self):
        """
        Load any pending TIFF files and return the complete image stack.

        Only the filenames in :attr:`unloaded_filenames` are read from
        disk; previously loaded frames stored in :attr:`_data` are
        preserved and the new frames are concatenated.

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
            data = np.stack(frames)
            data = fix_bad_pixels(data)
            logger.info(f"Scan {self.scan_index}: Read {n_files} tiff file(s) in {time.perf_counter() - t0:.2f}s")
            if self._data is None:
                self._data = data
            else:
                self._data = np.concatenate([self._data, data], axis=0)
            self.unloaded_filenames = []
        return self._data


class RixsScanImageTable(QAbstractTableModel):
    """
    Qt table model that lists the TIFF filenames for a single scan.

    Displays basenames in a single-column table suitable for use in a
    QTableView sidebar.

    Parameters
    ----------
    fnames : list of str
        Sorted list of absolute TIFF file paths to display.
    parent : QObject, optional
        Parent object passed to :class:`QAbstractTableModel`.
    """

    def __init__(
        self,
        fnames,
        parent=None,
    ):
        """
        Initialise the model with a list of TIFF filenames.

        Parameters
        ----------
        fnames : list of str
            Sorted list of absolute TIFF file paths.
        parent : QObject, optional
            Parent object for Qt ownership.
        """
        super().__init__(parent)
        # self.fnames = glob.glob(os.path.join(folder, f"*_scan{scan_index:d}_*.tif"))
        self.fnames = fnames
        self._headers = ["TIF filename"]

    def update_fnames(self, fnames):
        """Update the list of filenames and notify views."""
        self.beginResetModel()
        self.fnames = fnames
        self.endResetModel()

    def rowCount(self, parent=None):
        return len(self.fnames)

    def columnCount(self, parent=None):
        return 1

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            row, _ = index.row(), index.column()
            return Path(self.fnames[row]).name

        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal and self._headers:
            return self._headers[section]
        else:
            return str(section + 1)

    def get_image_fname(self, row):
        """
        Return the absolute path of the TIFF file at *row*.

        Parameters
        ----------
        row : int
            Zero-based row index.

        Returns
        -------
        str
            Absolute path to the TIFF file.
        """
        return self.fnames[row]
