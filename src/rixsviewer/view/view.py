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

    # Tableau-10 palette: perceptually distinct, high-contrast, deterministic.
    # Cycles via  i % len(_LINE_COLORS)  when there are more lines than colours.
    _LINE_COLORS = (
        (31, 119, 180),  # blue
        (255, 127, 14),  # orange
        (44, 160, 44),  # green
        (214, 39, 40),  # red
        (148, 103, 189),  # purple
        (140, 86, 75),  # brown
        (227, 119, 194),  # pink
        (188, 189, 34),  # olive
        (23, 190, 207),  # cyan
        (127, 127, 127),  # grey
    )

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
        plot.invertY(True)  # row 0 at top; Y axis increases downward
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

        # widget_calibhdl: 1-row × 2-column layout
        # col 0 – calibration plot, col 1 – line-search plot
        self.calib_hdl = self.ui.widget_calibhdl.addPlot(row=0, col=0)
        self.linesearch_hdl = self.ui.widget_calibhdl.addPlot(row=0, col=1)
        self.ui.widget_calibhdl.ci.layout.setColumnStretchFactor(0, 1)
        self.ui.widget_calibhdl.ci.layout.setColumnStretchFactor(1, 1)

        cmap = pg.colormap.get("plasma")
        self.img2d_hdl.setColorMap(cmap)

    # ------------------------------------------------------------------
    # Plotting / visualization
    # ------------------------------------------------------------------

    def plot_binned_data(self, result, show_rawdata=False, hdl_target="plot"):
        """Render binned RIXS data onto the plot widget.

        Parameters
        ----------
        result : dict
            Output from ``RixsDataset.bin_data_wrap``.  Expected keys:
            ``rawdata_lines``, ``binned_line``, ``DeltaD``,
            ``summed_data``, ``levels``.
        show_rawdata : bool, optional
            When *True* the individual raw-data lines are drawn in random
            colours behind the binned line.
        """
        hdl = self.plot_hdl if hdl_target == "plot" else self.calib_hdl
        hdl.clear()
        if show_rawdata:
            for i, (x, y) in enumerate(result["rawdata_lines"]):
                color = self._LINE_COLORS[i % len(self._LINE_COLORS)]
                pen = pg.mkPen(color=color, width=1)
                hdl.plot(x, y, pen=pen)

        # Plot the binned line with error bars
        x, y, err = result["binned_line"]
        pen = pg.mkPen(color=(0, 0, 255), width=1)
        hdl.plot(x, y, pen=pen)

        # --- Error bar item ---
        err_plot = pg.ErrorBarItem(x=x, y=y, top=err, bottom=err, beam=0.00001)
        hdl.addItem(err_plot)

        hdl.setLabel("left", "Intensity")
        hdl.setLabel("bottom", "Energy (keV)")

        if result["summed_data"] is not None:
            self.img2d_hdl.setImage(result["summed_data"], levels=result["levels"])
        self.ui.label_energy_interval.setText(f"Energy interval: [{result['energy_resolution']:.3f} meV]")

    def plot_linesearch(self, ls):
        """Render the DeltaD vs FWHM line-search curve on ``linesearch_hdl``.

        Parameters
        ----------
        ls : dict
            Result dict returned by
            :meth:`~specfile_reader.RixsScanTiffDataset.linesearch_pixel_size`.
            Expected keys: ``lns_table``, ``lns_value``,
            ``org_value``, ``lsq_value``.
        """
        linesearch_table = ls["lns_table"]
        best_deltad = ls["lns_value"]
        original_deltad = ls["org_value"]
        hdl = self.linesearch_hdl
        hdl.clear()

        if not linesearch_table:
            return

        # Legend must exist before items are added (same pattern as calib_hdl)
        legend = hdl.addLegend(offset=(10, 10))

        deltad_arr = [row[0] for row in linesearch_table]
        fwhm_arr = [row[1] for row in linesearch_table]

        # Main scatter + line (no legend entry – it is the sweep curve)
        pen = pg.mkPen(color=(31, 119, 180), width=2)
        symbol_brush = pg.mkBrush(color=(31, 119, 180))
        hdl.plot(
            deltad_arr,
            fwhm_arr,
            pen=pen,
            symbol="o",
            symbolSize=6,
            symbolBrush=symbol_brush,
            symbolPen=None,
        )

        # Helper: add a vertical dashed line AND a matching legend entry
        def _vline(pos, color, legend_label, label_pos):
            line = pg.InfiniteLine(
                pos=pos,
                angle=90,
                pen=pg.mkPen(color=color, width=1, style=pg.QtCore.Qt.DashLine),
                label=f"{pos:.6f}",
                labelOpts={"position": label_pos, "color": color},
            )
            hdl.addItem(line)
            # Use a PlotDataItem as the colour swatch in the legend
            swatch = pg.PlotDataItem(pen=pg.mkPen(color=color, width=2))
            legend.addItem(swatch, legend_label)

        if original_deltad is not None:
            _vline(original_deltad, (127, 127, 127), "original", 0.70)

        if best_deltad is not None:
            _vline(best_deltad, (214, 39, 40), "linesearch", 0.86)

        hdl.setLabel("bottom", "DeltaD (mm)")
        hdl.setLabel("left", "FWHM (keV)")
        hdl.setTitle("Pixel-size line search")

    def plot_calib_overlay(self, ls):
        """Overlay three calibration spectra on ``calib_hdl``.

        Draws one binned line per result, colour-coded to match the vertical
        markers in ``linesearch_hdl``:

        * **grey**   — user's original ``DeltaD``
        * **orange** — least-squares fitted ``DeltaD``
        * **red**    — line-search best ``DeltaD`` (minimum FWHM)

        Parameters
        ----------
        ls : dict
            Result dict returned by
            :meth:`~specfile_reader.RixsScanTiffDataset.linesearch_pixel_size`.
            Expected keys: ``org_result``, ``lns_result``.
        """
        original_result = ls["org_result"]
        linesearch_result = ls["lns_result"]
        hdl = self.calib_hdl
        hdl.clear()

        # Legend must exist before plot() calls so named curves are registered
        legend = hdl.addLegend(offset=(10, 10))

        # (color, result, label) — same palette as the linesearch markers
        layers = [
            ((127, 127, 127), original_result, "original"),
            ((214, 39, 40), linesearch_result, "linesearch"),
        ]

        for color, result, label in layers:
            if result is None:
                continue
            x, y, err = result["binned_line"]
            fwhm_val = result.get("fwhm")
            fwhm_str = f"{fwhm_val * 1e6:.1f} meV" if fwhm_val is not None else "N/A"
            legend_name = f"{label} (FWHM={fwhm_str})"
            pen = pg.mkPen(color=color, width=2)
            hdl.plot(x, y, pen=pen, name=legend_name)
            err_item = pg.ErrorBarItem(
                x=x,
                y=y,
                top=err,
                bottom=err,
                beam=0.00001,
                pen=pg.mkPen(color=color, width=1),
            )
            hdl.addItem(err_item)

        hdl.setLabel("left", "Intensity")
        hdl.setLabel("bottom", "Energy (keV)")
        hdl.setTitle("Calibration spectra overlay")

        # Set x-axis range to ±8 × FWHM around the peak center.
        fwhm = linesearch_result["fwhm"]
        center = linesearch_result["center"]
        hdl.setXRange(center - 8 * fwhm, center + 8 * fwhm, padding=0)

    def update_image(self, data, levels, num_frames, binning_kwargs, scan_index, frame_index):
        """Render a single detector frame.

        Parameters
        ----------
        data : numpy.ndarray
            2-D frame array (pre-flip not yet applied).
        levels : tuple of (float, float)
            ``(vmin, vmax)`` colour scale limits.
        num_frames : int
            Total number of frames in the dataset (used to set slider range).
        binning_kwargs : dict
            Current binning parameters; forwarded to ``_update_roi`` so the
            ROI overlay reflects ``Ylow``, ``Yhigh``, and ``RefL``.
        """
        self.ui.horizontalSlider_frame_index.setRange(0, num_frames - 1)
        self.img2d_hdl.setImage(data, levels=levels)
        self._update_roi(data.shape, binning_kwargs)
        self.ui.groupBox_2d_scattering.setTitle(
            f"2D Scattering: [Scan: {scan_index}, Frame: {frame_index+1}/{num_frames}]"
        )

    # ------------------------------------------------------------------
    # ROI helpers
    # ------------------------------------------------------------------

    def _update_roi(self, image_shape, binning_kwargs):
        """Create (first call) or reposition (subsequent calls) the ROI overlay.

        With ``invertY(True)`` on the plot, display coordinates match data
        coordinates directly: row ``Ylow`` is at ``y = Ylow`` and row
        ``Yhigh`` is at ``y = Yhigh``.  No coordinate transformation is needed.

        Parameters
        ----------
        image_shape : tuple of int
            ``(rows, cols)`` of the data array (used for default fallbacks).
        binning_kwargs : dict
            Must contain ``"Ylow"``, ``"Yhigh"``, and ``"RefL"``.
        """
        ylow = binning_kwargs.get("Ylow", 0)
        yhigh = binning_kwargs.get("Yhigh", image_shape[0])
        refl = binning_kwargs.get("RefL", image_shape[1] // 2)

        roi_x = 0
        roi_y = ylow
        roi_w = 2 * refl
        roi_h = yhigh - ylow  # always >= 0

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
