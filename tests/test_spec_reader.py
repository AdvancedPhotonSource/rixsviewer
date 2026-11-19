# Copyright © UChicago Argonne LLC
# See LICENSE file for details
"""Tests for the in-house incremental SPEC reader that replaced silx."""

import numpy as np
import pytest

from rixsviewer.model.spec_reader import SpecReader, read_scan_numbers

TWO_SCANS = (
    "#F session.spec\n"
    "#E 1700000000\n"
    "#O0 mot1  mot2\n"
    "\n"
    "#S 1  ascan  merixE 11.19 11.20  1 0.1\n"
    "#D Thu Nov 19 14:59:40 2026\n"
    "#N 3\n"
    "#L merixE  i0  i2\n"
    "11.19 100 10\n"
    "11.20 101 11\n"
    "\n"
    "#S 2  ascan  merixE 11.30 11.31  2 0.1\n"
    "#N 3\n"
    "#L merixE  i0  i2\n"
    "11.30 200 20\n"
    "11.305 201 21\n"
    "11.31 202 22\n"
)


def _write(path, text, mode="w"):
    with open(path, mode) as f:
        f.write(text)


class TestFullRead:
    def test_reads_scan_numbers_headers_and_data(self, tmp_path):
        spec = tmp_path / "session.spec"
        _write(spec, TWO_SCANS)

        reader = SpecReader(str(spec))

        assert len(reader) == 2
        assert [reader.number(0), reader.number(1)] == [1, 2]
        scan = reader[1]
        assert scan.number == 2
        assert scan.scan_header_dict["S"] == "2  ascan  merixE 11.30 11.31  2 0.1"
        assert scan.scan_header_dict["L"] == "merixE  i0  i2"
        # silx layout: one row per column (columns x points)
        np.testing.assert_array_equal(scan.data, [[11.30, 11.305, 11.31], [200, 201, 202], [20, 21, 22]])

    def test_repeated_header_keys_are_joined_with_newlines(self, tmp_path):
        # 27-ID writes one "#XB key = value" line per analyzer parameter
        spec = tmp_path / "session.spec"
        _write(
            spec,
            "#S 7  ascan  merixE 11.19 11.20  1 0.1\n"
            "#XB Analyzer_EB_keV = 11.184\n"
            "#XB TiltAngle_deg = -1.600000\n"
            "#N 1\n#L merixE\n11.19\n",
        )

        assert SpecReader(str(spec))[0].scan_header_dict["XB"] == (
            "Analyzer_EB_keV = 11.184\nTiltAngle_deg = -1.600000"
        )

    def test_labels_split_on_runs_of_two_or_more_spaces(self, tmp_path):
        spec = tmp_path / "session.spec"
        _write(spec, "#S 1  ascan  merixE 1 2  1 0.1\n#N 3\n#L Energy keV  i0  Two Words\n1 2 3\n")

        assert SpecReader(str(spec))[0].labels == ["Energy keV", "i0", "Two Words"]


class TestDataEdgeCases:
    def test_comment_lines_inside_the_data_block_are_skipped(self, tmp_path):
        spec = tmp_path / "session.spec"
        _write(
            spec,
            "#S 1  ascan  merixE 1 2  2 0.1\n#N 2\n#L merixE  i0\n"
            "1.0 10\n"
            "#C waited 300 seconds to stabilize.\n"
            "#Y EnergyScan\n"
            "1.5 15\n"
            "#C resume scan after beam is back.\n"
            "2.0 20\n",
        )

        np.testing.assert_array_equal(SpecReader(str(spec))[0].data, [[1.0, 1.5, 2.0], [10, 15, 20]])

    def test_malformed_rows_are_skipped(self, tmp_path):
        spec = tmp_path / "session.spec"
        _write(
            spec,
            "#S 1  ascan  merixE 1 2  2 0.1\n#N 2\n#L merixE  i0\n"
            "1.0 10\n"
            "1.2\n"  # too few columns
            "1.3 13 99\n"  # too many columns
            "1.4 abc\n"  # not a number
            "@A 1 2\n"  # MCA line
            "2.0 20\n",
        )

        np.testing.assert_array_equal(SpecReader(str(spec))[0].data, [[1.0, 2.0], [10, 20]])

    def test_scan_without_data_has_one_row_per_label_and_no_points(self, tmp_path):
        # aborted / just-started scans; _get_scandata relies on this shape
        spec = tmp_path / "session.spec"
        _write(spec, "#S 1  ascan  merixE 1 2  2 0.1\n#N 3\n#L merixE  i0  i2\n")

        assert SpecReader(str(spec))[0].data.shape == (3, 0)

    def test_unterminated_last_line_is_not_read(self, tmp_path):
        # SPEC may be halfway through writing a row: "11.2153 3" of "11.2153 3456"
        spec = tmp_path / "session.spec"
        _write(spec, "#S 1  ascan  merixE 1 2  2 0.1\n#N 2\n#L merixE  i0\n1.0 10\n2.0 3")

        np.testing.assert_array_equal(SpecReader(str(spec))[0].data, [[1.0], [10]])


