# Copyright © UChicago Argonne LLC
# See LICENSE file for details
from silx.io.specfile import SpecFile

from rixsviewer.model.spec_parsers import (
    _get_metadata,
    get_scan_header,
    parse_single_scan,
    tiff_point_index,
)

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


def test_get_scan_header_classifies_rxesamesh_as_rxesscan(tmp_path):
    spec_path = tmp_path / "fake.spec"
    spec_path.write_text(
        "#F fake session\n"
        "#S 1  rxesamesh merixE 11.216 11.2134 72 kohzuE 12.652 12.66 18 1\n"
        "#D 2026-09-23 12:00:00\n"
        "#N 5\n"
        "#L KohzuE merixE i0 i2 mmepin1\n"
    )
    scan = next(iter(SpecFile(str(spec_path))))

    header = get_scan_header(scan)

    assert header["scan_type"] == "RXESScan"
    assert header["incident_start"] == 12.652
    assert header["incident_end"] == 12.66
    assert header["incident_points"] == 19
    assert header["emission_start"] == 11.216
    assert header["emission_end"] == 11.2134
    assert header["emission_points"] == 73
    assert header["steps"] == 19 * 73


def test_tiff_point_index_sorts_numerically_past_three_digits():
    # Regression test for the bug fixed in commit history: filenames are
    # zero-padded to 3 digits only (point001..point999, then point1000
    # unpadded), so a plain lexicographic sort silently reorders frames
    # once a scan exceeds ~100 points -- e.g. "..._point182.tif" would
    # sort between "..._point1819.tif" and "..._point1820.tif".
    names = [
        "23Sept2026c_scan11_point1819.tif",
        "23Sept2026c_scan11_point182.tif",
        "23Sept2026c_scan11_point1820.tif",
        "23Sept2026c_scan11_point001.tif",
        "23Sept2026c_scan11_point099.tif",
        "23Sept2026c_scan11_point100.tif",
    ]

    ordered = sorted(names, key=tiff_point_index)

    assert ordered == [
        "23Sept2026c_scan11_point001.tif",
        "23Sept2026c_scan11_point099.tif",
        "23Sept2026c_scan11_point100.tif",
        "23Sept2026c_scan11_point182.tif",
        "23Sept2026c_scan11_point1819.tif",
        "23Sept2026c_scan11_point1820.tif",
    ]


def _required_fields_as_b_lines():
    return "".join(f"#B {line}\n" for line in REQUIRED_FIELDS.splitlines())


def _write_rxes_spec(tmp_path):
    spec_path = tmp_path / "fake.spec"
    spec_path.write_text(
        "#F fake session\n"
        "#S 1  rxesamesh merixE 11.190 11.200 2 kohzuE 12.650 12.660 3 0.1\n"
        "#D 2026-09-27 12:00:00\n"
        "#N 5\n"
        "#L KohzuE merixE i0 i2 mmepin1\n"
        + _required_fields_as_b_lines()
    )
    return str(spec_path)


def test_parse_single_scan_propagates_rxes_axis_fields(tmp_path):
    spec_path = _write_rxes_spec(tmp_path)
    scan = next(iter(SpecFile(spec_path)))

    info = parse_single_scan(scan, spec_path, str(tmp_path))

    assert info["incident_start"] == 12.650
    assert info["incident_end"] == 12.660
    assert info["incident_points"] == 4
    assert info["emission_start"] == 11.190
    assert info["emission_end"] == 11.200
    assert info["emission_points"] == 3


def test_parse_single_scan_leaves_rxes_fields_none_for_energy_scan(tmp_path):
    spec_path = tmp_path / "fake.spec"
    spec_path.write_text(
        "#F fake session\n"
        "#S 1  ascan  merixE 11.190 11.200  2 0.1\n"
        "#D 2026-09-27 12:00:00\n"
        "#N 5\n"
        "#L merixE i0 i2 mmepin1\n"
        + _required_fields_as_b_lines()
    )
    scan = next(iter(SpecFile(str(spec_path))))

    info = parse_single_scan(scan, str(spec_path), str(tmp_path))

    assert info["incident_points"] is None
    assert info["emission_points"] is None
