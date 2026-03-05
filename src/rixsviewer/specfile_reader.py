import glob
import logging
import math
import os
import re

import numpy as np
import pandas as pd
import tifffile
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from silx.io.specfile import SpecFile

logger = logging.getLogger(__name__)


def percentile_clip(data, threshold=99.9):
    """
    Compute display intensity limits using percentile clipping.

    Calculates a (vmin, vmax) tuple suitable for image display by computing
    the given percentile of positive values.  Only the first frame is used
    for 3-D arrays.

    Parameters
    ----------
    data : numpy.ndarray
        Input array with ndim 2 or 3.  Pixels with value ``<= 0`` are
        excluded from the percentile calculation.
    threshold : float, optional
        Upper percentile used to clip hot pixels, by default ``99.9``.

    Returns
    -------
    tuple of (float, float)
        ``(0, vmax)`` where *vmax* is the *threshold*-th percentile of the
        positive pixels.  Returns ``(0, 0)`` when *data* is empty.
    """
    if data.size == 0:
        return (0, 0)
    if data.ndim == 2:
        mask = data > 0
        vmax = np.percentile(data[mask], threshold)
    elif data.ndim == 3:
        mask = data[0] > 0
        vmax = np.percentile(data[0][mask], threshold)
    return (0, vmax)


def get_scan_type(scan):
    """
    Determine the scan type from a silx SpecFile scan object.

    Delegates to :func:`get_scan_type_from_scanstring` using the ``#S``
    header line of *scan*.

    Parameters
    ----------
    scan : silx.io.specfile.Scan
        A single scan object obtained from iterating a
        :class:`silx.io.specfile.SpecFile`.

    Returns
    -------
    tuple of (str, int)
        ``(scan_type, steps)`` where *scan_type* is one of
        ``'EnergyScan'``, ``'SnapshotScan'``, or ``'Unknown'`` and
        *steps* is the number of scan points (0 when unknown).
    """
    # scan_type = "Unknown"
    # if "Y" in scan.scan_header_dict and "L" in scan.scan_header_dict:
    #     scan_signature = scan.scan_header_dict["Y"]
    #     if scan_signature.startswith("EnergyScan"):
    #         scan_type = "EnergyScan"
    #     elif scan_signature.startswith("SnapshotScan"):
    #         scan_type = "SnapshotScan"

    # if scan_type != "Unknown":
    #     return scan_type
    # else:
    #    for on-going scans; the #Y line doesn't seem to be recognized correctly;
    scan_type, steps = get_scan_type_from_scanstring(scan.scan_header_dict["S"])
    return scan_type, steps


def get_scan_type_from_scanstring(text, tol=1e-6):
    """
    Classify a SPEC scan header line as ``SnapshotScan`` or ``EnergyScan``.

    Only scans whose motor name is exactly ``merixE`` are classified;
    all others return ``'Unknown'``.  A scan is a *SnapshotScan* when the
    start and end energies are equal within *tol*; otherwise it is an
    *EnergyScan*.

    Parameters
    ----------
    text : str
        The ``#S`` header line content **without** the leading ``#S``
        prefix.  Example::

            "286  ascan  merixE 11.2146 11.2154  80 1"

    tol : float, optional
        Absolute tolerance used by :func:`math.isclose` to decide whether
        start and end energies are equal, by default ``1e-6``.

    Returns
    -------
    tuple of (str, int)
        ``(scan_type, steps)`` where *scan_type* is one of
        ``'EnergyScan'``, ``'SnapshotScan'``, or ``'Unknown'``;
        *steps* is the number of data points (``steps_field + 1``) or
        ``0`` when the line cannot be parsed.
    """
    pattern = re.compile(
        r"""^
            \s*(\d+)\s+          # scan number
            (\w*scan)\s+         # scan macro name (e.g. ascan, dscan)
            merixE\s+            # motor name must be exactly 'merixE'
            ([+-]?\d*\.?\d+)\s+  # start
            ([+-]?\d*\.?\d+)\s+  # end
            (\d+)\s+             # steps
            ([+-]?\d*\.?\d+)\s*  # time
        $""",
        re.VERBOSE,
    )
    m = pattern.search(text)
    if not m:
        return "Unknown", 0

    start = float(m.group(3))
    end = float(m.group(4))
    steps = int(m.group(5)) + 1

    if math.isclose(start, end, rel_tol=0, abs_tol=tol):
        scan_type = "SnapshotScan"
    else:
        scan_type = "EnergyScan"

    return scan_type, steps


