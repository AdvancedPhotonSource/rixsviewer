import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QMessageBox


class RixsView:
    """View layer for RixsViewer (MVC).

    Owns all pyqtgraph plot handles and is responsible for rendering data onto
    the widgets that were created by the generated UI.  It holds a reference to
    the ``ui`` object but never modifies application state directly; instead it
    returns values (e.g. the fitted DeltaD) and lets the controller (GUI class)
    decide what to do with them.
    """

    def __init__(self, ui):
        self.ui = ui
        self._img_plot = None  # kept so the ROI can be added to it
        self._roi_rect = None  # created lazily in update_image
        self._roi_parameters = None
        self.setup_image_handler()
        self.init_plot_hdl()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def setup_image_handler(self):
        plot = self.ui.widget_img.addPlot(row=0, col=0)
        plot.setLabel("bottom", "Energy bin")
        plot.setLabel("left", "Position (pixel)")
        # Optional: grid and aspect ratio
        # plot.showGrid(x=True, y=True)
        plot.getViewBox().setAspectLocked(False)
        self._img_plot = plot

        # --- Add the ImageItem ---
        self.img2d_hdl = pg.ImageItem(axisOrder="row-major")
        plot.addItem(self.img2d_hdl)

        # Optional: colorbar
        hist = pg.HistogramLUTItem()
        hist.setImageItem(self.img2d_hdl)
        self.ui.widget_img.addItem(hist, row=0, col=1)
        # Optional: apply a matplotlib colormap
        cmap = pg.colormap.getFromMatplotlib("viridis")
        self.img2d_hdl.setLookupTable(cmap.getLookupTable())
        hist.gradient.setColorMap(cmap)

    def init_plot_hdl(self):
        self.plot_hdl = self.ui.widget_binhdl.addPlot()
        cmap = pg.colormap.get("plasma")
        self.img2d_hdl.setColorMap(cmap)

    # ------------------------------------------------------------------
    # Plotting / visualization
    # ------------------------------------------------------------------

    def plot_binned_data(self, result, show_rawdata=False, fit_pixel_size=False, parent_widget=None):
        """Render binned RIXS data onto the plot widget.

        Parameters
        ----------
        result : dict
            Output from ``RixsDataset.bin_data_wrap``.  Expected keys:
            ``rawdata_lines``, ``binned_line``, ``DeltaD_fit``,
            ``summed_data``, ``levels``.
        show_rawdata : bool, optional
            When *True* the individual raw-data lines are drawn in random
            colours behind the binned line.
        fit_pixel_size : bool, optional
            When *True* a dialog is shown asking whether to accept the fitted
            ``DeltaD`` value.  The fitted value is returned so the controller
            can update the model.
        parent_widget : QWidget, optional
            Parent for the confirmation dialog (pass ``self`` from the GUI
            class so the dialog is centred correctly).

        Returns
        -------
        float or None
            The accepted fitted ``DeltaD`` value when *fit_pixel_size* is
            *True* and the user confirmed, otherwise *None*.
        """
        self.plot_hdl.clear()
        if show_rawdata:
            for x, y in result["rawdata_lines"]:
                color = tuple(np.random.randint(100, 256, size=3))  # avoid dark colors
                pen = pg.mkPen(color=color, width=1)
                self.plot_hdl.plot(x, y, pen=pen)

        # Plot the binned line with error bars
        x, y, err = result["binned_line"]
        pen = pg.mkPen(color=(0, 0, 255), width=1)
        self.plot_hdl.plot(x, y, pen=pen)

        # --- Error bar item ---
        err_plot = pg.ErrorBarItem(x=x, y=y, top=err, bottom=err, beam=0.00001)
        self.plot_hdl.addItem(err_plot)

        self.plot_hdl.setLabel("left", "Intensity")
        self.plot_hdl.setLabel("bottom", "Energy (keV)")

        accepted_fitted_value = None
        if fit_pixel_size:
            fitted_value = float(result["DeltaD_fit"])
            reply = QMessageBox.question(
                parent_widget,
                "Update DeltaD Parameter",
                f"Update DeltaD parameter with fitted value {fitted_value:.6f} mm?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.Yes:
                accepted_fitted_value = fitted_value

        if result["summed_data"] is not None:
            self.img2d_hdl.setImage(np.flipud(result["summed_data"]), levels=result["levels"])

        return accepted_fitted_value

    def update_image(self, rixs_dset, frame_index, percentile_cutoff, binning_kwargs):
        """Render a single detector frame from *rixs_dset*.

        Parameters
        ----------
        rixs_dset : RixsDataset
            The currently selected dataset.
        frame_index : int
            Index of the frame to display.
        percentile_cutoff : float
            Percentile used to clip the colour scale.
        binning_kwargs : dict
            Keyword arguments forwarded to ``get_data_for_display``.

        Returns
        -------
        tuple
            ``(num_frames, frame_metadata)`` so the controller can update the
            slider range and sync the binning model.
        """
        data, levels, num_frames, frame_metadata = rixs_dset.get_data_for_display(
            frame_index=frame_index,
            percentile_cutoff=percentile_cutoff,
            **binning_kwargs,
        )
        self.ui.horizontalSlider_frame_index.setRange(0, num_frames - 1)
        self.img2d_hdl.setImage(np.flipud(data), levels=levels)
        self._update_roi(data.shape, binning_kwargs)
        return num_frames, frame_metadata

    # ------------------------------------------------------------------
    # ROI helpers
    # ------------------------------------------------------------------

    def _update_roi(self, image_shape, binning_kwargs):
        """Create (first call) or reposition (subsequent calls) the ROI overlay.

        The ROI is drawn in *display* coordinates — i.e. after ``np.flipud``
        has been applied to the image — so the Y axis runs from 0 (top of the
        displayed image) to ``image_shape[0] - 1`` (bottom).  In the original
        data:

        * row 0   → display row ``H - 1``
        * row H-1 → display row 0

        Therefore ``Ylow`` in data space maps to ``H - 1 - Ylow`` in display
        space, and ``Yhigh`` maps to ``H - 1 - Yhigh``.  The ROI's top-left
        corner is at display-y = ``H - 1 - Yhigh`` (smallest display-y) and
        its height is ``Yhigh - Ylow``.

        Parameters
        ----------
        image_shape : tuple of int
            ``(rows, cols)`` of the *original* (pre-flip) data array.
        binning_kwargs : dict
            Must contain ``"Ylow"``, ``"Yhigh"``, and ``"RefL"``.
        """
        ylow = binning_kwargs.get("Ylow", 0)
        yhigh = binning_kwargs.get("Yhigh", image_shape[0])
        refl = binning_kwargs.get("RefL", image_shape[1] // 2)

        H = image_shape[0]

        # Convert data-space Y bounds to display-space (flipud)
        disp_y_bottom = H - 1 - ylow  # larger display-y value
        disp_y_top = H - 1 - yhigh  # smaller display-y value

        roi_x = 0
        roi_y = disp_y_top
        roi_w = 2 * refl
        roi_h = disp_y_bottom - disp_y_top  # always >= 0

        if self._roi_rect is None:
            # Create once; make it non-interactive (display-only)
            self._roi_rect = pg.RectROI(
                pos=[roi_x, roi_y],
                size=[roi_w, roi_h],
                pen=pg.mkPen(color=(0, 255, 0), width=1),
                movable=False,
                resizable=False,
            )
            # Remove the scale handle that RectROI adds by default
            self._roi_rect.removeHandle(0)
            self._img_plot.addItem(self._roi_rect)
        elif self._roi_parameters != (ylow, yhigh, refl):
            self._roi_parameters = (ylow, yhigh, refl)
            self._roi_rect.setPos([roi_x, roi_y], finish=False)
            self._roi_rect.setSize([roi_w, roi_h], finish=False)
