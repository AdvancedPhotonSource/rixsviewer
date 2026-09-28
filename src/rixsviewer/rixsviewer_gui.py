# Copyright © UChicago Argonne LLC
# See LICENSE file for details
import argparse
import logging
import os
import sys
import traceback
from pathlib import Path

import numpy as np
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

from .model import RixsBinningModel, RixsSpecTable, load_settings, save_settings
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

    def __init__(self, spec_filename=None, tiff_folder=None, heartbeat_s=1.0, force_reload_s=10.0):
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
        self.force_reload_s = force_reload_s
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
        self.ui.comboBox_rxes_plottarget.currentIndexChanged.connect(
            self.on_rxes_plottarget_changed
        )
        self.ui.checkBox_show_rixsprofile.toggled.connect(self.on_show_rixsprofile_toggled)
        self.ui.comboBox_rxes_cmap.currentIndexChanged.connect(self.on_rxes_cmap_changed)
        self.ui.spinBox_force_rxes_binning_points.editingFinished.connect(
            self.on_rxes_force_nenergybins_changed
        )
        self.ui.checkBox_overwrite_rxes_binning_points.toggled.connect(
            self.on_rxes_force_nenergybins_changed
        )

        self.timer = QTimer(self)
        self.timer.setInterval(int(heartbeat_s * 1000))
        self.timer.timeout.connect(self.update_spec_record)
        self.ui.checkBox_autoupdate.checkStateChanged.connect(self.start_stop_timer)

        self.threadpool = QThreadPool()
        self._binning_active = False
        self._binning_dset = None
        self._pending_evict = None
        self._updating_params = False
        self._catching_up = False
        self._backfill_queue = []
        self._backfill_index = 0

        # Initialize the RixsBinningModel and set up parameter tree
        self.setup_parameter_tree()
        self.setup_scan_table()
        self._setup_tooltips()

    def _setup_tooltips(self):
        ui = self.ui
        # Load / file
        ui.toolButton_load_specfile.setToolTip("Browse for a SPEC data file (.spec)")
        ui.lineEdit_specfilename.setToolTip("Path to the loaded SPEC file")
        ui.toolButton_set_tifffolder.setToolTip("Browse for the folder containing TIFF detector images")
        ui.lineEdit.setToolTip("Path to the TIFF image folder")
        ui.pushButton_load_scan.setToolTip("Parse the SPEC file and populate the scan table")
        ui.checkBox_autoupdate.setToolTip(
            "Poll the SPEC file every second for new scans and process them automatically.\n"
            "Disables manual calibration."
        )
        # 2D image display
        ui.doubleSpinBox_percentile_cutoff.setToolTip(
            "Percentile used to clip the colour scale (50–100).\n"
            "Lower values increase contrast by saturating bright pixels."
        )
        ui.horizontalSlider_frame_index.setToolTip("Step through individual detector frames in the current scan")
        # Parameters / metadata
        ui.comboBox_metasource.setToolTip(
            "Source of binning parameters:\n"
            "  SpecFile — read from the scan header\n"
            "  PV       — live EPICS readback\n"
            "  USER     — manual entry in the parameter tree"
        )
        ui.pushButton_3.setToolTip("Load binning parameters from a saved file")
        ui.pushButton_4.setToolTip("Save current binning parameters to a file")
        # Process tab
        ui.checkBox_show_rawdata.setToolTip("Overlay the un-normalised raw spectrum on the plot")
        ui.checkBox_overwrite_binning_points.setToolTip("Override the automatic energy bin spacing with a fixed bin count")
        ui.spinBox_force_binning_points.setToolTip("Number of energy bins to use when the override checkbox is enabled")
        ui.comboBox_plottarget.setToolTip(
            "Signal channel to display:\n"
            "  intensity_norm — normalised RIXS intensity\n"
            "  pseudo_cps     — counts per second\n"
            "  i0 / i2        — incident / transmitted beam monitors\n"
            "  mmepin1/2      — pin diode monitors\n"
            "  A              — number of valid frames per energy bin"
        )
        ui.pushButton_process.setToolTip("Run the Rowland-circle binning pipeline on the current scan")
        ui.progressBar_process.setToolTip("Binning progress (%)")
        # RXES Map tab
        ui.comboBox_rxes_plottarget.setToolTip(
            "Array to display for the current RXES map:\n"
            "  intensity_norm — coverage-averaged intensity\n"
            "  intensity      — raw accumulated intensity\n"
            "  sample         — coverage count (frames per cell)"
        )
        ui.comboBox_rxes_cmap.setToolTip("Colormap used for the RXES map's colorbar")
        ui.checkBox_show_rixsprofile.setToolTip(
            "Show a 1D emission-energy profile at a fixed incident energy.\n"
            "Click anywhere on the map to pick the incident energy; defaults to the median."
        )
        ui.checkBox_overwrite_rxes_binning_points.setToolTip(
            "Override the automatic emission-bin spacing for the RXES map with a fixed bin count.\n"
            "Defaults to this scan's own merixE point count; unchecking falls back to native pixel spacing."
        )
        ui.spinBox_force_rxes_binning_points.setToolTip(
            "Number of emission bins for the RXES map when the override checkbox is enabled"
        )
        ui.pushButton_save.setToolTip("Export the binned spectrum to a SPEC-format file")
        # Calibration tab
        ui.comboBox_fit_target.setToolTip(
            "Parameter to optimise:\n"
            "  DeltaD    — effective pixel size (mm)\n"
            "  TiltAngle — crystal tilt angle (degrees)"
        )
        ui.comboBox_center_method.setToolTip(
            "Peak-finding algorithm for the elastic line:\n"
            "  gaussian  — most accurate, slowest\n"
            "  centroid  — balanced\n"
            "  argmax    — fastest, least accurate"
        )
        ui.pushButton_fit_pixel_size.setToolTip(
            "Run a line-search to find the optimal DeltaD or TiltAngle\n"
            "by minimising the elastic peak FWHM"
        )
        ui.progressBar_calibrate.setToolTip("Calibration progress (%)")

    def start_stop_timer(self):
        """Auto-update the scan table with new scans from the spec file"""
        if self.ui.checkBox_autoupdate.isChecked():
            self.ui.pushButton_fit_pixel_size.setDisabled(True)
            self.ui.pushButton_fit_pixel_size.setChecked(False)

            backfill = self.scan_model.get_unprocessed_scans() if self.scan_model else []
            if backfill:
                logger.info(
                    "Auto-update enabled: catching up on %d unprocessed scan(s).",
                    len(backfill),
                )
                self._catching_up = True
                self._backfill_queue = backfill
                self._backfill_index = 0
                self._advance_backfill_queue()
            else:
                logger.info("Auto-updating scan table from spec file...")
                self.timer.start()
        else:
            self.ui.pushButton_fit_pixel_size.setEnabled(True)
            logger.info("Auto-update disabled.")
            self.timer.stop()
            self._catching_up = False
            self._backfill_queue = []
            self._backfill_index = 0

    def _advance_backfill_queue(self):
        """
        Process the next scan in :attr:`_backfill_queue`, or start live polling.

        Called once to kick off catch-up processing, then again from
        :meth:`process_binning`'s completion handler after each scan finishes,
        until the queue is drained. If auto-update is unchecked mid-catch-up,
        the queue is abandoned without starting the timer.
        """
        if self._backfill_index >= len(self._backfill_queue) or not self.ui.checkBox_autoupdate.isChecked():
            caught_up = self._backfill_index > 0
            self._catching_up = False
            self._backfill_queue = []
            self._backfill_index = 0
            if self.ui.checkBox_autoupdate.isChecked():
                if caught_up:
                    self.statusBar().showMessage("Catch-up complete.", 5000)
                self.timer.start()
            return

        dset = self._backfill_queue[self._backfill_index]
        self._backfill_index += 1
        self.statusBar().showMessage(
            f"Catching up on missed scans: scan {dset.scan_index} "
            f"({self._backfill_index}/{len(self._backfill_queue)})"
        )

        if self.current_rixs_dset is not None and self.current_rixs_dset is not dset:
            self._evict_scan_data(self.current_rixs_dset)
        self._set_current_rixs_dset(dset)
        self.ui.tableView_image.setModel(dset.get_table_model())
        header = self.ui.tableView_image.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.update_image(frame_index=-1)
        self.process_binning()

    def update_meta_source(self):
        """Update the binning kwargs source based on the combo box selection"""
        meta_source = self.ui.comboBox_metasource.currentText()
        if meta_source == "PV":
            logger.info("Using PVs for binning parameters")
            kwargs = self.binning_model.get_kwargs_from_pv()
            self._put_params(kwargs)
        elif meta_source == "SpecFile" and self.current_rixs_dset is not None:
            logger.info("Using SpecFile metadata for binning parameters")
            spec_meta = self.current_rixs_dset.scan_info.get("metadata", {})
            self._put_params(spec_meta)

        if self.current_rixs_dset is not None:
            self.process_binning()

    def _evict_scan_data(self, dset):
        """
        Release a dataset's loaded TIFF stack so memory stays at ~one scan.

        The frames can be reloaded from disk on demand, so a released scan
        remains fully usable.

        Parameters
        ----------
        dset : RixsEnergyScanDataset, RixsSnapshotScanDataset, RixsRxesScanDataset, or None
            The dataset to release. ``None`` is a no-op.
        """
        if dset is None or not dset.has_loaded_frames() or dset.scan_info is None:
            return
        if self._binning_active and dset is self._binning_dset:
            # a background worker is still reading/writing this dataset's
            # buffer (process_binning -> bin_data_wrap -> read_tiff_data);
            # freeing it now would race the worker thread. Defer eviction
            # until process_binning's on_finished runs.
            self._pending_evict = dset
            return
        # release_data() frees the preallocated buffer, not just the view
        dset.release_data()

    def update_spec_record(self):
        """
        Check for updates in the spec file and process them.

        This method is called periodically by the timer when auto-update is enabled.
        """
        if self.scan_model is not None:
            has_updates = self.scan_model.process_spec_file()
            new_dset = self.scan_model.last_scan_dset
            if new_dset is not self.current_rixs_dset:
                # auto-update never fires on_selection_changed; evict here or
                # every scan's stack stays resident for the whole session (OOM)
                self._evict_scan_data(self.current_rixs_dset)
                self._set_current_rixs_dset(new_dset)

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

        # Disable "PV" and "Auto Update" if EPICS is not reachable
        if not self.binning_model.check_pv_connection():
            logger.info("EPICS PVs not reachable — disabling PV metadata source and auto-update")
            combo = self.ui.comboBox_metasource
            pv_item = combo.model().item(1)  # index 1 = "PV"
            pv_item.setEnabled(False)
            pv_item.setToolTip("EPICS PVs not available")
            self.ui.checkBox_autoupdate.setChecked(False)
            self.ui.checkBox_autoupdate.setEnabled(False)
            self.ui.checkBox_autoupdate.setToolTip("Auto-update requires EPICS PV access (not available)")

    def on_parameter_changed(self, param, changes):
        """Handle parameter tree changes and sync with binning model"""
        meta_source = self.ui.comboBox_metasource.currentText()
        if meta_source != "USER" and not self._updating_params:
            QMessageBox.warning(
                self,
                "Parameter edit blocked",
                f"Parameters are read-only in '{meta_source}' mode.\n"
                "Switch the metadata source to 'USER' to edit them.",
            )
            return
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
        try:
            self.params.child(name).setValue(value)
        except KeyError:
            pass

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
        self._updating_params = True
        for name, value in kwargs.items():
            self._put_param(name, value)
        self._updating_params = False

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
        if not self.current_rixs_dset.supports_calibration():
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
            self.current_rixs_dset.save_to_file(fname, force=True)
        except Exception as e:
            QMessageBox.critical(self, "Save failed", f"Could not save file:\n{e}")
            return

        self.statusBar().showMessage(f"Results saved to: {fname}", 5000)

    def _resolve_nenergybins_override(self):
        """Return the ``{NEnergyBins, force_NEnergyBins}`` binning kwargs
        from whichever "Force NEnergyBins" checkbox/spinbox pair applies to
        the current scan -- the RXES Map tab's pair for scans that produce a
        2D map, the Process tab's pair for everything else. The two scan
        kinds need very different default bin counts (a scan's own merixE
        point count vs. an arbitrary 1D default), so they get separate
        controls rather than sharing one.
        """
        if self.current_rixs_dset.supports_rxes_map():
            checkbox = self.ui.checkBox_overwrite_rxes_binning_points
            spinbox = self.ui.spinBox_force_rxes_binning_points
        else:
            checkbox = self.ui.checkBox_overwrite_binning_points
            spinbox = self.ui.spinBox_force_binning_points

        if checkbox.isChecked():
            return {"NEnergyBins": spinbox.value(), "force_NEnergyBins": True}
        return {"force_NEnergyBins": False}

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
        plot_target = self.ui.comboBox_plottarget.currentText()

        binning_kwargs = self._get_binning_kwargs(meta_source)
        binning_kwargs.update(self._resolve_nenergybins_override())

        if len(self.current_rixs_dset.unloaded_filenames) == 0:
            if self.ui.checkBox_autoupdate.isChecked():
                if not self.current_rixs_dset.has_loaded_frames():
                    return  # nothing loaded yet, nothing to re-bin

        self._binning_active = True
        self._binning_dset = self.current_rixs_dset
        self.ui.pushButton_process.setEnabled(False)

        def worker_fn():
            return self._binning_dset.bin_data_wrap(
                metadata_source=meta_source,
                center_method=center_method,
                progress_callback=worker.signals.progress.emit,
                **binning_kwargs,
            )

        def on_result(result):
            self._route_binning_result(result, show_rawdata, plot_target)

        def on_error(err_str):
            if err_str.startswith("No frames") or "no scandata rows" in err_str:
                self.statusBar().showMessage(f"Warning: {err_str}", 5000)
            else:
                logger.error(f"Processing binning failed: {err_str}")

        def on_finished():
            self._binning_active = False
            self._binning_dset = None
            self.ui.pushButton_process.setEnabled(True)
            if self._pending_evict is not None:
                pending = self._pending_evict
                self._pending_evict = None
                self._evict_scan_data(pending)
            if (
                self.ui.checkBox_autoupdate.isChecked()
                and self.current_rixs_dset is not None
            ):
                self.update_image(frame_index=-1)
                if (
                    self.current_rixs_dset.is_complete()
                    and self.current_rixs_dset.bin_result is not None
                ):
                    self.current_rixs_dset.save_to_file(self.save_filename)
                if self.current_rixs_dset.unloaded_filenames:
                    self.process_binning()
                    return
            if self._catching_up:
                self._advance_backfill_queue()

        worker = Worker(worker_fn)
        self.binning_worker = worker  # Keep reference to prevent GC of signals

        if hasattr(self.ui, "progressBar_process"):
            self.ui.progressBar_process.setValue(0)
            worker.signals.progress.connect(self.ui.progressBar_process.setValue)

        worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error)
        worker.signals.finished.connect(on_finished)
        self.threadpool.start(worker)

    def on_rxes_plottarget_changed(self):
        """Replot the RXES map from its already-computed cached result.

        intensity/intensity_norm/sample are all produced by the same
        ``bin_data_wrap`` call, so switching between them is a free replot
        -- no need to re-run the reduction pipeline.
        """
        dset = self.current_rixs_dset
        bin_result = getattr(dset, "bin_result", None) if dset is not None else None
        if bin_result is None or bin_result.get("kind") != "rxes_map":
            return
        self.view.plot_rxes_map(
            bin_result, plot_target=self.ui.comboBox_rxes_plottarget.currentText()
        )

    def on_show_rixsprofile_toggled(self, checked):
        self.view.set_rxes_profile_visible(checked)

    def on_rxes_cmap_changed(self):
        self.view.set_rxes_colormap(self.ui.comboBox_rxes_cmap.currentText())

    def on_rxes_force_nenergybins_changed(self, *_):
        """Re-bin immediately on Enter/focus-loss in the spinbox, or on
        toggling the checkbox -- NEnergyBins is a calibration key, so
        bin_data_wrap() replays the whole scan under the new bin count
        rather than requiring a separate trip to the Process tab's Apply.
        """
        if self.current_rixs_dset is not None and self.current_rixs_dset.supports_rxes_map():
            self.process_binning()

    def _route_binning_result(self, result, show_rawdata, plot_target):
        """
        Route a ``bin_data_wrap()`` result to the right presentation.

        A 2D RXES map (``result["kind"] == "rxes_map"``) is rendered on the
        "RXES Map" tab; *plot_target* (from the 1D-plot combo box) doesn't
        apply there, so ``comboBox_rxes_plottarget`` is consulted instead.
        A 1D spectrum result is plotted as before.
        """
        if result.get("kind") == "rxes_map":
            self.view.plot_rxes_map(
                result, plot_target=self.ui.comboBox_rxes_plottarget.currentText()
            )
            self.ui.tabWidget.setCurrentWidget(self.ui.tab_rxesmap)
            filled = int(np.sum(result["sample"] > 0))
            total = result["sample"].size
            self.statusBar().showMessage(
                f"RXES map updated: {filled}/{total} cells filled", 3000
            )
            return

        self.view.plot_binned_data(
            result, show_rawdata, plot_target=plot_target, hdl_target="plot"
        )
        if result.get("warning"):
            self.statusBar().showMessage(f"Warning: {result['warning']}", 5000)

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
            "All Files (*);;SPEC Files (*.spm3)",
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

        p = Path(self.spec_filename)
        self.save_filename = p.with_name(f"{p.stem}_bindata_rixsviewer.spec")
        logger.info(f"saving binned results to {self.save_filename}")

        logger.info(f"Loading spec and tiff: {self.spec_filename}, {self.tiff_folder}")
        try:
            scan_model = RixsSpecTable(
                self.spec_filename, self.tiff_folder, self.save_filename,
                force_reload_s=self.force_reload_s,
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

        save_settings(self.spec_filename, self.tiff_folder)

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

    def _set_current_rixs_dset(self, dset):
        """Set ``current_rixs_dset`` and keep the RXES Map tab in sync with it.

        Centralizes the tab sync so every place that changes the current
        dataset (manual row click, auto-update, backfill catch-up) gets it
        for free rather than needing to remember to call it separately.
        """
        self.current_rixs_dset = dset
        self._sync_rxes_map_tab(dset)

    def _sync_rxes_map_tab(self, dset):
        """Enable the RXES Map tab only for scans that produce a 2D map.

        Otherwise clear any map left over from a previously-selected RXES
        scan and, if that tab was the active one, switch back to Process --
        without this a stale RXES map kept showing after selecting a plain
        EnergyScan/SnapshotScan.
        """
        is_rxes = dset is not None and dset.supports_rxes_map()
        idx = self.ui.tabWidget.indexOf(self.ui.tab_rxesmap)
        # Capture this before disabling: Qt auto-switches away from a tab
        # that's current the moment it's disabled, so checking afterwards
        # would always see some other (arbitrary) tab as current.
        was_current = self.ui.tabWidget.currentWidget() is self.ui.tab_rxesmap
        self.ui.tabWidget.setTabEnabled(idx, is_rxes)
        if is_rxes:
            # Default the RXES-specific bin-count override to this scan's
            # own merixE point count -- a sensible starting point distinct
            # per scan, without clobbering a value the user already tweaked
            # for this same scan (this only runs on an actual scan switch).
            self.ui.spinBox_force_rxes_binning_points.setValue(dset.scan_info["emission_points"])
        else:
            self.view.clear_rxes_map()
            if was_current:
                self.ui.tabWidget.setCurrentWidget(self.ui.tab_2)

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

        if self.current_rixs_dset is not None and self.current_rixs_dset is not dset:
            self._evict_scan_data(self.current_rixs_dset)

        self._set_current_rixs_dset(dset)
        self.ui.tableView_image.setModel(self.current_rixs_dset.get_table_model())
        header = self.ui.tableView_image.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        self.update_image(frame_index=-2)
        if not self.ui.checkBox_autoupdate.isChecked():
            self.process_binning()

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
        description="RixsViewer - A tool for visualizing and analyzing RIXS (Resonance Inelastic X-ray Scattering) data"
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
        "--heartbeat",
        type=float,
        default=1.0,
        metavar="SEC",
        help="Auto-update poll interval in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--force-reload",
        type=float,
        default=10.0,
        metavar="SEC",
        help="Force SPEC re-read after this many seconds regardless of mtime,"
             " to bypass NFS attribute caching (default: 10.0)",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    # Parse arguments (filter out Qt arguments)
    args, qt_args = parser.parse_known_args()
    unrecognized_opts = [a for a in qt_args if a.startswith("-")]
    if unrecognized_opts:
        parser.error(f"unrecognized arguments: {' '.join(unrecognized_opts)}")

    # Fall back to the last-used spec file / TIFF folder for any field not
    # given on the command line.
    saved = load_settings()
    if args.specfile is None:
        args.specfile = saved.get("spec_filename")
    if args.tiff_folder is None:
        args.tiff_folder = saved.get("tiff_folder")

    # Suppress a harmless pyqtgraph/Qt6 warning about UniqueConnection + lambdas:
    # "qt.core.qobject.connect: QObject::connect(QStyleHints, QStyleHints):
    #  unique connections require a pointer to member function of a QObject subclass"
    # This must be set before QApplication is created.
    os.environ.setdefault("QT_LOGGING_RULES", "qt.core.qobject.connect=false")

    # Create QApplication with remaining arguments
    app = QApplication([sys.argv[0]] + qt_args)

    if sys.platform == "darwin":
        pass                      # keep native macOS style
    else:
        app.setStyle("Fusion")    # Windows / Linux

    icon_path = Path(__file__).parent / "assets" / "icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Configure pyqtgraph after QApplication is created to avoid Qt
    # "unique connections require a pointer to member function" warnings
    pg.setConfigOption("background", "w")
    pg.setConfigOption("foreground", "k")
    pg.setConfigOption("antialias", True)

    # Create and show the GUI
    gui = RixsViewerGUI(
        spec_filename=args.specfile,
        tiff_folder=args.tiff_folder,
        heartbeat_s=args.heartbeat,
        force_reload_s=args.force_reload,
    )
    gui.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
