import argparse
import logging
import os
import sys
import traceback
from pathlib import Path

import pyqtgraph as pg
from pyqtgraph.parametertree import Parameter
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QFileDialog, QHeaderView, QMainWindow, QMessageBox

from .model import RixsBinningModel, RixsSpecTable
from .view import RixsView
from .view.ui import Ui_MainWindow

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


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
        self.ui.toolButton_set_tifffolder.clicked.connect(self.on_set_tifffolder_clicked)
        self.ui.pushButton_load_scan.clicked.connect(self.setup_scan_table)
        self.view = RixsView(self.ui)
        self.ui.pushButton_process.clicked.connect(self.process_binning)
        self.ui.pushButton_fit_pixel_size.clicked.connect(self.calibrate_parameters)
        self.ui.comboBox_metasource.currentIndexChanged.connect(self.update_meta_source)
        self.ui.horizontalSlider_frame_index.valueChanged.connect(self.update_image)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_spec_record)
        self.ui.checkBox_autoupdate.checkStateChanged.connect(self.start_stop_timer)

        # Initialize the RixsBinningModel and set up parameter tree
        self.setup_parameter_tree()
        self.setup_scan_table()

    def start_stop_timer(self):
        """Auto-update the scan table with new scans from the spec file"""
        if self.ui.checkBox_autoupdate.isChecked():
            self.ui.pushButton_fit_pixel_size.setDisabled(True)
            self.ui.pushButton_fit_pixel_size.setChecked(False)
            logger.info("Auto-updating scan table from spec file...")
            self.timer.start()
        else:
            self.ui.pushButton_fit_pixel_size.setEnabled(True)
            logger.info("Auto-update disabled.")
            self.timer.stop()

    def update_meta_source(self):
        """Update the binning kwargs source based on the combo box selection"""
        meta_source = self.ui.comboBox_metasource.currentText()
        if meta_source == "PV":
            logger.info("Using PVs for binning parameters")
            kwargs = self.binning_model.get_kwargs_from_pv()
            self._put_params(kwargs)  # reflect PV values in the param-tree widget

        return

    def update_spec_record(self):
        if self.scan_model is not None:
            self.scan_model.process_spec_file()
            self.process_binning()
            self.current_rixs_dset = self.scan_model.last_scan_dset

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
        meta_source = self.ui.comboBox_metasource.currentText()
        # Parameters are only editable when meta source is set to 'USER'
        if meta_source == "USER":
            self.binning_model.update_from_parameter(param, changes)

    # ------------------------------------------------------------------
    # Controller helpers: keep model and param-tree widget in sync
    # ------------------------------------------------------------------

    def _put_param(self, name, value):
        """Update one parameter in the model and reflect the new value in the
        parameter-tree widget.  This is the only place in the controller that
        should write a single named value to both M and V."""
        self.binning_model.put_single_parameter(name, value)
        param = self.params.child(name)
        if param is not None:
            param.setValue(value)

    def _put_params(self, kwargs):
        """Bulk version of :meth:`_put_param` — update all key/value pairs in
        *kwargs* in both the model and the parameter-tree widget."""
        for name, value in kwargs.items():
            self._put_param(name, value)

    def _get_binning_kwargs(self, meta_source):
        """
        Resolve the binning keyword arguments based on the metadata source.

        Parameters
        ----------
        meta_source : str
            One of 'SpecFile', 'PV', or 'USER'.

        Returns
        -------
        dict or None
            A dictionary of binning parameters, or None if the source is 'SpecFile'.
        """
        if meta_source == "PV":
            return self.binning_model.get_kwargs_from_pv()
        elif meta_source in ("USER", "SpecFile"):
            return self.binning_model.get_kwargs()

    def calibrate_parameters(self):
        if self.current_rixs_dset is None:
            return
        if self.current_rixs_dset.scan_info["scan_type"] != "EnergyScan":
            QMessageBox.warning(self, "Warning", "Effective pixel size can only be fitted for EnergyScan")
            return

        meta_source = self.ui.comboBox_metasource.currentText()
        center_method = self.ui.comboBox_center_method.currentText()
        opt_target = self.ui.comboBox_fit_target.currentText()

        binning_kwargs = self._get_binning_kwargs(meta_source)

        try:
            ls = self.current_rixs_dset.linesearch_to_optimize_parameter(
                target=opt_target,
                metadata_source=meta_source,
                center_method=center_method,
                **binning_kwargs,
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Linesearch to optimize {opt_target} failed:\n{e}")
            traceback.print_exc()
            return

        # Plot the sweep curve with all three reference markers
        self.view.plot_linesearch(ls)

        # Overlay all three spectra on calib_hdl (left panel)
        self.view.plot_calib_overlay(ls)

        unit = "mm" if opt_target == "DeltaD" else "deg"
        if ls["lns_value"]:
            reply = QMessageBox.question(
                self,
                f"Update {opt_target} Parameter",
                (
                    f"original  {opt_target}: {ls['org_value']:.6f} {unit}\n"
                    f"optimized {opt_target}: {ls['lns_value']:.6f} {unit}\n\n"
                    "Apply the line-search best value?"
                ),
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self._put_param(opt_target, ls["lns_value"])

    def process_binning(self):
        if self.current_rixs_dset is None:
            return

        show_rawdata = self.ui.checkBox_show_rawdata.isChecked()
        meta_source = self.ui.comboBox_metasource.currentText()
        center_method = self.ui.comboBox_center_method.currentText()
        bin_pixel = self.ui.spinBox_binpixel.value()

        binning_kwargs = self._get_binning_kwargs(meta_source)

        if len(self.current_rixs_dset.unloaded_filenames) == 0:
            if self.ui.checkBox_autoupdate.isChecked():
                return

        result = self.current_rixs_dset.bin_data_wrap(
            metadata_source=meta_source,
            center_method=center_method,
            bin_pixel=bin_pixel,
            **binning_kwargs,
        )
        self.view.plot_binned_data(result, show_rawdata, hdl_target="plot")

    # plot_binned_data is handled by RixsView

    def on_load_specfile_clicked(self):
        """Handle the load spec file button click"""
        # Open file dialog to select a spec file
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open SPEC File",
            str(Path(self.spec_filename).parent),
            "SPEC Files (*.spm3);;All Files (*)",
        )

        # If a file was selected, update the line edit and reload the scan table
        if file_path:
            self.spec_filename = file_path
            self.ui.lineEdit_specfilename.setText(file_path)

    def on_set_tifffolder_clicked(self):
        """Handle the set TIFF folder button click"""
        # Open directory dialog to select a folder
        folder_path = QFileDialog.getExistingDirectory(
            self, "Select TIFF Folder", self.tiff_folder, QFileDialog.ShowDirsOnly
        )

        # If a folder was selected, update the line edit and store the path
        if folder_path:
            self.tiff_folder = folder_path
            self.ui.lineEdit.setText(folder_path)

    def setup_scan_table(self):
        """Set up the scan table with the RixsScanListTable model"""
        if not Path(self.tiff_folder).is_dir:
            logger.error(f"Check the tiff folder: {self.tiff_folder}")
            return
        if not Path(self.spec_filename).is_file:
            logger.error(f"Check the spec file: {self.spec_filename}")
            return

        logger.info(f"Loading spec and tiff: {self.spec_filename}, {self.tiff_folder}")
        try:
            scan_model = RixsSpecTable(self.spec_filename, self.tiff_folder)
        except Exception as e:
            traceback.print_exc()
            logger.error(f"Error loading SPEC file: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load SPEC file:\n{e}",
            )
            return

        # Connect the model to the tableView_scan
        self.ui.tableView_scan.setModel(scan_model)

        # Configure column stretching to use all available space
        header = self.ui.tableView_scan.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)

        # Connect click signal to handler
        # self.ui.tableView_scan.clicked.connect(self.on_scan_table_clicked)
        self.ui.tableView_scan.selectionModel().selectionChanged.connect(self.on_selection_changed)
        self.scan_model = scan_model
        return

    def on_selection_changed(self, selected, deselected):
        """
        Called whenever the table's selection changes.
        'selected' and 'deselected' are QItemSelection objects.
        """
        selected_indexes = self.ui.tableView_scan.selectionModel().selectedIndexes()
        row = [index.row() for index in selected_indexes][0]
        if self.ui.checkBox_autoupdate.isChecked():
            row = self.scan_model.rowCount() - 1  # choose the last row in auto-update mode

        dset = self.scan_model.get_selected_dataset(row)
        if dset is None:
            return

        self.current_rixs_dset = dset
        self.ui.tableView_image.setModel(self.current_rixs_dset.get_table_model())
        header = self.ui.tableView_image.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.update_image(frame_index=-1)

    def update_image(self, frame_index=-1):
        # frame_index = -1 will plot the middle frame
        if self.current_rixs_dset is None:
            return
        percentile_cutoff = self.ui.doubleSpinBox_percentile_cutoff.value()

        binning_kwargs = self.binning_model.get_kwargs()

        frame_info = self.current_rixs_dset.get_data_for_display(
            frame_index=frame_index,
            percentile_cutoff=percentile_cutoff,
            **binning_kwargs,
        )
        self.view.update_image(
            frame_info["data"],
            frame_info["levels"],
            frame_info["num_frames"],
            frame_info["frame_metadata"],
            frame_info["scan_index"],
            frame_info["frame_index"],
        )

        # Update slider range and position without re-triggering valueChanged
        slider = self.ui.horizontalSlider_frame_index
        slider.blockSignals(True)
        slider.setMaximum(frame_info["num_frames"] - 1)
        slider.setValue(frame_info["frame_index"])
        slider.blockSignals(False)

        meta_source = self.ui.comboBox_metasource.currentText()
        if meta_source == "SpecFile":
            self._put_params(frame_info["frame_metadata"])

    def closeEvent(self, event):
        self.timer.stop()
        return super().closeEvent(event)


