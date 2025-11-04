from PySide6.QtWidgets import QApplication, QMainWindow, QHeaderView, QFileDialog
import sys
import os
import argparse
from .specfile_reader import RixsScanListTable, RixsScanImageTable
from .rixs_image import RixsTiffImage, RixsBinningModel
from .rixsviewer_ui import Ui_MainWindow
import pyqtgraph as pg
from pyqtgraph.parametertree import Parameter

pg.setConfigOption("background", "w")  # or (255, 255, 255)
pg.setConfigOption("foreground", "k")


class RixsViewerGUI(QMainWindow):
    def __init__(self, spec_filename=None):
        super().__init__()

        # Set up the UI
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Connect signals
        self.ui.toolButton_load_specfile.clicked.connect(self.on_load_specfile_clicked)

        # Initialize the RixsBinningModel and set up parameter tree
        self.setup_parameter_tree()

        # Set up the scan table model if a spec file is provided
        if spec_filename:
            self.ui.lineEdit_specfilename.setText(spec_filename)
            self.setup_scan_table(spec_filename)

    def setup_parameter_tree(self):
        """Set up the parameter tree with RixsBinningModel parameters"""
        # Create the RixsBinningModel instance
        self.binning_model = RixsBinningModel()
        
        # Create a Parameter object from the binning model parameters
        self.params = Parameter.create(
            name='RIXS Binning Parameters', 
            type='group', 
            children=self.binning_model.params
        )
        
        # Set the parameter tree to display these parameters
        self.ui.widget_ptree.setParameters(self.params, showTop=False)

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
        self.scan_image_model = RixsScanImageTable(scan_index)
        self.ui.tableView_image.setModel(self.scan_image_model)
        header = self.ui.tableView_image.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.on_image_table_clicked()
        self.ui.tableView_image.clicked.connect(self.on_image_table_clicked)

    def on_image_table_clicked(self, index=None):
        if index is None:
            row_number = 0
        else:
            row_number = index.row()
        fname = self.scan_image_model.get_image_fname(row_number)
        if os.path.isfile(fname):
            self.current_rixs_image = RixsTiffImage(fname)
            # img = self.current_rixs_image.get_image()
            self.ui.widget_imgview.setImage(
                self.current_rixs_image.get_image(), axes={"y": 0, "x": 1}
            )


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
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")

    # Parse arguments (filter out Qt arguments)
    args, qt_args = parser.parse_known_args()

    # Create QApplication with remaining arguments
    app = QApplication([sys.argv[0]] + qt_args)

    # Create and show the GUI
    gui = RixsViewerGUI(spec_filename=args.specfile)
    gui.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