SCAN_1 = "#S 1  ascan  merixE 1 2  2 0.1\n#N 2\n#L merixE  i0\n1.0 10\n1.5 15\n2.0 20\n"
SCAN_2_START = "#S 2  ascan  merixE 3 4  2 0.1\n#N 2\n#L merixE  i0\n3.0 30\n"


class TestRefresh:
    def test_column_count_from_first_row_holds_across_refreshes(self, tmp_path):
        # no #N / #L: the first row decides the width, also for rows read later
        spec = tmp_path / "live.spec"
        _write(spec, "#S 1  ascan  merixE 1 2  2 0.1\n1.0 10\n")
        reader = SpecReader(str(spec))
        assert reader[0].data.shape == (2, 1)

        _write(spec, "1.5\n2.0 20\n", mode="a")
        reader.refresh()

        np.testing.assert_array_equal(reader[0].data, [[1.0, 2.0], [10, 20]])

    def test_refresh_reads_appended_rows_and_new_scans(self, tmp_path):
        spec = tmp_path / "live.spec"
        _write(spec, SCAN_1 + SCAN_2_START)
        reader = SpecReader(str(spec))
        scan_1 = reader[0]
        assert reader[1].data.shape == (2, 1)

        _write(spec, "3.5 35\n#S 3  ascan  merixE 5 6  2 0.1\n#N 2\n#L merixE  i0\n5.0 50\n", mode="a")

        assert reader.refresh() is True
        assert len(reader) == 3
        np.testing.assert_array_equal(reader[1].data, [[3.0, 3.5], [30, 35]])
        np.testing.assert_array_equal(reader[2].data, [[5.0], [50]])
        # finished scans are kept as they are, not re-read from the file
        assert reader[0] is scan_1

    def test_refresh_reports_no_change_when_nothing_was_appended(self, tmp_path):
        spec = tmp_path / "live.spec"
        _write(spec, SCAN_1)
        reader = SpecReader(str(spec))

        assert reader.refresh() is False
        assert len(reader) == 1

    def test_refresh_completes_a_partially_written_row(self, tmp_path):
        spec = tmp_path / "live.spec"
        _write(spec, SCAN_2_START + "3.5 3")
        reader = SpecReader(str(spec))
        np.testing.assert_array_equal(reader[0].data, [[3.0], [30]])

        _write(spec, "456\n", mode="a")

        assert reader.refresh() is True
        np.testing.assert_array_equal(reader[0].data, [[3.0, 3.5], [30, 3456]])

    def test_refresh_rereads_a_file_replaced_by_a_new_one(self, tmp_path):
        spec = tmp_path / "live.spec"
        _write(spec, SCAN_1 + SCAN_2_START)
        reader = SpecReader(str(spec))
        replacement = tmp_path / "new.spec"
        _write(replacement, "#S 9  ascan  merixE 9 9.5  1 0.1\n#N 2\n#L merixE  i0\n9.0 90\n")
        replacement.replace(spec)  # new file under the same name

        assert reader.refresh() is True
        assert [reader.number(i) for i in range(len(reader))] == [9]
        np.testing.assert_array_equal(reader[0].data, [[9.0], [90]])

    def test_refresh_rereads_a_file_truncated_in_place(self, tmp_path):
        spec = tmp_path / "live.spec"
        _write(spec, SCAN_1 + SCAN_2_START)
        reader = SpecReader(str(spec))

        _write(spec, "#S 4  ascan  merixE 4 5  1 0.1\n#N 2\n#L merixE  i0\n4.0 40\n")  # shorter

        assert reader.refresh() is True
        assert [reader.number(i) for i in range(len(reader))] == [4]

    def test_refresh_rereads_a_file_rewritten_in_place_with_more_content(self, tmp_path):
        # same file, same or larger size, but the part already read changed
        spec = tmp_path / "live.spec"
        _write(spec, SCAN_1)
        reader = SpecReader(str(spec))

        _write(spec, SCAN_1.replace("2.0 20", "2.0 99") + SCAN_2_START)

        assert reader.refresh() is True
        assert len(reader) == 2
        np.testing.assert_array_equal(reader[0].data, [[1.0, 1.5, 2.0], [10, 15, 99]])


