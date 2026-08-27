# Copyright © UChicago Argonne LLC
# See LICENSE file for details
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SETTINGS_DIR = Path.home() / ".rixsviewer"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"


def load_settings():
    """Load persisted user settings (e.g. last-used spec file / TIFF folder).

    Returns
    -------
    dict
        Empty dict if the settings file doesn't exist or can't be read.
    """
    if not SETTINGS_FILE.is_file():
        return {}
    try:
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"Could not read settings file {SETTINGS_FILE}: {e}")
        return {}


def save_settings(spec_filename, tiff_folder):
    """Persist the current spec file / TIFF folder for reload on next launch."""
    try:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, "w") as f:
            json.dump({"spec_filename": spec_filename, "tiff_folder": tiff_folder}, f)
    except OSError as e:
        logger.warning(f"Could not write settings file {SETTINGS_FILE}: {e}")
