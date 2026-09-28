# Copyright © UChicago Argonne LLC
# See LICENSE file for details
import logging
import math
import re
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_POINT_INDEX_PATTERN = re.compile(r"_point(\d+)\.tif$")


def tiff_point_index(path):
    """
    Extract the numeric point index from a TIFF filename for natural sorting.

    Filenames are zero-padded to 3 digits only (``point001``..``point999``,
    then unpadded from ``point1000`` on), so a plain lexicographic sort
    silently reorders frames once a scan exceeds ~100 points (e.g.
    ``..._point182.tif`` sorts between ``_point1819.tif`` and
    ``_point1820.tif``). Use as the ``key=`` for :func:`sorted`.

    Parameters
    ----------
    path : str or pathlib.Path

    Returns
    -------
    int
        The point index, or ``-1`` if the filename doesn't match the
        expected pattern (sorts unmatched names first).
    """
    m = _POINT_INDEX_PATTERN.search(str(path))
    return int(m.group(1)) if m else -1


_ENERGY_SCAN_PATTERN = re.compile(
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

_RXES_SCAN_PATTERN = re.compile(
    r"""^
        \s*(\d+)\s+          # scan number
        rxesamesh\s+         # nested 2D mesh macro
        merixE\s+            # analyzer/emission energy motor (outer loop)
        ([+-]?\d*\.?\d+)\s+  # emission start
        ([+-]?\d*\.?\d+)\s+  # emission end
        (\d+)\s+             # emission intervals
        kohzuE\s+            # incident energy motor (inner loop)
        ([+-]?\d*\.?\d+)\s+  # incident start
        ([+-]?\d*\.?\d+)\s+  # incident end
        (\d+)\s+             # incident intervals
        ([+-]?\d*\.?\d+)\s*  # time
    $""",
    re.VERBOSE,
)


def get_scan_header(scan, tol=1e-6):
    """
    Classify a silx SpecFile scan's ``#S`` header line.

    Recognises three shapes:

    - ``rxesamesh merixE ... kohzuE ...`` -> ``'RXESScan'``, a nested 2D
      mesh over analyzer/emission (``merixE``, outer loop) and incident
      (``kohzuE``, inner loop) energy.
    - ``<word>scan merixE ...`` -> ``'EnergyScan'``, or ``'SnapshotScan'``
      when start and end are equal within *tol*.
    - anything else -> ``'Unknown'``.

    Parameters
    ----------
    scan : silx.io.specfile.Scan
    tol : float, optional
        Absolute tolerance for comparing start and end energies, by default ``1e-6``.

    Returns
    -------
    dict
        Keys: ``scan_type``, ``steps``, ``exposure_time``, ``start``, ``end``.
        ``RXESScan`` additionally has ``incident_start``, ``incident_end``,
        ``incident_points``, ``emission_start``, ``emission_end``,
        ``emission_points``; ``steps`` is the total point count
        (``incident_points * emission_points``).
        All values are zero/``'Unknown'`` when the header line cannot be parsed.
    """
    header_line = scan.scan_header_dict["S"]

    m = _RXES_SCAN_PATTERN.search(header_line)
    if m:
        emission_start, emission_end = float(m.group(2)), float(m.group(3))
        emission_points = int(m.group(4)) + 1
        incident_start, incident_end = float(m.group(5)), float(m.group(6))
        incident_points = int(m.group(7)) + 1
        return {
            "scan_type": "RXESScan",
            "steps": incident_points * emission_points,
            "exposure_time": float(m.group(8)),
            "start": incident_start,
            "end": incident_end,
            "incident_start": incident_start,
            "incident_end": incident_end,
            "incident_points": incident_points,
            "emission_start": emission_start,
            "emission_end": emission_end,
            "emission_points": emission_points,
        }

    m = _ENERGY_SCAN_PATTERN.search(header_line)
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
        (str(p) for p in Path(tif_folder).glob(f"{basename}_scan{scan.number}_point*.tif")),
        key=tiff_point_index,
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
        "incident_start": header.get("incident_start"),
        "incident_end": header.get("incident_end"),
        "incident_points": header.get("incident_points"),
        "emission_start": header.get("emission_start"),
        "emission_end": header.get("emission_end"),
        "emission_points": header.get("emission_points"),
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
    - TiltAngle: Detector tilt angle (degrees); defaults to 0.0 when the
      'TiltAngle_deg' key is absent (older datasets)
    - NEnergyBins: Number of energy bins; defaults to 0 when absent

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
    tilt_angle_m = re.search(r"TiltAngle_deg\s*=\s*([+-]?[\d.]+)", scan_comment_str)

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
        "TiltAngle": float(tilt_angle_m.group(1)) if tilt_angle_m else 0.0,
        "NEnergyBins": int(float(n_energy_bins_m.group(1))) if n_energy_bins_m else 0,
    }