def test_read_scan_numbers_lists_every_scan_in_file_order(tmp_path):
    spec = tmp_path / "results.spec"
    _write(
        spec,
        "#F results\n#C #S 99 in a comment is not a scan\n\n"
        "#S 12 EnergyScan\n#L Energy_keV  Intensity\n1 2\n\n"
        "#S 3 EnergyScan\n#L Energy_keV  Intensity\n1 2\n\n"
        "#S 250 RXESScan\n#L A  B\n1 2\n",
    )

    assert read_scan_numbers(str(spec)) == [12, 3, 250]


# Real beamtime files to compare against silx, which this reader replaced.
# Override with RIXS_SPEC_PARITY_FILES (os.pathsep-separated paths).
_DEFAULT_PARITY_FILES = (
    "/home/beams28/RIXS/Data/2026-3/slot11_bj/nov2026_irl3",
    "/home/beams28/RIXS/Data/2026-3/slot11_bj/nov2026_irl3_bindata_rixsviewer.spec",
)


def _parity_files():
    import os

    env = os.environ.get("RIXS_SPEC_PARITY_FILES")
    paths = env.split(os.pathsep) if env else _DEFAULT_PARITY_FILES
    return [p for p in paths if os.path.isfile(p)]


@pytest.mark.parametrize("path", _parity_files() or [pytest.param(None, marks=pytest.mark.skip("no SPEC files"))])
def test_matches_silx_on_real_beamtime_files(path, tmp_path):
    specfile = pytest.importorskip("silx.io.specfile")
    # SPEC may append to a live file between the two reads: compare both
    # readers on one snapshot, cut after its last complete line
    raw = open(path, "rb").read()
    snapshot = tmp_path / "snapshot.spec"
    snapshot.write_bytes(raw[: raw.rfind(b"\n") + 1])
    sf = specfile.SpecFile(str(snapshot))
    reader = SpecReader(str(snapshot))

    assert [reader.number(i) for i in range(len(reader))] == [sf.number(i) for i in range(len(sf))]
    for i in range(len(sf)):
        expected, actual = sf[i], reader[i]
        for key in ("S", "N", "L", "XB", "B"):
            assert actual.scan_header_dict.get(key) == expected.scan_header_dict.get(key), (expected.number, key)
        assert actual.labels == expected.labels, expected.number
        if expected.data.size == 0:
            # aborted scans: silx gives (0, 0), we keep one row per label
            # (n_columns, 0); _get_scandata treats both as "no points"
            assert actual.data.shape[1:] == (0,), expected.number
            continue
        assert actual.data.shape == expected.data.shape, expected.number
        np.testing.assert_array_equal(actual.data, expected.data, err_msg=f"scan {expected.number}")


def test_scan_table_works_without_silx_installed(tmp_path):
    """The packaged app ships without silx; loading a SPEC file must not need it."""
    import subprocess
    import sys
    import textwrap

    from conftest import FakeBeamline

    beamline = FakeBeamline(str(tmp_path))
    beamline.run_scan(1)
    beamline.run_scan(2)
    spec = beamline.spec
    script = textwrap.dedent(f"""
        import os, sys
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        sys.modules["silx"] = None  # any "import silx..." now raises ImportError
        from PySide6.QtWidgets import QApplication
        app = QApplication([])
        import rixsviewer.rixsviewer_gui
        from rixsviewer.model.spec_table import RixsSpecTable
        table = RixsSpecTable({str(spec)!r}, {str(tmp_path)!r}, {str(tmp_path / "out.spec")!r})
        print(table.rowCount())
        """)
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=120)

    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip().splitlines()[-1] == "2"
