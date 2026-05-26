# RIXS Viewer Agent Instructions

## Project Overview
RixsViewer is a PySide6-based GUI application for visualizing and analyzing RIXS (Resonance Inelastic X-ray Scattering) spectroscopy data. It processes 2D detector images into 1D energy spectra using Rowland circle geometry binning, with real-time monitoring and calibration capabilities.

## Architecture
Follows MVC pattern:
- **Model**: Data processing, parameter management, SPEC/TIFF file handling
- **View**: PyQtGraph-based visualization of 2D images and 1D spectra
- **Controller**: Main GUI coordinating model/view interactions

Key components:
- `RixsBinningModel`: Parameter management with EPICS PV integration
- `RixsScanTiffDataset`: Lazy TIFF loading and spectrum binning
- `RixsSpecTable`: Incremental SPEC file processing
- `RixsView`: PyQtGraph visualization
- `RixsViewerGUI`: Main application window

## Development Workflow
- **Install**: `pip install -e ".[dev,docs]"`
- **Format**: `black --line-length=120 src/`
- **Lint**: `flake8 src/`
- **Test**: `pytest tests/` (currently no tests)
- **Docs**: `cd docs && make html`
- **Run**: `rixsviewer [--specfile PATH] [--tiff-folder PATH]`

## Conda Environment
- use `/home/beams/MQICHU/.conda/envs/d2603_rixs` as the conda environment for testing and debuging.

## Conventions
- **Logging**: Use `logging.getLogger(__name__)` with INFO for workflow, DEBUG for lazy loading
- **Threading**: Long operations in `QThreadPool` via `Worker(QRunnable)` with signals
- **Data Flow**: SPEC → scan classification → lazy TIFF loading → binning → visualization
- **Auto-update**: 1s timer polls SPEC file mtime for incremental processing
- **Calibration**: Line search optimization for pixel size/tilt angle

## Common Pitfalls
- Large TIFF stacks consume significant RAM
- EPICS PV access may fail silently if environment not configured
- SPEC file watching only checks mtime, not content
- Threading errors logged but don't halt UI
- Manual type casting in PV reading (fragile)
- No test coverage increases regression risk

## Documentation
- [User Guide](docs/source/user_guide.rst): CLI usage, workflow, calibration
- [API Docs](docs/build/html/): Auto-generated from docstrings
- [Pyproject.toml](pyproject.toml): Build config, dependencies, tool settings</content>
<parameter name="filePath">/home/beams/MQICHU/Tools_cloud/rixs_tools/rixsviewer_dev/AGENTS.md