def parse_single_scan(scan, spec_fname, tif_folder):
    """
    Build a metadata dictionary for a single SPEC scan.

    Parameters
    ----------
    scan : silx.io.specfile.Scan
        A scan object from a :class:`silx.io.specfile.SpecFile`.
    spec_fname : str
        Absolute path to the SPEC data file.  Used to derive the TIFF
        file basename pattern.
    tif_folder : str
        Directory that contains the TIFF files associated with the scan.

    Returns
    -------
    dict
        Dictionary with the following keys:

        ``scan_number`` : int
            Integer scan index.
        ``scan_type`` : str
            One of ``'EnergyScan'``, ``'SnapshotScan'``, or ``'Unknown'``.
        ``spec_points`` : int
            Number of points declared in the SPEC header.
        ``tiff_points`` : int
            Number of TIFF files found on disk for this scan.
        ``metadata`` : dict
            Parsed instrument parameters (see
            :func:`get_metadata_from_header`).
        ``scandata`` : pandas.DataFrame
            Per-point motor/counter values from the scan body.
        ``filenames`` : list of str
            Sorted list of TIFF file paths belonging to this scan.
    """
    scan_number = scan.number
    scandata = get_scandata_information(scan)
    filenames = get_linked_tiff_filenames(spec_fname, tif_folder, scan_number)
    scan_type, scan_points = get_scan_type(scan)
    info = {
        "scan_number": scan_number,
        "scan_type": scan_type,
        "spec_points": scan_points,
        "tiff_points": len(filenames),
        "metadata": get_metadata_from_header(scan.scan_header_dict["B"]),
        "scandata": scandata,
        "filenames": filenames,
    }
    return info


def get_linked_tiff_filenames(spec_fname, tif_folder, scan_number):
    """
    Find and sort TIFF files on disk that belong to a given scan.

    Files are matched with the glob pattern
    ``<tif_folder>/<spec_basename>_scan<scan_number>_point*.tif``.

    Parameters
    ----------
    spec_fname : str
        Path to the SPEC data file.  Only the basename is used.
    tif_folder : str
        Directory that contains the TIFF files.
    scan_number : int
        Scan index used to filter matching files.

    Returns
    -------
    list of str
        Sorted list of absolute TIFF file paths.
    """
    basename = os.path.basename(spec_fname)
    fnames = glob.glob(
        os.path.join(tif_folder, f"{basename}_scan{scan_number}_point*.tif")
    )
    fnames.sort()
    return fnames


def get_scandata_information(scan):
    """
    Extract per-point motor and counter data from a scan as a DataFrame.

    Column names are read from the ``#L`` header line of the scan.

    Parameters
    ----------
    scan : silx.io.specfile.Scan
        A scan object from a :class:`silx.io.specfile.SpecFile`.

    Returns
    -------
    pandas.DataFrame
        DataFrame with one row per scan point and one column per
        motor/counter label defined in the ``#L`` header.
    """
    header = scan.scan_header_dict["L"].split()
    scandata = scan.data.T
    scandata = pd.DataFrame(scandata, columns=header)
    return scandata


