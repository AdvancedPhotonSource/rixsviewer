import logging
import os

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from silx.io.specfile import SpecFile

from .spec_parsers import get_scan_type, parse_single_scan
from .scan_dataset import RixsScanTiffDataset

logger = logging.getLogger(__name__)


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

    def __init__(self, fname, tif_folder, save_filename, parent=None):
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
        self.save_filename = save_filename
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
            return False

        has_updates = False
        scan_dset = None
        for scan_pack in self.spec_container:
            scan_number = scan_pack.number
            # no need to re-process old scans
            if scan_number < self.last_scan_index:
                continue

            if get_scan_type(scan_pack)[0] in ["EnergyScan", "SnapshotScan"]:
                if scan_number in self.record:
                    scan_dset = self.record[scan_number]
                    prev_tiff = scan_dset.scan_info["tiff_points"] if scan_dset.scan_info else -1
                    scan_dset.update_scan_info(scan_pack)
                    if scan_dset.scan_info["tiff_points"] != prev_tiff:
                        has_updates = True
                        # update the view for this row
                        row = scan_dset.row_position
                        index_top_left = self.index(row, 0)
                        index_bottom_right = self.index(row, self.columnCount() - 1)
                        self.dataChanged.emit(index_top_left, index_bottom_right)
                else:
                    has_updates = True
                    # new scan dataset; save the previous scan
                    if self.last_scan_dset is not None:
                        self.last_scan_dset.save_to_file(self.save_filename)
                    row = len(self.record)
                    scan_dset = RixsScanTiffDataset(row, self.spec_fname, self.tif_folder, scan_number)
                    scan_dset.update_scan_info(scan_pack)
                    self.beginInsertRows(QModelIndex(), row, row)
                    self.record[scan_number] = scan_dset
                    self.endInsertRows()
                    self.last_scan_index = max(self.last_scan_index, scan_number)
        if scan_dset is not None:
            self.last_scan_dset = scan_dset
        return has_updates

    def rowCount(self, parent=None):
        return len(self.record)

    def columnCount(self, parent=None):
        return len(self._headers)

    def get_scan_number(self, row):
        return list(self.record.keys())[row]

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
        scan_index = self.get_scan_number(row)
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
            scan_number = self.get_scan_number(row)
            scan_tiff_dset = self.record[scan_number]
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
