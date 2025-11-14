from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QHeaderView,
    QFileDialog,
    QMessageBox,
)
import sys
import argparse
from .specfile_reader import RixsScanListTable
from .rixs_image import RixsBinningModel
from .rixsviewer_ui import Ui_MainWindow
import numpy as np
import pyqtgraph as pg
from pyqtgraph.parametertree import Parameter
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

pg.setConfigOption("background", "w")  # or (255, 255, 255)
pg.setConfigOption("foreground", "k")
logger = logging.getLogger(__name__)


class RixsViewerGUI(QMainWindow):
    def __init__(self, spec_filename=None, tiff_folder=None):
        super().__init__()

        # Set up the UI
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.scan_model = None
        self.current_rixs_dset = None

        self.tiff_folder = tiff_folder
        self.spec_filename = spec_filename

        if tiff_folder:
            self.ui.lineEdit.setText(self.tiff_folder)
        if spec_filename:
            self.ui.lineEdit_specfilename.setText(spec_filename)

        # Connect signals
        self.ui.toolButton_load_specfile.clicked.connect(self.on_load_specfile_clicked)
        self.ui.toolButton_set_tifffolder.clicked.connect(
            self.on_set_tifffolder_clicked
        )
        self.ui.pushButton_load_scan.clicked.connect(self.setup_scan_table)
        self.init_plot_hdl()
        self.ui.pushButton_process.clicked.connect(self.process_binning)

        # Initialize the RixsBinningModel and set up parameter tree
        self.setup_parameter_tree()
        self.setup_scan_table()

    def setup_parameter_tree(self):
        """Set up the parameter tree with RixsBinningModel parameters"""
        # Create the RixsBinningModel instance
        self.binning_model = RixsBinningModel()

        # Create a Parameter object from the binning model parameters
        self.params = Parameter.create(
            name="RIXS Binning Parameters",
            type="group",
            children=self.binning_model.params,
        )

        # Connect the parameter tree to the model for bidirectional sync
        self.binning_model.param_tree = self.params

        # Connect parameter changes to update the binning model
        self.params.sigTreeStateChanged.connect(self.on_parameter_changed)

        # Set the parameter tree to display these parameters
        self.ui.widget_ptree.setParameters(self.params, showTop=False)

    def on_parameter_changed(self, param, changes):
        """Handle parameter tree changes and sync with binning model"""
        self.binning_model.update_from_parameter(param, changes)

    def init_plot_hdl(self):
        self.plot_hdl = self.ui.widget_binhdl.addPlot()
        cmap = pg.colormap.get("plasma")
        self.ui.widget_imgview.setColorMap(cmap)

    def process_binning(self):
        if self.current_rixs_dset is None:
            return

        fit_pixel_size = self.ui.checkBox_fit_pixel_size.isChecked()
        show_rawdata = self.ui.checkBox_show_rawdata.isChecked()

        result = self.current_rixs_dset.bin_data(
            fit_pixel_size=fit_pixel_size, **self.binning_model.get_kwargs()
        )

        self.plot_hdl.clear()
        if show_rawdata:
            for x, y in result["rawdata_lines"]:
                color = tuple(np.random.randint(100, 256, size=3))  # avoid dark colors
                pen = pg.mkPen(color=color, width=1)
                self.plot_hdl.plot(x, y, pen=pen)

        # plot the binned line with error bars
        x, y, err = result["binned_line"]
        pen = pg.mkPen(color=(0, 0, 255), width=1)
        self.plot_hdl.plot(x, y, pen=pen)

        # --- Error bar item ---
        err_plot = pg.ErrorBarItem(x=x, y=y, top=err, bottom=err, beam=0.00001)
        self.plot_hdl.addItem(err_plot)

        self.plot_hdl.setLabel("left", "Intensity")
        self.plot_hdl.setLabel("bottom", "Energy (keV)")

        if fit_pixel_size:
            # Show confirmation dialog before updating DeltaD parameter
            fitted_value = float(result["DeltaD_fit"])
            reply = QMessageBox.question(
                self,
                "Update DeltaD Parameter",
                f"Update DeltaD parameter with fitted value {fitted_value:.6f} µm?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )

            if reply == QMessageBox.Yes:
                self.binning_model.put_parameter("DeltaD", fitted_value)

        if result["summed_data"] is not None:
            self.ui.widget_imgview.setImage(
                result["summed_data"], axes={"y": 0, "x": 1}, levels=result["levels"]
            )

    def on_load_specfile_clicked(self):
        """Handle the load spec file button click"""
        # Open file dialog to select a spec file
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open SPEC File", "", "SPEC Files (*.spm3);;All Files (*)"
        )

        # If a file was selected, update the line edit and reload the scan table
        if file_path:
            self.ui.lineEdit_specfilename.setText(file_path)

    def on_set_tifffolder_clicked(self):
        """Handle the set TIFF folder button click"""
        # Open directory dialog to select a folder
        folder_path = QFileDialog.getExistingDirectory(
            self, "Select TIFF Folder", self.tiff_folder
        )

        # If a folder was selected, update the line edit and store the path
        if folder_path:
            self.tiff_folder = folder_path
            self.ui.lineEdit.setText(folder_path)

    def setup_scan_table(self):
        """Set up the scan table with the RixsScanListTable model"""
        # Create the model

        if self.tiff_folder is None or self.spec_filename is None:
            return None

        try:
            scan_model = RixsScanListTable(self.spec_filename, self.tiff_folder)
        except Exception as e:
            logger.error(f"Error loading SPEC file: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load SPEC file:\n{e}",
            )
            return None

        # Connect the model to the tableView_scan
        self.ui.tableView_scan.setModel(scan_model)

        # Configure column stretching to use all available space
        header = self.ui.tableView_scan.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)

        # Connect click signal to handler
        # self.ui.tableView_scan.clicked.connect(self.on_scan_table_clicked)
        self.ui.tableView_scan.selectionModel().selectionChanged.connect(
            self.on_selection_changed
        )
        self.scan_model = scan_model
        return

    def on_selection_changed(self, selected, deselected):
        """
        Called whenever the table's selection changes.
        'selected' and 'deselected' are QItemSelection objects.
        """
        selected_indexes = self.ui.tableView_scan.selectionModel().selectedIndexes()
        rows = [index.row() for index in selected_indexes]
        threshold = self.binning_model.get_parameter("threshold")
        dset = self.scan_model.get_selected_dataset(rows, threshold)
        if dset is None:
            return

        self.current_rixs_dset = dset
        self.ui.tableView_image.setModel(self.current_rixs_dset.model)
        header = self.ui.tableView_image.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        data, levels = self.current_rixs_dset.get_data_for_display()
        self.ui.widget_imgview.setImage(
            data, axes={"t": 0, "y": 1, "x": 2}, levels=levels
        )
        self.ui.tableView_image.clicked.connect(self.on_image_table_clicked)

    def on_image_table_clicked(self, index):
        self.ui.widget_imgview.setCurrentIndex(index.row())


def main():
    """Main entry point for the application"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="RixsViewer - A tool for visualization and modeling of RIXS (Resonance Inelastic X-ray Scattering) data"
    )
    parser.add_argument(
        "specfile",
        nargs="?",
        default="/home/beams/RIXS/Data/2025-1/slot8_Zivkovic/21Mar2025.spm3",
        help="Path to the SPEC file to load (default: %(default)s)",
    )
    parser.add_argument(
        "--tiff-folder",
        default="/net/s27data/export/sector27/lambda/2025-1/slot8/cray_clean",
        help="Path to the TIFF folder (default: %(default)s)",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")

    # Parse arguments (filter out Qt arguments)
    args, qt_args = parser.parse_known_args()

    # Create QApplication with remaining arguments
    app = QApplication([sys.argv[0]] + qt_args)

    # Create and show the GUI
    gui = RixsViewerGUI(spec_filename=args.specfile, tiff_folder=args.tiff_folder)
    gui.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