def get_metadata_from_header(scan_comment_str) -> dict:
    """
    Parse metadata from scan header string.

    Expected format: 'Analyzer_EB_keV = 11.184\nRowland_Radius_m = 1998\nCenter_x_pixel = 77\n...'

    Returns dictionary with parameter names matching RixsBinningModel in rixs_image.py:
    - Eb: Analyzer backscattering energy (keV)
    - Ra: Rowland circle radius (mm)
    - RefL: Reference pixel/channel for energy dispersion center
    - Ylow, Yhigh: Y pixel binning range
    - Acrystalsize: Analyzer crystal size (mm)
    - DeltaD: Detector pixel width in energy dispersion direction (mm)
    """

    text = scan_comment_str

    # Regular expressions for new format
    analyzer_eb_kev = re.search(r"Analyzer_EB_keV\s*=\s*([\d.]+)", text)
    rowland_radius_m = re.search(r"Rowland_Radius_m\s*=\s*([\d.]+)", text)
    center_x_pixel = re.search(r"Center_x_pixel\s*=\s*([\d.]+)", text)
    low_y_pixel = re.search(r"Low_y_pixel\s*=\s*([\d.]+)", text)
    high_y_pixel = re.search(r"High_y_pixel\s*=\s*([\d.]+)", text)
    analyzer_crystal_size_mm = re.search(
        r"Analyzer_Crystal_Size_mm\s*=\s*([\d.]+)", text
    )
    lambda_strip_size_mm = re.search(r"Lambda_Strip_Size_mm\s*=\s*([\d.]+)", text)

    # Build result dictionary
    result = {
        "Eb": float(analyzer_eb_kev.group(1)),
        "Ra": float(rowland_radius_m.group(1)),
        "RefL": int(float(center_x_pixel.group(1))),
        "Ylow": int(float(low_y_pixel.group(1))),
        "Yhigh": int(float(high_y_pixel.group(1))),
        "Acrystalsize": float(analyzer_crystal_size_mm.group(1)),
        "DeltaD": float(lambda_strip_size_mm.group(1)),
    }

    # Keep binning_range for backward compatibility
    result["binning_range"] = (result["Ylow"], result["Yhigh"])

    return result


