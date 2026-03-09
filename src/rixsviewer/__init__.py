"""
RixsViewer - A tool for visualization and modeling of RIXS (Resonance Inelastic X-ray Scattering) data

This package provides tools for loading, visualizing, and analyzing RIXS spectroscopy data.
"""

import importlib.metadata

try:
    __version__ = importlib.metadata.version("rixsviewer")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"
__author__ = "MQICHU"

from .rixsviewer_gui import RixsViewerGUI

__all__ = ["RixsViewerGUI"]
