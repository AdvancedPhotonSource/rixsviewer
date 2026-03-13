"""Model layer for RixsViewer (MVC).

Exposes the two public model classes used by the controller.
"""

from .binning_model import RixsBinningModel
from .spec_table import RixsSpecTable

__all__ = ["RixsBinningModel", "RixsSpecTable"]
