# Copyright © UChicago Argonne LLC
# See LICENSE file for details
"""Lightweight SPEC data-file reader (replaces ``silx.io.specfile``).

Only what RixsViewer needs: scan numbers, the scan header dictionary and the
data block, exposed with the same names and layout silx uses
(``number``, ``scan_header_dict``, ``data`` as columns x points).
"""

import os
import re

import numpy as np

_SCAN_LINE = re.compile(r"#S\s+(\d+)")
_HEADER_LINE = re.compile(r"#(\w+) *(.*)")
_LABEL_SEPARATOR = re.compile(r"\s{2,}")
# how many already-read bytes refresh() re-reads to notice an in-place rewrite
_TAIL_CHECK_BYTES = 64


class SpecScan:
    """One ``#S`` block of a SPEC file."""

    def __init__(self, number):
        self.number = number
        self.scan_header_dict = {}
        self._pending = []  # data lines not parsed yet (parsed on the next .data access)
        self._data = None  # parsed rows so far, (n_columns, n_points)

    def _add_header(self, key, value):
        if key in self.scan_header_dict:
            self.scan_header_dict[key] += "\n" + value
        else:
            self.scan_header_dict[key] = value

    def _add_data_line(self, line):
        self._pending.append(line)

    @property
    def labels(self):
        """Column labels from ``#L``; labels are separated by two or more spaces."""
        label_line = self.scan_header_dict.get("L", "").strip()
        return _LABEL_SEPARATOR.split(label_line) if label_line else []

    def _n_columns(self):
        """Expected values per data row: ``#N``, else the label count, else unknown."""
        try:
            return int(self.scan_header_dict["N"].split()[0])
        except (KeyError, IndexError, ValueError):
            return len(self.labels) or None

    @property
    def data(self):
        """Scan data as a float array of shape ``(n_columns, n_points)``.

        Rows that are not all numbers, or whose length differs from the
        expected column count, are skipped.
        """
        if self._pending:
            self._parse_pending()
        if self._data is None:
            return np.empty((self._n_columns() or 0, 0), dtype=float)
        return self._data

    def _parse_pending(self):
        n_columns = self._n_columns()
        if n_columns is None and self._data is not None:
            n_columns = self._data.shape[0]  # set by the first row read earlier
        rows = []
        for line in self._pending:
            values = line.split()
            if n_columns is None:
                n_columns = len(values)
            if len(values) != n_columns:
                continue
            try:
                rows.append([float(v) for v in values])
            except ValueError:
                continue
        self._pending = []
        if rows:
            new = np.array(rows, dtype=float).T
            # only the numpy array is kept: Python float lists cost ~5x the memory
            self._data = new if self._data is None else np.concatenate([self._data, new], axis=1)


class SpecReader:
    """Read a SPEC data file into :class:`SpecScan` objects, incrementally.

    The reader remembers how far into the file it has read. :meth:`refresh`
    reads only the bytes appended since then and adds them to the open scan
    (or starts new ones); scans that were already complete are not touched
    again. This relies on SPEC only ever appending to its data file. A file
    that got shorter, was replaced by a new file under the same name, or whose
    last-read bytes changed is read again from the start.

    A final line without its newline is left for a later refresh: SPEC may
    still be writing it.
    """

    def __init__(self, path):
        self.path = str(path)
        self._reset()
        self.refresh()

    def _reset(self):
        self._scans = []
        self._offset = 0  # bytes consumed: always just after a newline
        self._tail = b""  # the last consumed bytes, to detect in-place rewrites
        self._file_id = None  # (st_dev, st_ino) of the file last read

    def refresh(self):
        """
        Read what was appended to the file since the last read.

        Returns
        -------
        bool
            ``True`` if new complete lines were read or the file had to be
            read again from the start; ``False`` if nothing changed.
        """
        with open(self.path, "rb") as f:
            st = os.fstat(f.fileno())
            file_id = (st.st_dev, st.st_ino)
            restarted = False
            if self._file_id is not None and (file_id != self._file_id or st.st_size < self._offset):
                self._reset()  # replaced or truncated
                restarted = True
            self._file_id = file_id
            f.seek(self._offset - len(self._tail))
            chunk = f.read()

        if not chunk.startswith(self._tail):
            # the bytes we already read changed: the file was rewritten in place
            self._reset()
            self.refresh()
            return True

        n_tail = len(self._tail)
        new = chunk[n_tail:]
        end = new.rfind(b"\n") + 1
        if end == 0:
            return restarted
        complete = new[:end]
        self._offset += end
        self._tail = (self._tail + complete)[-_TAIL_CHECK_BYTES:]
        for line in complete.decode("utf-8", errors="replace").splitlines():
            self._feed(line)
        return True

    def _feed(self, line):
        if line.startswith("#S"):
            m = _SCAN_LINE.match(line)
            if m:
                self._scans.append(SpecScan(int(m.group(1))))
                self._scans[-1]._add_header("S", line[2:].lstrip(" "))
            return
        if not self._scans:
            return  # file header, before the first scan
        scan = self._scans[-1]
        if line.startswith("#"):
            m = _HEADER_LINE.match(line)
            if m:
                scan._add_header(m.group(1), m.group(2))
        elif line.strip() and not line.startswith("@"):  # "@A ..." are MCA lines
            scan._add_data_line(line)

    def __len__(self):
        return len(self._scans)

    def number(self, index):
        """Scan number of the scan at position *index* in the file."""
        return self._scans[index].number

    def __getitem__(self, index):
        return self._scans[index]


def read_scan_numbers(path):
    """
    Return the number of every scan in a SPEC file, in file order.

    Streams the file and looks only at ``#S`` lines, so large files (e.g. the
    results file of a long beamtime) are never held in memory.
    """
    numbers = []
    with open(path, "rb") as f:
        for raw in f:
            if raw.startswith(b"#S"):
                m = _SCAN_LINE.match(raw.decode("utf-8", errors="replace"))
                if m:
                    numbers.append(int(m.group(1)))
    return numbers
