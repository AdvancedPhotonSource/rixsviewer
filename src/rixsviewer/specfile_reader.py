import os
import sys
import numpy as np
import re
import ast
import glob
from PySide6.QtCore import Qt, QAbstractTableModel
from silx.io.specfile import SpecFile
import pandas as pd
import tifffile


def parse_scan_info(scan_comment_str) -> dict:
    """
    Parse scan metadata from a dictionary-like string and extract key numerical values.

    Extracted fields:
        - scan_start, scan_end
        - ref_channel
        - EB
        - Rowland_radius
        - binning_range
        - datetime
    """
    text = scan_comment_str

    # Regular expressions
    scan_energy = re.search(r"merixE\s+([\d.]+)\s+([\d.]+)", text)
    ref_channel = re.search(r"Detector ref channel\s*=\s*(\d+)", text)
    eb = re.search(r"Analyzer EB\s*=\s*([\d.]+)", text)
    rowland = re.search(r"Rowland radius\s*=\s*(\d+)", text)
    binning = re.search(r"Detector binning range:\s*(\d+)\s+(\d+)", text)
    datetime = re.search(r"Datafile:(\w+)", text)

    return {
        "scan_start": float(scan_energy.group(1)) if scan_energy else None,
        "scan_end": float(scan_energy.group(2)) if scan_energy else None,
        "ref_channel": int(ref_channel.group(1)) if ref_channel else None,
        "EB": float(eb.group(1)) if eb else None,
        "Rowland_radius": int(rowland.group(1)) if rowland else None,
        "binning_range": (int(binning.group(1)), int(binning.group(2))),
        "datetime": datetime.group(1) if datetime else None,
    }


class RixsScanListTable(QAbstractTableModel):
    def __init__(self, fname, parent=None):
        super().__init__(parent)
        self.scanindex_to_tablerow = {}
        self.tablerow_to_scanindex = {}
        self.specfile = SpecFile(fname)
        self._headers = ["Scan #", "Type", "Points"]

    def rowCount(self, parent=None):
        return len(self.specfile)

    def columnCount(self, parent=None):
        return len(self._headers)

    def get_scan_information(self, row):
        header = ["E", "C", "A", "M", "I0", "I2"]
        scan = self.specfile[row]
        scan_data = scan.data.T
        scan_df = pd.DataFrame(scan_data, columns=header)
        scan_meta = parse_scan_info(scan.scan_header_dict["C"])
        scan_df["ThetaB"] = np.arcsin(scan_meta["EB"] / scan_df["E"])
        return {"data": scan_df, "meta": scan_meta}

    def parse_scan(self, scan, row):
        scan_number = scan.number
        if scan_number not in self.scanindex_to_tablerow:
            self.scanindex_to_tablerow[scan_number] = row
            self.tablerow_to_scanindex[row] = scan_number
        if scan.scan_header_dict["C"].startswith("ascan  merixE"):
            scan_type = "SpectrumScan"
        elif scan.scan_header_dict["C"].startswith("Snapshot energy"):
            scan_type = "SnapshotScan"
        else:
            scan_type = "UndefinedScan"

        scan_points = scan.data.shape[1]
        return (scan_number, scan_type, scan_points)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            row, col = index.row(), index.column()
            scan = self.specfile[row]
            scan_info = self.parse_scan(scan, row)
            return scan_info[col]

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


class RixsScanImageDataset:
    def __init__(self, scan_index, folder, scan_info, threshold=4095):
        self.fnames = glob.glob(os.path.join(folder, f"*_scan{scan_index:d}_*.tif"))
        self.fnames.sort()
        self.threshod = threshold
        self.scan_info = scan_info
        self.data = self.read_data()
        self.model = self.get_table_model()

    def get_data_for_display(self):
        mask = self.data[0] > 0
        vmin = 0
        vmax = np.percentile(self.data[0][mask], 99)
        return self.data, (vmin, vmax)

    def bin_data(self, model_config):
        lines = []
        data_1d = np.sum(self.data, axis=1)
        shape = self.data.shape
        Eb = self.scan_info["meta"]["EB"]
        rowland_radius = self.scan_info["meta"]["Rowland_radius"]
        delta_d = model_config.get_parameter("DeltaD")

        for n in range(shape[0]):
            energy_cen = self.scan_info["data"]["E"].iloc[n]
            theta_b = self.scan_info["data"]["ThetaB"].iloc[n]
            # delta_e = energy_cen * delta_d / (2 * rowland_radius) / np.tan(theta_b)
            delta_e = Eb * delta_d / (2 * rowland_radius) / np.tan(theta_b)
            x = energy_cen - (np.arange(shape[2]) - shape[2] // 2) * delta_e
            y = data_1d[n]
            lines.append([x, y])
        return lines

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


def test():
    specfile = SpecFile(fname)
    scan = specfile[90]
    print(scan.number)
    print(scan.scan_header_dict)
    print(scan.header)


if __name__ == "__main__":
    test()
