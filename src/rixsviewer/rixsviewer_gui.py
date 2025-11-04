from PySide6.QtWidgets import QApplication, QMainWindow, QHeaderView, QFileDialog
import sys
import os
import argparse
from .specfile_reader import RixsScanListTable, RixsScanImageDataset
from .rixs_image import RixsBinningModel
from .rixsviewer_ui import Ui_MainWindow
import pyqtgraph as pg
from pyqtgraph.parametertree import Parameter

pg.setConfigOption("background", "w")  # or (255, 255, 255)
pg.setConfigOption("foreground", "k")


class RixsViewerGUI(QMainWindow):
    def __init__(self, spec_filename=None, tiff_folder=None):
        super().__init__()

        # Set up the UI
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        if tiff_folder:
            self.tiff_folder = tiff_folder
            self.ui.lineEdit.setText(self.tiff_folder)

        if spec_filename:
            self.ui.lineEdit_specfilename.setText(spec_filename)
            self.setup_scan_table(spec_filename)

        # Connect signals
        self.ui.toolButton_load_specfile.clicked.connect(self.on_load_specfile_clicked)
        self.ui.toolButton_set_tifffolder.clicked.connect(
            self.on_set_tifffolder_clicked
        )
        self.current_rixs_dset = None

        self.init_plot_hdl()
        self.ui.pushButton_process.clicked.connect(self.process_binning)

        # Initialize the RixsBinningModel and set up parameter tree
        self.setup_parameter_tree()

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

        # Connect parameter changes to update the binning model
        self.params.sigTreeStateChanged.connect(self.on_parameter_changed)

        # Set the parameter tree to display these parameters
        self.ui.widget_ptree.setParameters(self.params, showTop=False)

    def on_parameter_changed(self, param, changes):
        """Handle parameter tree changes and sync with binning model"""
        self.binning_model.update_from_parameter(param, changes)

    def init_plot_hdl(self):
        self.plot_hdl = self.ui.widget_binhdl.addPlot()

    def process_binning(self):
        if self.current_rixs_dset is None:
            return

        lines = self.current_rixs_dset.bin_data()
        self.plot_hdl.clear()
        pen = pg.mkPen(color="blue", width=1)
        for x, y in lines:
            self.plot_hdl.plot(x, y, pen=pen)
        self.plot_hdl.setLabel("left", "Intensity")
        self.plot_hdl.setLabel("bottom", "Energy (keV)")

    def on_load_specfile_clicked(self):
        """Handle the load spec file button click"""
        # Open file dialog to select a spec file
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open SPEC File", "", "SPEC Files (*.spm3);;All Files (*)"
        )

        # If a file was selected, update the line edit and reload the scan table
        if file_path:
            self.ui.lineEdit_specfilename.setText(file_path)
            self.setup_scan_table(file_path)

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

    def setup_scan_table(self, spec_filename):
        """Set up the scan table with the RixsScanListTable model"""
        # Create the model
        self.scan_model = RixsScanListTable(spec_filename)

        # Connect the model to the tableView_scan
        self.ui.tableView_scan.setModel(self.scan_model)

        # Configure column stretching to use all available space
        header = self.ui.tableView_scan.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)

        # Connect click signal to handler
        self.ui.tableView_scan.clicked.connect(self.on_scan_table_clicked)

    def on_scan_table_clicked(self, index):
        """Handle clicks on the scan table and print the row number"""
        row_number = index.row()
        scan_index = self.scan_model.tablerow_to_scanindex[row_number]
        threshold = self.binning_model.get_parameter("threshold")
        scan_data = self.scan_model.get_scan(row_number)
        self.current_rixs_dset = RixsScanImageDataset(
            scan_index,
            folder=self.tiff_folder,
            scan_data=scan_data,
            threshold=threshold,
        )
        self.ui.tableView_image.setModel(self.current_rixs_dset.model)
        header = self.ui.tableView_image.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.ui.widget_imgview.setImage(
            self.current_rixs_dset.data, axes={"t": 0, "y": 1, "x": 2}
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
        default="/scratch/MQICHU/Datasets/rixs/rixsviewer_dataset/21Mar2025.spm3",
        help="Path to the SPEC file to load (default: %(default)s)",
    )
    parser.add_argument(
        "--tiff-folder",
        default="/scratch/MQICHU/Datasets/rixs/rixsviewer_dataset/slot8/cray_clean/",
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
