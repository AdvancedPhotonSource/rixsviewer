"""
RixsViewer - A tool for visualization and modeling of RIXS (Resonance Inelastic X-ray Scattering) data

This package provides tools for loading, visualizing, and analyzing RIXS spectroscopy data.
"""

__version__ = "0.1.0"
__author__ = "MQICHU"

from .rixsviewer_gui import RixsViewerGUI
from .specfile_reader import RixsScanListTable

__all__ = ["RixsViewerGUI", "RixsScanListTable"]