def main():
    """Main entry point for the application"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="RixsViewer - A tool for visualization and modeling of RIXS (Resonance Inelastic X-ray Scattering) data"
    )
    parser.add_argument(
        "specfile",
        nargs="?",
        default="/home/beams/RIXS/Data/2026-1/slot4_rixsviewer/4March2026",
        help="Path to the SPEC file to load (default: %(default)s)",
    )
    parser.add_argument(
        "--tiff-folder",
        default="/net/s27data/export/sector27/lambda/2026-1/slot4/cray_clean",
        help="Path to the TIFF folder (default: %(default)s)",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")

    # Parse arguments (filter out Qt arguments)
    args, qt_args = parser.parse_known_args()

    # Suppress a harmless pyqtgraph/Qt6 warning about UniqueConnection + lambdas:
    # "qt.core.qobject.connect: QObject::connect(QStyleHints, QStyleHints):
    #  unique connections require a pointer to member function of a QObject subclass"
    # This must be set before QApplication is created.
    os.environ.setdefault("QT_LOGGING_RULES", "qt.core.qobject.connect=false")

    # Create QApplication with remaining arguments
    app = QApplication([sys.argv[0]] + qt_args)

    # Configure pyqtgraph after QApplication is created to avoid Qt
    # "unique connections require a pointer to member function" warnings
    pg.setConfigOption("background", "w")
    pg.setConfigOption("foreground", "k")

    # Create and show the GUI
    gui = RixsViewerGUI(spec_filename=args.specfile, tiff_folder=args.tiff_folder)
    gui.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
