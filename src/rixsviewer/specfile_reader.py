import os
import numpy as np
import re
import glob
import math
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from silx.io.specfile import SpecFile
import pandas as pd
import tifffile
import logging

logger = logging.getLogger(__name__)


def percentile_clip(data):
    if data.size == 0:
        return (0, 0)
    if data.ndim == 2:
        mask = data > 0
        vmax = np.percentile(data[mask], 99)
    elif data.ndim == 3:
        mask = data[0] > 0
        vmax = np.percentile(data[0][mask], 99)
    return (0, vmax)


def get_scan_type(scan) -> str:
    scan_type = "Unknown"
    # if "Y" in scan.scan_header_dict and "L" in scan.scan_header_dict:
    #     scan_signature = scan.scan_header_dict["Y"]
    #     if scan_signature.startswith("EnergyScan"):
    #         scan_type = "EnergyScan"
    #     elif scan_signature.startswith("SnapshotScan"):
    #         scan_type = "SnapshotScan"

    if scan_type != "Unknown":
        return scan_type
    else:
        # for on-going scans; the #Y line doesn't seem to be recognized correctly;
        scan_type, steps = get_scan_type_from_scanstring(scan.scan_header_dict["S"])
        return scan_type, steps


def get_scan_type_from_scanstring(text, tol=1e-6):
    """
    Classify a spec scan header line (without '#S') as SnapshotScan or EnergyScan,
    but only if the motor name is exactly 'merixE'.
    Example text: "286  ascan  merixE 11.2146 11.2154  80 1"
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
        return "Unknown"

    start = float(m.group(3))
    end = float(m.group(4))
    steps = int(m.group(5)) + 1

    if math.isclose(start, end, rel_tol=0, abs_tol=tol):
        scan_type = "SnapshotScan"
    else:
        scan_type = "EnergyScan"

    return scan_type, steps


def parse_single_scan(scan, spec_fname, tif_folder):
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
    basename = os.path.basename(spec_fname)
    fnames = glob.glob(
        os.path.join(tif_folder, f"{basename}_scan{scan_number}_point*.tif")
    )
    fnames.sort()
    return fnames


def get_scandata_information(scan):
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
        "RefL": float(center_x_pixel.group(1)),
        "Ylow": int(float(low_y_pixel.group(1))),
        "Yhigh": int(float(high_y_pixel.group(1))),
        "Acrystalsize": float(analyzer_crystal_size_mm.group(1)),
        "DeltaD": float(lambda_strip_size_mm.group(1)),
    }

    # Keep binning_range for backward compatibility
    result["binning_range"] = (result["Ylow"], result["Yhigh"])

    return result


class RixsSpecTable(QAbstractTableModel):
    def __init__(self, fname, tif_folder, parent=None):
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
        last_modtime = os.path.getmtime(self.spec_fname)
        if last_modtime == self.last_modtime and self.spec_container is not None:
            return False
        else:
            self.last_modtime = last_modtime
        self.spec_container = SpecFile(self.spec_fname)
        return True

    def process_spec_file(self):
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
    def __init__(self, row_position, spec_fname, tif_folder, threshold=4095):
        self.row_position = row_position
        self.spec_fname = spec_fname
        self.tif_folder = tif_folder
        self.threshold = threshold
        self._model = None
        self._data = None
        self.unloaded_filenames = []
        self.scan_info = None

    def update_scan_info(self, scan_pack):
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
        key = {
            0: "scan_number",
            1: "scan_type",
            2: "spec_points",
            3: "tiff_points",
        }[col]
        return self.scan_info[key]

    def get_data_for_display(self):
        self._data = self.read_data()
        levels = percentile_clip(self._data)
        return self._data, levels

    def bin_data(self, DeltaD=0.022, xref=70, fit_pixel_size=True, **kwargs):
        self._data = self.read_data()
        shape = self._data.shape
        data_1d = np.sum(self._data, axis=1)
        # pad values after xrefl
        data_1d[:, 2 * xref :] = np.mean(data_1d[:, 2 * xref])

        xaxis = np.arange(shape[2]) - xref

        Eb = self.scan_info["metadata"]["Eb"]
        rowland_radius = self.scan_info["metadata"]["Ra"]
        theta_b = np.arcsin(
            self.scan_info["metadata"]["Eb"] / self.scan_info["scandata"]["merixE"]
        )
        energy_cen = np.array(self.scan_info["scandata"]["merixE"]).reshape(-1, 1)

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
            logger.info(f"Fitted effective pixel size: {effective_pixel_size} mm")
        else:
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
        bin_data_norm = np.nansum(~np.isnan(bin_data), axis=0)
        bin_data_mean = bin_data_sum / np.clip(bin_data_norm, a_min=1, a_max=None)

        eff_data_len = np.sum(~np.isnan(bin_data), axis=0)
        bin_data_err = np.nanstd(bin_data, axis=0) / np.sqrt(eff_data_len)

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
        return len(self.fnames)

    def get_table_model(self):
        if self._model is None:
            self._model = RixsScanImageTable(self.scan_info["filenames"])
        return self._model

    def read_data(self):
        if len(self.unloaded_filenames) > 0:
            logger.info(f"Reading {len(self.unloaded_filenames)} tiff files")
            data = []
            for fname in self.unloaded_filenames:
                data.append(tifffile.imread(fname))
            data = np.array(data)
            data[data >= self.threshold] = 0
            if self._data is None:
                self._data = data
            else:
                self._data = np.concatenate([self._data, data], axis=0)
            self.unloaded_filenames = []
        return self._data


class RixsScanImageTable(QAbstractTableModel):
    def __init__(
        self,
        fnames,
        parent=None,
    ):
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
        return self.fnames[row]


if __name__ == "__main__":
    pass
