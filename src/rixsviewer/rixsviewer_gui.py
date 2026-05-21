import argparse
import logging
import os
import sys
import traceback
from pathlib import Path

import pyqtgraph as pg
from pyqtgraph.parametertree import Parameter
from PySide6.QtCore import QTimer, QRunnable, Slot, QThreadPool, QObject, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHeaderView,
    QMainWindow,
    QMessageBox,
)

from .model import RixsBinningModel, RixsSpecTable
from .view import RixsView
from .view.ui import Ui_MainWindow
from . import __version__

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


logger = logging.getLogger(__name__)


class WorkerSignals(QObject):
    finished = Signal()
    error = Signal(str)
    result = Signal(object)
    progress = Signal(int)


class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:
            traceback.print_exc()
            self.signals.error.emit(str(e))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()


class RixsViewerGUI(QMainWindow):
    """
    Main GUI class for the RIXS Viewer application.

    This class manages the main window, connects UI elements to actions,
    and coordinates between the model and view.
    """

    def __init__(self, spec_filename=None, tiff_folder=None):
        """
        Initialize the RixsViewerGUI.

        Parameters
        ----------
        spec_filename : str, optional
            Path to the initial SPEC file to load.
        tiff_folder : str, optional
            Path to the folder containing TIFF images.
        """
        super().__init__()

        # Set up the UI
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle(f"RixsViewer v{__version__}")

        self.scan_model = None
        self.current_rixs_dset = None

        self.tiff_folder = tiff_folder
        self.spec_filename = spec_filename
        self.save_filename = None

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
        self.view = RixsView(self.ui)
        self.ui.pushButton_process.clicked.connect(self.process_binning)
        self.ui.pushButton_save.clicked.connect(self.save_bin_results)
        self.ui.pushButton_fit_pixel_size.clicked.connect(self.calibrate_parameters)
        self.ui.comboBox_metasource.currentIndexChanged.connect(self.update_meta_source)
        self.ui.horizontalSlider_frame_index.valueChanged.connect(self.update_image)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_spec_record)
        self.ui.checkBox_autoupdate.checkStateChanged.connect(self.start_stop_timer)

        self.threadpool = QThreadPool()
        self._binning_active = False

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
        """
        Check for updates in the spec file and process them.

        This method is called periodically by the timer when auto-update is enabled.
        """
        if self.scan_model is not None:
            has_updates = self.scan_model.process_spec_file()
            self.current_rixs_dset = self.scan_model.last_scan_dset

            if has_updates:
                self.process_binning()
                self.ui.tableView_image.setModel(
                    self.current_rixs_dset.get_table_model()
                )
                header = self.ui.tableView_image.horizontalHeader()
                header.setSectionResizeMode(QHeaderView.Stretch)

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
        """
        Update one parameter in the model and reflect the new value in the UI.

        This is the only place in the controller that should write a single
        named value to both the model and the parameter-tree widget.

        Parameters
        ----------
        name : str
            The name of the parameter to update.
        value : any
            The new value for the parameter.
        """
        self.binning_model.put_single_parameter(name, value)
        param = self.params.child(name)
        if param is not None:
            param.setValue(value)

    def _put_params(self, kwargs):
        """
        Bulk version of `_put_param` to update multiple parameters.

        Updates all key/value pairs in `kwargs` in both the model and the
        parameter-tree widget.

        Parameters
        ----------
        kwargs : dict
            A dictionary of parameter names and their new values.
        """
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
        """
        Fit pixel size and optical parameters using a line search.

        This method retrieves parameters, performs a line search to optimize them,
        and plots the results. It requires the current scan to be an EnergyScan.
        """
        if self.current_rixs_dset is None:
            return
        if self.current_rixs_dset.scan_info["scan_type"] != "EnergyScan":
            QMessageBox.warning(
                self,
                "Warning",
                "Effective pixel size can only be fitted for EnergyScan",
            )
            return

        self.ui.pushButton_fit_pixel_size.setEnabled(False)

        meta_source = self.ui.comboBox_metasource.currentText()
        center_method = self.ui.comboBox_center_method.currentText()
        opt_target = self.ui.comboBox_fit_target.currentText()

        binning_kwargs = self._get_binning_kwargs(meta_source)

        def worker_fn():
            return self.current_rixs_dset.linesearch_to_optimize_parameter(
                target=opt_target,
                metadata_source=meta_source,
                center_method=center_method,
                progress_callback=worker.signals.progress.emit,
                **binning_kwargs,
            )

        def on_error(err_str):
            if err_str.startswith("No frames"):
                self.statusBar().showMessage(f"Warning: {err_str}", 5000)
            else:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Linesearch to optimize {opt_target} failed:\n{err_str}",
                )

        def on_result(ls):
            # Plot the sweep curve with all three reference markers
            self.view.plot_linesearch(ls)

            # Overlay all three spectra on calib_hdl (left panel)
            self.view.plot_calib_overlay(ls)

            unit = "mm" if opt_target == "DeltaD" else "deg"
            if ls.get("lns_value"):
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
                current_meta_source = self.ui.comboBox_metasource.currentText()
                if reply == QMessageBox.Yes:
                    if current_meta_source != "USER":
                        QMessageBox.critical(
                            self,
                            "Error",
                            f"Overriding metadata entry [{opt_target}] only supported in `USER` mode.",
                        )
                        return
                    self._put_param(opt_target, ls["lns_value"])
                if opt_target == "TiltAngle":
                    self.update_image()

        def on_finished():
            if not self.ui.checkBox_autoupdate.isChecked():
                self.ui.pushButton_fit_pixel_size.setEnabled(True)

        worker = Worker(worker_fn)
        self.calibrate_worker = worker  # Keep reference to prevent GC of signals

        if hasattr(self.ui, "progressBar_calibrate"):
            self.ui.progressBar_calibrate.setValue(0)
            worker.signals.progress.connect(self.ui.progressBar_calibrate.setValue)

        worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error)
        worker.signals.finished.connect(on_finished)
        self.threadpool.start(worker)

    def save_bin_results(self):
        """
        Save the binned results to a user-chosen file.
        """
        if self.current_rixs_dset is None or self.current_rixs_dset.bin_result is None:
            return

        default = str(self.save_filename) if self.save_filename else ""
        dialog = QFileDialog(
            self, "Save binned results", default, "SPEC files (*.spec);;All files (*)"
        )
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setOption(QFileDialog.Option.DontConfirmOverwrite, True)
        if not dialog.exec():
            return
        fname = dialog.selectedFiles()[0]

        try:
            self.current_rixs_dset.save_to_file(fname)
        except Exception as e:
            QMessageBox.critical(self, "Save failed", f"Could not save file:\n{e}")
            return

        self.save_filename = Path(fname)
        self.statusBar().showMessage(f"Results saved to: {fname}", 5000)

    def process_binning(self):
        """
        Process the binning of the current dataset and display the result.

        This method reads binning parameters, applies the binning logic,
        and plots the resulting data.
        """
        if self.current_rixs_dset is None:
            return

        if self._binning_active:
            return

        show_rawdata = self.ui.checkBox_show_rawdata.isChecked()
        meta_source = self.ui.comboBox_metasource.currentText()
        center_method = self.ui.comboBox_center_method.currentText()
        bin_pixel = self.ui.spinBox_binpixel.value()
        plot_target = self.ui.comboBox_plottarget.currentText()

        binning_kwargs = self._get_binning_kwargs(meta_source)

        if len(self.current_rixs_dset.unloaded_filenames) == 0:
            if self.ui.checkBox_autoupdate.isChecked():
                return

        self._binning_active = True
        self.ui.pushButton_process.setEnabled(False)

        def worker_fn():
            return self.current_rixs_dset.bin_data_wrap(
                metadata_source=meta_source,
                center_method=center_method,
                bin_pixel=bin_pixel,
                progress_callback=worker.signals.progress.emit,
                **binning_kwargs,
            )

        def on_result(result):
            self.view.plot_binned_data(
                result, show_rawdata, plot_target=plot_target, hdl_target="plot"
            )
            if result.get("warning"):
                self.statusBar().showMessage(f"Warning: {result['warning']}", 5000)

        def on_error(err_str):
            if err_str.startswith("No frames"):
                self.statusBar().showMessage(f"Warning: {err_str}", 5000)
            else:
                QMessageBox.critical(
                    self, "Error", f"Processing binning failed:\n{err_str}"
                )

        def on_finished():
            self._binning_active = False
            self.ui.pushButton_process.setEnabled(True)
            if (
                self.ui.checkBox_autoupdate.isChecked()
                and self.current_rixs_dset is not None
            ):
                self.update_image(frame_index=-1)
                si = self.current_rixs_dset.scan_info
                if (
                    si
                    and si["tiff_points"] > 0
                    and si["tiff_points"] == si["spec_points"]
                    and self.current_rixs_dset.bin_result is not None
                ):
                    self.current_rixs_dset.save_to_file(self.save_filename)

        worker = Worker(worker_fn)
        self.binning_worker = worker  # Keep reference to prevent GC of signals

        if hasattr(self.ui, "progressBar_process"):
            self.ui.progressBar_process.setValue(0)
            worker.signals.progress.connect(self.ui.progressBar_process.setValue)

        worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error)
        worker.signals.finished.connect(on_finished)
        self.threadpool.start(worker)

    # plot_binned_data is handled by RixsView

    def on_load_specfile_clicked(self):
        """Handle the load spec file button click"""
        # Open file dialog to select a spec file
        start_folder = (
            "./" if self.spec_filename is None else str(Path(self.spec_filename).parent)
        )
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open SPEC File",
            start_folder,
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
        """
        Set up the scan table with the RixsSpecTable model.
        """
        if self.tiff_folder is None or self.spec_filename is None:
            return
        if not Path(self.tiff_folder).is_dir:
            logger.error(f"Check the tiff folder: {self.tiff_folder}")
            return
        if not Path(self.spec_filename).is_file:
            logger.error(f"Check the spec file: {self.spec_filename}")
            return

        logger.info(f"Loading spec and tiff: {self.spec_filename}, {self.tiff_folder}")
        try:
            scan_model = RixsSpecTable(
                self.spec_filename, self.tiff_folder, self.save_filename
            )
        except Exception as e:
            traceback.print_exc()
            logger.error(f"Error loading SPEC file: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load SPEC file:\n{e}",
            )
            return

        p = Path(self.spec_filename)
        self.save_filename = p.with_name(f"{p.stem}_bindata_rixsviewer.spec")
        logger.info(f"saveing bined results to {self.save_filename}")

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
        row = [index.row() for index in selected_indexes][0]
        if self.ui.checkBox_autoupdate.isChecked():
            row = (
                self.scan_model.rowCount() - 1
            )  # choose the last row in auto-update mode

        dset = self.scan_model.get_selected_dataset(row)
        if dset is None:
            return

        self.current_rixs_dset = dset
        self.ui.tableView_image.setModel(self.current_rixs_dset.get_table_model())
        header = self.ui.tableView_image.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.update_image(frame_index=-2)

    def update_image(self, frame_index=-2):
        """
        Update the main image view with a specific frame.

        Parameters
        ----------
        frame_index : int, optional
            The index of the frame to display. Default is -2, which plots
            the middle frame. Use -1 for the last frame.
        """
        # frame_index = -2 will plot the middle frame
        # frame_index = -1 will plot the last frame
        if self.current_rixs_dset is None:
            return
        percentile_cutoff = self.ui.doubleSpinBox_percentile_cutoff.value()

        binning_kwargs = self.binning_model.get_kwargs()

        frame_info = self.current_rixs_dset.get_data_for_display(
            frame_index=frame_index,
            percentile_cutoff=percentile_cutoff,
            **binning_kwargs,
        )

        # Scan may be empty (no TIFF frames or no scandata rows yet)
        if frame_info is None:
            logger.debug(
                "update_image: no data available for scan %s yet.",
                self.current_rixs_dset.scan_index,
            )
            return

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
        """
        Handle the close event.

        Parameters
        ----------
        event : PySide6.QtGui.QCloseEvent
            The close event object.
        """
        reply = QMessageBox.question(
            self,
            "Confirm Exit",
            "Are you sure you want to close RIXSviewer?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.timer.stop()
            super().closeEvent(event)
        else:
            event.ignore()


def main():
    """Main entry point for the application"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="RixsViewer - A tool for visualization and modeling of RIXS (Resonance Inelastic X-ray Scattering) data"
    )
    parser.add_argument(
        "--specfile",
        nargs="?",
        help="Path to the SPEC file to load (default: %(default)s)",
    )
    parser.add_argument(
        "--tiff-folder",
        help="Path to the TIFF folder (default: %(default)s)",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    # Parse arguments (filter out Qt arguments)
    args, qt_args = parser.parse_known_args()

    # Suppress a harmless pyqtgraph/Qt6 warning about UniqueConnection + lambdas:
    # "qt.core.qobject.connect: QObject::connect(QStyleHints, QStyleHints):
    #  unique connections require a pointer to member function of a QObject subclass"
    # This must be set before QApplication is created.
    os.environ.setdefault("QT_LOGGING_RULES", "qt.core.qobject.connect=false")

    # Create QApplication with remaining arguments
    app = QApplication([sys.argv[0]] + qt_args)

    icon_path = Path(__file__).parent / "assets" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

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
