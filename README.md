# RixsViewer

A PySide6-based GUI application for visualizing and analyzing RIXS (Resonance Inelastic X-ray Scattering) spectroscopy data.

## Features

- Load and display SPEC scan files and Lambda detector TIFF stacks
- Rowland-circle geometry binning of 2D detector images into 1D energy spectra
- Real-time auto-update mode for live data monitoring during beam time
- Calibration tools for pixel size and crystal tilt angle optimization
- Export binned spectra to SPEC-format files
- EPICS PV integration for live instrument parameter readback (optional)

## Installation

```bash
pip install rixsviewer
```

With EPICS PV support (APS beamline systems):

```bash
pip install rixsviewer[epics]
```

## Usage

```bash
rixsviewer --specfile /path/to/scan.spec --tiff-folder /path/to/tiffs/
```

Or launch without arguments and use the file browser buttons in the GUI.

## Requirements

- Python >= 3.8
- PySide6, numpy, scipy, pyqtgraph, silx, tifffile, pandas, matplotlib

## License

Apache-2.0 — Copyright © 2026 UChicago Argonne, LLC
