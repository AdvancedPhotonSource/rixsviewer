import os
import numpy as np
import re
import glob
from PySide6.QtCore import Qt, QAbstractTableModel
from silx.io.specfile import SpecFile
import pandas as pd
import tifffile
import logging

logger = logging.getLogger(__name__)


def parse_single_scan(scan):
    scan_number = scan.number
    scan_type = "Unknown"
    if "Y" in scan.scan_header_dict:
        scan_signature = scan.scan_header_dict["Y"]
        if scan_signature.startswith("EnergyScan"):
            scan_type = "EnergyScan"
        elif scan_signature.startswith("SnapshotScan"):
            scan_type = "SnapshotScan"

    if scan_type == "Unknown":
        return None, None

    scandata = get_scandata_information(scan)

    info = {
        "scan_number": scan_number,
        "scan_type": scan_type,
        "actual_points": scandata.shape[0],
        "metadata": get_metadata_from_header(scan.scan_header_dict["B"]),
        "scandata": scandata,
    }

    return scan_number, info


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
        self.tif_folder = tif_folder
        self.last_modtime = -1
        self._headers = ["Scan#", "Type", "ExpectedPoints", "ActualPoints"]
        self.record = []
        self.process_spec_file()

    def process_spec_file(self):
        last_modtime = os.path.getmtime(self.spec_fname)
        if last_modtime == self.last_modtime:
            return
        else:
            self.last_modtime = last_modtime

        self.record = []  # empty the record
        specfile = SpecFile(self.spec_fname)
        for scan_index in range(len(specfile)):
            scan_pack = specfile[scan_index]
            scan_type, scan_info = parse_single_scan(scan_pack)
            if scan_type is not None:
                self.record.append(scan_info)

    def rowCount(self, parent=None):
        return len(self.record)

    def columnCount(self, parent=None):
        return len(self._headers)

    def get_selected_dataset(self, row, threshold, RefL=70):
        scan_info = self.record[row]
        if scan_info["scan_type"] == "EnergyScan":
            scan_number = scan_info["scan_number"]
            basename = os.path.basename(self.spec_fname)
            fnames = glob.glob(
                os.path.join(
                    self.tif_folder, f"{basename}_scan{scan_number}_point*.tif"
                )
            )
            fnames.sort()
            dset = RixsScanTiffDataset(
                fnames,
                scan_info=scan_info,
                threshold=threshold,
            )
            return dset

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            row, col = index.row(), index.column()
            key = {
                0: "scan_number",
                1: "scan_type",
                2: "actual_points",
                3: "actual_points",
            }[col]
            return self.record[row][key]

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
    def __init__(self, fnames, scan_info, threshold=4095):
        self.fnames = fnames
        self.threshod = threshold
        self.scan_info = scan_info
        self.data = self.read_data()
        self.model = self.get_table_model()

    def get_data_for_display(self, data=None):
        if data is None:
            data = self.data
        mask = data[0] > 0
        vmin = 0
        vmax = np.percentile(data[0][mask], 99)
        return data, (vmin, vmax)

    def bin_data(self, DeltaD=0.022, xref=70, fit_pixel_size=True, **kwargs):
        shape = self.data.shape
        data_1d = np.sum(self.data, axis=1)
        # pad values after xrefl
        data_1d[:, 2 * xref :] = np.mean(data_1d[:, 2 * xref])

        xaxis = np.arange(shape[2]) - xref
        # center of mass in pixels for the peak position;
        com_pixel = np.sum(data_1d * xaxis, axis=1) / np.sum(data_1d, axis=1)

        Eb = self.scan_info["meta"]["Eb"]
        rowland_radius = self.scan_info["meta"]["Ra"]
        theta_b = self.scan_info["data"]["ThetaB"]
        energy_cen = np.array(self.scan_info["data"]["E"]).reshape(-1, 1)

        scale = np.array(Eb / (2 * rowland_radius) / np.tan(theta_b))

        if fit_pixel_size and self.scan_type == "SnapshotScan":
            logger.warning("fit_pixel_size is not implemented for SnapshotScan")
            fit_pixel_size = False

        if fit_pixel_size and self.scan_type == "EnergyScan":
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

        if self.scan_type == "SnapshotScan":
            summed_data = np.sum(self.data, axis=0)
            summed_data, levels = self.get_data_for_display(summed_data)
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
        return RixsScanImageTable(self.fnames)

    def read_data(self):
        data = []
        for fname in self.fnames:
            data.append(tifffile.imread(fname))
        data = np.array(data)
        data[data >= self.threshod] = 0
        return data


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