class RixsSpecTable(QAbstractTableModel):
    """
    Qt table model that exposes SPEC scan metadata to a QTableView.

    Each row corresponds to one RIXS scan (``EnergyScan`` or
    ``SnapshotScan``) found in the SPEC file.  The model can be refreshed
    in-place by calling :meth:`process_spec_file` again; only new or
    updated scans are re-processed.

    Parameters
    ----------
    fname : str
        Path to the SPEC data file to monitor.
    tif_folder : str
        Directory that contains the associated TIFF image files.
    parent : QObject, optional
        Parent object passed to :class:`QAbstractTableModel`.
    """

    def __init__(self, fname, tif_folder, parent=None):
        """
        Initialise the model and perform the first read of the SPEC file.

        Parameters
        ----------
        fname : str
            Path to the SPEC data file.
        tif_folder : str
            Directory containing the TIFF image files.
        parent : QObject, optional
            Parent object for Qt ownership.
        """
        super().__init__(parent)
        self.spec_fname = fname
        self.spec_container = None
        self.tif_folder = tif_folder
        self.last_modtime = -1
        self._headers = ["Scan#", "Type", "SpecPoints", "TiffPoints"]
        self.record = {}
        self.last_scan_index = 0
        self.last_scan_dset = None
        self.process_spec_file()

    def read_latest_spec_file(self):
        """
        (Re-)load the SPEC file if it has been modified since the last read.

        Compares the file's modification time against the cached value.  If
        unchanged the existing :attr:`spec_container` is kept.

        Returns
        -------
        bool
            ``True`` when the file was (re-)loaded; ``False`` when the
            cached version is still current.
        """
        last_modtime = os.path.getmtime(self.spec_fname)
        if last_modtime == self.last_modtime and self.spec_container is not None:
            return False
        else:
            self.last_modtime = last_modtime
        self.spec_container = SpecFile(self.spec_fname)
        return True

    def process_spec_file(self):
        """
        Parse the SPEC file and update the model with new or changed scans.

        Scans with indices below :attr:`last_scan_index` are skipped to
        avoid redundant processing.  For scans already present in
        :attr:`record` only the scan info is refreshed and the
        ``dataChanged`` signal is emitted.  Truly new scans are inserted
        via ``beginInsertRows`` / ``endInsertRows``.
        """
        if not self.read_latest_spec_file():
            return

        for scan_pack in self.spec_container:
            scan_number = scan_pack.number
            # no need to re-process old scans
            if scan_number < self.last_scan_index:
                continue

            if get_scan_type(scan_pack)[0] in ["EnergyScan", "SnapshotScan"]:
                if scan_number in self.record:
                    scan_dset = self.record[scan_number]
                    scan_dset.update_scan_info(scan_pack)
                    # update the view for this row
                    row = scan_dset.row_position
                    index_top_left = self.index(row, 0)
                    index_bottom_right = self.index(row, self.columnCount() - 1)
                    self.dataChanged.emit(index_top_left, index_bottom_right)
                else:
                    # new scan dataset
                    row = len(self.record)
                    scan_dset = RixsScanTiffDataset(
                        row, self.spec_fname, self.tif_folder
                    )
                    scan_dset.update_scan_info(scan_pack)
                    self.beginInsertRows(QModelIndex(), row, row)
                    self.record[scan_number] = scan_dset
                    self.endInsertRows()
                    self.last_scan_index = max(self.last_scan_index, scan_number)
        self.last_scan_dset = scan_dset

    def rowCount(self, parent=None):
        return len(self.record)

    def columnCount(self, parent=None):
        return len(self._headers)

    def get_selected_dataset(self, row):
        """
        Retrieve the :class:`RixsScanTiffDataset` for a given table row.

        Parameters
        ----------
        row : int
            Zero-based row index as shown in the QTableView.

        Returns
        -------
        RixsScanTiffDataset
            Dataset object associated with the scan at *row*.
        """
        scan_index = list(self.record.keys())[row]
        scan_tiff_dset = self.record[scan_index]
        return scan_tiff_dset

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid():
            return False

        # notify views
        self.dataChanged.emit(index, index, [role])
        return True

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            row, col = index.row(), index.column()
            scan_index = list(self.record.keys())[row]
            scan_tiff_dset = self.record[scan_index]
            return scan_tiff_dset.get_qtableview_display_data(col)

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

    def __init__(self, row_position, spec_fname, tif_folder):
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
        """
        self.row_position = row_position
        self.spec_fname = spec_fname
        self.tif_folder = tif_folder
        self._model = None
        self._data = None
        self.unloaded_filenames = []
        self.scan_info = None

    def update_scan_info(self, scan_pack):
        """
        Refresh scan metadata and track newly-arrived TIFF files.

        If the TIFF point count has changed since the last update,
        :attr:`unloaded_filenames` is populated with the filenames not
        yet present in the cached data so that :meth:`read_data` can
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
        if (
            self.scan_info is None
            or self.scan_info["tiff_points"] != scan_info["tiff_points"]
        ):
            prev_filenames = (
                [] if self.scan_info is None else self.scan_info["filenames"]
            )
            unloaded_filenames = [
                fn for fn in scan_info["filenames"] if fn not in prev_filenames
            ]
            self.unloaded_filenames = unloaded_filenames
            self.scan_info = scan_info

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

    def get_data_for_display(self, **kwargs):
        """
        Load the TIFF stack and compute display intensity limits.

        Parameters
        ----------
        **kwargs
            Reserved for future use; not currently forwarded.

        Returns
        -------
        data : numpy.ndarray
            3-D array of shape ``(n_frames, height, width)`` containing
            pixel intensities as ``float32``.
        levels : tuple of (float, float)
            ``(vmin, vmax)`` computed by :func:`percentile_clip`.
        """
        self._data = self.read_data()
        levels = percentile_clip(self._data)
        return self._data, levels

    def bin_data_wrap(
        self,
        fit_pixel_size=False,
        metadata_source="SpecFile",
        noise_model="poisson",
        binning_kwargs=None,
    ):
        """
        High-level wrapper that calls :meth:`_bin_data` with resolved parameters.

        Parameters
        ----------
        fit_pixel_size : bool, optional
            When ``True`` and the scan is an ``EnergyScan``, fit the
            effective pixel size from the data rather than using the
            value stored in the metadata.  Default is ``False``.
        metadata_source : {'internal', 'external'}
            Source of instrument parameters:

            ``'SpecFile'``
                Use parameters parsed from the SPEC ``#B`` header line
                (stored in :attr:`scan_info['metadata']`).
            ``'PV'``
                Use parameters from the PVs.
            ``'GUI'``
                Use parameters from the GUI.
        noise_model : {'poisson', 'gaussian'}
            Statistical model used to estimate per-bin uncertainty.
            Default is ``'poisson'``.
        binning_kwargs : dict or None, optional
            Instrument parameters forwarded to :meth:`_bin_data` when
            *metadata_source* is ``'external'``.  Ignored otherwise.

        Returns
        -------
        dict
            Result dictionary returned by :meth:`_bin_data`.

        Raises
        ------
        AssertionError
            If *metadata_source* is not ``'internal'`` or ``'external'``.
        """
        assert metadata_source in ["SpecFile", "PV", "GUI"], "metadata_source not supported."
        kwargs = {"fit_pixel_size": fit_pixel_size, "noise_model": noise_model}
        if metadata_source == "SpecFile":
            kwargs.update(self.scan_info["metadata"])
        else:
            kwargs.update(binning_kwargs)
        return self._bin_data(**kwargs)

    def _bin_data(
        self,
        DeltaD=0.022,
        RefL=70,
        fit_pixel_size=True,
        Eb=10,
        rowland_radius=1900,
        energy_cen=None,
        Ylow=0,
        Yhigh=256,
        noise_model="poisson",
        **kwargs,
    ):
        """
        Compute the binned RIXS spectrum from the loaded TIFF stack.

        Applies row-range selection, optional reflectivity tail masking,
        energy-axis calibration using the Rowland circle geometry, and
        interpolated rebinning onto a uniform energy grid.

        Parameters
        ----------
        DeltaD : float, optional
            Nominal detector pixel pitch in the energy-dispersion direction
            (mm), used when *fit_pixel_size* is ``False``.  Default ``0.022``.
        RefL : int, optional
            Reference pixel (channel) corresponding to the elastic peak
            position, i.e. the zero of the pixel-offset axis.  Default ``70``.
        fit_pixel_size : bool, optional
            If ``True`` and the scan type is ``'EnergyScan'``, estimate the
            effective pixel size by least-squares fitting the elastic peak
            positions vs. incident energy.  Default ``True``.
        Eb : float, optional
            Analyzer backscattering energy in keV.  Default ``10``.
        rowland_radius : float, optional
            Rowland circle radius in mm.  Default ``1900``.
        energy_cen : ignored
            Accepted for API compatibility but not used; the incident energy
            is taken from the ``merixE`` column of :attr:`scan_info`.
        Ylow : int, optional
            Lower Y-pixel bound (inclusive) for the row-summation region.
            Default ``0``.
        Yhigh : int, optional
            Upper Y-pixel bound (exclusive) for the row-summation region.
            Default ``256``.
        noise_model : {'poisson', 'gaussian'}, optional
            Statistical model for per-bin error estimation:

            ``'poisson'``
                ``err = sqrt(mean / count)``.
            ``'gaussian'``
                ``err = std / sqrt(count)``.

            Default is ``'poisson'``.
        **kwargs
            Additional keyword arguments are silently ignored (allows
            extra metadata keys to be forwarded without error).

        Returns
        -------
        dict
            Dictionary with the following keys:

            ``rawdata_lines`` : list of [numpy.ndarray, numpy.ndarray]
                Per-frame ``[energy_axis, intensity]`` pairs before
                rebinning.
            ``binned_line`` : tuple of (numpy.ndarray, numpy.ndarray, numpy.ndarray)
                ``(bin_energy_axis, bin_data_mean, bin_data_err)`` on a
                uniform energy grid.
            ``DeltaD_fit`` : float
                Effective pixel size used (fitted or nominal).
            ``summed_data`` : numpy.ndarray or None
                Sum of all frames (only for ``'SnapshotScan'``;
                ``None`` for ``'EnergyScan'``).
            ``levels`` : tuple of (float, float) or None
                Display intensity limits for *summed_data* computed by
                :func:`percentile_clip`, or ``None`` for ``'EnergyScan'``.

        Raises
        ------
        AssertionError
            If *Ylow* / *Yhigh* are outside the detector dimensions or
            *noise_model* is not recognised.
        """
        self._data = self.read_data()
        shape = self._data.shape

        assert Ylow >= 0 and Yhigh <= shape[1] and Ylow < Yhigh, (
            "check Ylow and Yhigh and detector shape"
        )
        data_1d = np.sum(self._data[:, Ylow:Yhigh, :], axis=1)

        # pad values after xrefl if needed;
        if 2 * RefL < shape[2]:
            data_1d[:, 2 * RefL :] = np.mean(data_1d[:, 2 * RefL])

        xaxis = np.arange(shape[2]) - RefL

        merixE = self.scan_info["scandata"]["merixE"]
        assert merixE.shape[0] == shape[0], (
            "merixE and data_1d must have the same number of rows"
        )

        theta_b = np.arcsin(Eb / merixE)
        energy_cen = np.array(merixE).reshape(-1, 1)

        scale = np.array(Eb / (2 * rowland_radius) / np.tan(theta_b))

        scan_type = self.scan_info["scan_type"]

        if fit_pixel_size and scan_type == "SnapshotScan":
            logger.warning("fit_pixel_size is not implemented for SnapshotScan")
            fit_pixel_size = False

        if fit_pixel_size and scan_type == "EnergyScan":
            # center of mass in pixels for the peak position;
            com_pixel = np.sum(data_1d * xaxis, axis=1) / np.sum(data_1d, axis=1)

            a_mat = np.array(com_pixel * scale).reshape(shape[0], 1)
            a_mat = np.hstack([a_mat, np.ones_like(a_mat)])  # n_images x 2
            effective_pixel_size, energy_fit = np.linalg.lstsq(a_mat, energy_cen)[0]
            effective_pixel_size = float(effective_pixel_size)
            logger.info(f"Fitted effective pixel size: {effective_pixel_size} mm")
        else:
            # use DeltaD as the effective pixel size
            effective_pixel_size = DeltaD

        energy_axis = energy_cen - np.outer(scale, xaxis) * effective_pixel_size

        # sort the data
        for n in range(shape[0]):
            sort_idx = np.argsort(energy_axis[n])
            energy_axis[n] = energy_axis[n][sort_idx]
            data_1d[n] = data_1d[n][sort_idx]

        lines = [[energy_axis[n], data_1d[n]] for n in range(shape[0])]
        energy_min, energy_max = np.min(energy_axis), np.max(energy_axis)
        step = int(
            (energy_max - energy_min) / np.mean(np.abs((np.diff(energy_axis, axis=1))))
        )

        bin_energy_axis = np.linspace(energy_min, energy_max, step)
        bin_data = [
            np.interp(
                bin_energy_axis, energy_axis[n], data_1d[n], left=np.nan, right=np.nan
            )
            for n in range(shape[0])
        ]

        bin_data = np.array(bin_data)
        bin_data_sum = np.nansum(bin_data, axis=0)
        bin_data_cnt = np.sum(~np.isnan(bin_data), axis=0)
        bin_data_mean = bin_data_sum / np.clip(bin_data_cnt, a_min=1, a_max=None)

        assert noise_model in [
            "poisson",
            "gaussian",
        ], "noise_model must be either 'poisson' or 'gaussian'"
        if noise_model == "poisson":
            bin_data_err = np.sqrt(bin_data_mean / bin_data_cnt)
        elif noise_model == "gaussian":
            bin_data_err = np.nanstd(bin_data, axis=0) / np.sqrt(bin_data_cnt)

        if self.scan_info["scan_type"] == "SnapshotScan":
            summed_data = np.sum(self._data, axis=0)
            levels = percentile_clip(summed_data)
        else:
            summed_data = None
            levels = None

        return {
            "rawdata_lines": lines,
            "binned_line": (bin_energy_axis, bin_data_mean, bin_data_err),
            "DeltaD_fit": effective_pixel_size,
            "summed_data": summed_data,
            "levels": levels,
        }

    def __len__(self):
        """
        Return the number of TIFF files associated with this scan.

        Returns
        -------
        int
            Length of :attr:`fnames`.
        """
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
        return self._model

    def read_data(self):
        """
        Load any pending TIFF files and return the complete image stack.

        Only the filenames in :attr:`unloaded_filenames` are read from
        disk; previously loaded frames stored in :attr:`_data` are
        preserved and the new frames are concatenated.

        Two known bad pixels are zeroed out after loading:
        ``(101, 147)`` and ``(98, 170)``.

        Returns
        -------
        numpy.ndarray
            3-D array of shape ``(n_frames, height, width)`` with dtype
            ``float32``, or ``None`` if no files have been loaded yet.
        """
        if len(self.unloaded_filenames) > 0:
            logger.info(f"Reading {len(self.unloaded_filenames)} tiff file(s)")
            data = []
            for fname in self.unloaded_filenames:
                data.append(tifffile.imread(fname))
            data = np.array(data).astype(np.float32)
            data[:, 101, 147] = 0
            data[:, 98, 170] = 0
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

    def rowCount(self, parent=None):
        return len(self.fnames)

    def columnCount(self, parent=None):
        return 1

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            row, _ = index.row(), index.column()
            return os.path.basename(self.fnames[row])

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


if __name__ == "__main__":
    pass
