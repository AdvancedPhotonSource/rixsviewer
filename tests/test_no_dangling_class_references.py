# Copyright © UChicago Argonne LLC
# See LICENSE file for details
"""Regression test for a code-review finding: RixsScanTiffDataset was
deleted when it was split into RixsEnergyScanDataset/RixsSnapshotScanDataset,
but several docstrings and CLAUDE.md still named it.

Deliberately excludes src/rixsviewer/view/view.py, which has its own
pre-existing, unrelated stale reference to a nonexistent "specfile_reader"
module -- out of scope for this split, left alone per the design spec.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXCLUDED = {REPO_ROOT / "src" / "rixsviewer" / "view" / "view.py"}


def test_no_references_to_deleted_rixsscantiffdataset_class():
    offenders = []
    files = [REPO_ROOT / "CLAUDE.md"]
    files.extend((REPO_ROOT / "src").rglob("*.py"))

    for fname in files:
        if fname in EXCLUDED:
            continue
        if "RixsScanTiffDataset" in fname.read_text(encoding="utf-8"):
            offenders.append(str(fname.relative_to(REPO_ROOT)))

    assert offenders == []
