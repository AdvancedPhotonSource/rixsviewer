import pyqtgraph as pg
import numpy as np


class RixsImageWidget(pg.GraphicsLayoutWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        plot = self.addPlot(row=0, col=0)
        plot.setLabel("bottom", "Energy bin")
        plot.setLabel("left", "Position (pixel)")
        plot.getViewBox().setAspectLocked(False)

        self.img2d_hdl = pg.ImageItem(axisOrder="row-major")
        plot.addItem(self.img2d_hdl)

        hist = pg.HistogramLUTItem()
        hist.setImageItem(self.img2d_hdl)
        self.addItem(hist, row=0, col=1)

        cmap = pg.colormap.getFromMatplotlib("viridis")
        self.img2d_hdl.setLookupTable(cmap.getLookupTable())
        hist.gradient.setColorMap(cmap)


class ImageViewWithAxes(pg.GraphicsLayoutWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Create a PlotItem (this provides axes, labels, etc.)
        self.plotItem = self.addPlot()
        self.plotItem.setLabel("bottom", "Energy")
        self.plotItem.setLabel("left", "Height")

        # Hide the default auto-generated curve stuff we don't need
        self.plotItem.showGrid(x=True, y=True)
        self.plotItem.enableAutoRange()

        # Create an ImageView, but tell it to use *our* ViewBox instead of creating its own
        self.imageView = pg.ImageView(view=self.plotItem.getViewBox())
        # Important: ImageView is a QWidget, so we don’t add it to the GraphicsLayout,
        # we just use its functionality and image item.
        data = np.random.normal(size=(200, 300))
        self.imageView.setImage(data)

        # The ImageView internally creates an ImageItem and puts it in the given ViewBox
        # We can access it via:
        self.imageItem = self.imageView.getImageItem()
