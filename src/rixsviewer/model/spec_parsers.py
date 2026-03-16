import glob
import logging
import math
import os
import re

import pandas as pd
from silx.io.specfile import SpecFile

logger = logging.getLogger(__name__)


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
    fnames = glob.glob(os.path.join(tif_folder, f"{basename}_scan{scan_number}_point*.tif"))
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

    # Guard against empty scans (num_rows == 0): scan.data will have shape
    # (num_columns, 0), so after .T it becomes (0, 0), which causes a pandas
    # shape-mismatch when column names are supplied.  Return an empty DataFrame
    # with the correct column schema instead of crashing.
    if scandata.shape[0] == 0:
        logger.debug(
            "Skipping empty scan (no data rows); returning empty DataFrame "
            "with %d columns: %s",
            len(header),
            header,
        )
        return pd.DataFrame(columns=header)

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
    analyzer_crystal_size_mm = re.search(r"Analyzer_Crystal_Size_mm\s*=\s*([\d.]+)", text)
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
        "TiltAngle": 0.0,
    }

    # Keep binning_range for backward compatibility
    # result["binning_range"] = (result["Ylow"], result["Yhigh"])

    return result
