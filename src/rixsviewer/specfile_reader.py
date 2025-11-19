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
    def __init__(self, fname, tif_folder, parent=None):
        super().__init__(parent)
        self.scanindex_to_tablerow = {}
        self.tablerow_to_scanindex = {}
        self.specfile = SpecFile(fname)
        self.tif_folder = tif_folder
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

    def get_selected_dataset(self, rows, threshold, RefL=70):
        dset_types = list(set([self.parse_scan(row)[1] for row in rows]))
        if len(dset_types) > 1:
            logger.error("Error: mixed type of dataset selected")
            return None

        if dset_types[0] == "SpectrumScan":
            _scan_info = self.get_scan_information(rows[0])
            index = self.tablerow_to_scanindex[rows[0]]
            fnames = glob.glob(os.path.join(self.tif_folder, f"*_scan{index}_*.tif"))
            fnames.sort()
            dset = RixsScanImageDataset(
                fnames,
                scan_info=_scan_info,
                scan_type="SpectrumScan",
                threshold=threshold,
            )
            return dset
        else:
            fnames = []
            scan_data_list = []
            prev_scan_info = None
            for row in rows:
                _scan_info = self.get_scan_information(row)
                _scan_info.pop("datetime", None)  # allow multi-day measurements
                index = self.tablerow_to_scanindex[row]
                _fnames = glob.glob(
                    os.path.join(self.tif_folder, f"*_scan{index}_*.tif")
                )
                if len(_fnames) == 1:
                    if (
                        prev_scan_info is None
                        or prev_scan_info["meta"] == _scan_info["meta"]
                    ):
                        scan_data_list.append(_scan_info["data"].iloc[0])
                        fnames.extend(_fnames)
                        prev_scan_info = _scan_info

            if len(fnames) == 0:
                logger.error("Error: no TIFF files found for the selected scans")
                return None
            else:
                # fnames.sort()
                prev_scan_info["data"] = pd.DataFrame(scan_data_list)
                dset = RixsScanImageDataset(
                    fnames,
                    scan_info=prev_scan_info,
                    scan_type="SnapshotScan",
                    threshold=threshold,
                )
                return dset

    def parse_scan(self, row):
        scan = self.specfile[row]
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
            scan_info = self.parse_scan(row)
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
    def __init__(self, fnames, scan_info, scan_type, threshold=4095):
        self.fnames = fnames
        self.scan_type = scan_type
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

        Eb = self.scan_info["meta"]["EB"]
        rowland_radius = self.scan_info["meta"]["Rowland_radius"]
        theta_b = self.scan_info["data"]["ThetaB"]
        energy_cen = np.array(self.scan_info["data"]["E"]).reshape(-1, 1)

        scale = np.array(Eb / (2 * rowland_radius) / np.tan(theta_b))

        if fit_pixel_size and self.scan_type == "SnapshotScan":
            logger.warning("fit_pixel_size is not implemented for SnapshotScan")
            fit_pixel_size = False

        if fit_pixel_size and self.scan_type == "SpectrumScan":
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
