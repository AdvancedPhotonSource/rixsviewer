# Copyright © UChicago Argonne LLC
# See LICENSE file for details
import logging
import math
import re
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def get_scan_header(scan, tol=1e-6):
    """
    Classify a silx SpecFile scan as ``'EnergyScan'``, ``'SnapshotScan'``, or ``'Unknown'``.

    Parses the ``#S`` header line, which must have motor name ``merixE``.
    A scan is a *SnapshotScan* when start and end energies are equal within
    *tol*; otherwise it is an *EnergyScan*.

    Parameters
    ----------
    scan : silx.io.specfile.Scan
    tol : float, optional
        Absolute tolerance for comparing start and end energies, by default ``1e-6``.

    Returns
    -------
    dict
        Keys: ``scan_type``, ``steps``, ``exposure_time``, ``start``, ``end``.
        All values are zero/``'Unknown'`` when the header line cannot be parsed.
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
    m = pattern.search(scan.scan_header_dict["S"])
    if not m:
        return {
            "scan_type": "Unknown",
            "steps": 0,
            "exposure_time": 0,
            "start": 0.0,
            "end": 0.0,
        }

    start, end = float(m.group(3)), float(m.group(4))
    scan_type = (
        "SnapshotScan"
        if math.isclose(start, end, rel_tol=0, abs_tol=tol)
        else "EnergyScan"
    )
    return {
        "scan_type": scan_type,
        "steps": int(m.group(5)) + 1,
        "exposure_time": float(m.group(6)),
        "start": start,
        "end": end,
    }


def parse_single_scan(scan, spec_fname, tif_folder):
    """
    Build a metadata dictionary for a single SPEC scan.

    Parameters
    ----------
    scan : silx.io.specfile.Scan
    spec_fname : str
        Absolute path to the SPEC data file.
    tif_folder : str
        Directory containing TIFF files for the scan.

    Returns
    -------
    dict
        Keys: ``scan_number``, ``scan_type``, ``spec_points``, ``tiff_points``,
        ``metadata``, ``scandata``, ``filenames``, ``exposure_time``.
    """
    header = get_scan_header(scan)

    basename = Path(spec_fname).name
    filenames = sorted(
        str(p) for p in Path(tif_folder).glob(f"{basename}_scan{scan.number}_point*.tif")
    )

    # metadata key changed from "B" to "XB"; check both for backward compatibility
    metadata_str = scan.scan_header_dict.get("XB") or scan.scan_header_dict["B"]

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
    }


def _get_scandata(scan):
    header = scan.scan_header_dict["L"].split()
    scandata = scan.data.T
    # scan.data has shape (num_columns, 0) for empty scans; .T → (0, 0) causes
    # a pandas shape-mismatch when column names are supplied.
    if scandata.shape[0] == 0:
        logger.debug("Empty scan; returning empty DataFrame with columns: %s", header)
        return pd.DataFrame(columns=header)
    return pd.DataFrame(scandata, columns=header)


def _get_metadata(scan_comment_str: str) -> dict:
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

    Raises
    ------
    ValueError
        If any required field is missing from the header string.
    """

    def _get(pattern: str, field: str) -> str:
        m = re.search(pattern, scan_comment_str)
        if m is None:
            raise ValueError(f"Required field '{field}' not found in scan header")
        return m.group(1)

    n_energy_bins_m = re.search(r"N_Energy_Bins\s*=\s*([\d.]+)", scan_comment_str)

    return {
        "Eb": float(_get(r"Analyzer_EB_keV\s*=\s*([\d.]+)", "Analyzer_EB_keV")),
        "Ra": float(_get(r"Rowland_Radius_m\s*=\s*([\d.]+)", "Rowland_Radius_m")),
        "RefL": int(float(_get(r"Center_x_pixel\s*=\s*([\d.]+)", "Center_x_pixel"))),
        "Ylow": int(float(_get(r"Low_y_pixel\s*=\s*([\d.]+)", "Low_y_pixel"))),
        "Yhigh": int(float(_get(r"High_y_pixel\s*=\s*([\d.]+)", "High_y_pixel"))),
        "Acrystalsize": float(
            _get(r"Analyzer_Crystal_Size_mm\s*=\s*([\d.]+)", "Analyzer_Crystal_Size_mm")
        ),
        "DeltaD": float(
            _get(r"Lambda_Strip_Size_mm\s*=\s*([\d.]+)", "Lambda_Strip_Size_mm")
        ),
        "TiltAngle": 0.0,
        "NEnergyBins": int(float(n_energy_bins_m.group(1))) if n_energy_bins_m else 0,
    }
