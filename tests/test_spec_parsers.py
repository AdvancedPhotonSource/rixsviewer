# Copyright © UChicago Argonne LLC
# See LICENSE file for details
from rixsviewer.model.spec_parsers import _get_metadata

REQUIRED_FIELDS = (
    "Analyzer_EB_keV = 11.184\n"
    "Rowland_Radius_m = 1998\n"
    "Center_x_pixel = 77\n"
    "Low_y_pixel = 0\n"
    "High_y_pixel = 256\n"
    "Analyzer_Crystal_Size_mm = 1.3\n"
    "Lambda_Strip_Size_mm = 0.02\n"
)


def test_get_metadata_parses_tilt_angle_from_header():
    header = REQUIRED_FIELDS + "TiltAngle_deg = 3.5\n"
    metadata = _get_metadata(header)
    assert metadata["TiltAngle"] == 3.5


def test_get_metadata_defaults_tilt_angle_when_missing():
    metadata = _get_metadata(REQUIRED_FIELDS)
    assert metadata["TiltAngle"] == 0.0
