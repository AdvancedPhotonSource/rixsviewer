import os
import sys
import glob
from PySide6.QtCore import Qt, QAbstractTableModel
from silx.io.specfile import SpecFile

fname = "/scratch/MQICHU/Datasets/rixs/rixsviewer_dataset/21Mar2025.spm3"


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


class RixsScanImageTable(QAbstractTableModel):
    def __init__(
        self,
        scan_index,
        folder="/scratch/MQICHU/Datasets/rixs/rixsviewer_dataset/slot8/cray_clean/",
        parent=None,
    ):
        super().__init__(parent)
        self.fnames = glob.glob(os.path.join(folder, f"*_scan{scan_index:d}_*.tif"))
        self.fnames.sort()
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
