# Copyright © UChicago Argonne LLC
# See LICENSE file for details
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SETTINGS_DIR = Path.home() / ".rixsviewer"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"


def _read_settings_file():
    if not SETTINGS_FILE.is_file():
        return {}
    try:
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Could not read settings file {SETTINGS_FILE}: {e}")
        return {}


def _write_settings_file(data):
    try:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, "w") as f:
            json.dump(data, f)
    except OSError as e:
        logger.warning(f"Could not write settings file {SETTINGS_FILE}: {e}")


def load_settings():
    """Load persisted user settings (spec file / TIFF folder, splitter sizes, ...).

    Returns
    -------
    dict
        Empty dict if the settings file doesn't exist or can't be read.
    """
    return _read_settings_file()


def save_settings(spec_filename, tiff_folder):
    """Persist the current spec file / TIFF folder for reload on next launch.

    Merges into the existing settings file rather than overwriting it, so
    this doesn't clobber splitter sizes saved separately (see
    :func:`save_splitter_state`).
    """
    data = _read_settings_file()
    data["spec_filename"] = spec_filename
    data["tiff_folder"] = tiff_folder
    _write_settings_file(data)


def save_splitter_state(splitter_states):
    """Persist splitter sizes for reload on next launch.

    Parameters
    ----------
    splitter_states : dict
        Maps a splitter's objectName to its ``QSplitter.saveState()`` bytes,
        base64-encoded as a str (JSON can't hold raw bytes). Merges into the
        existing settings file rather than overwriting it, so this doesn't
        clobber the spec file / TIFF folder saved separately.
    """
    data = _read_settings_file()
    data["splitter_state"] = splitter_states
    _write_settings_file(data)


def save_window_geometry(encoded_geometry):
    """Persist the main window's geometry for reload on next launch.

    Parameters
    ----------
    encoded_geometry : str
        ``QMainWindow.saveGeometry()`` bytes, base64-encoded as a str (JSON
        can't hold raw bytes). Merges into the existing settings file rather
        than overwriting it, so this doesn't clobber settings saved
        separately.
    """
    data = _read_settings_file()
    data["window_geometry"] = encoded_geometry
    _write_settings_file(data)
