# Copyright © UChicago Argonne LLC
# See LICENSE file for details
# bad_pixels.py
# ─────────────────────────────────────────────────────────────────────────────
# List of known bad pixel coordinates for the Lambda detector.
#
# Each entry is a (row, col) tuple in detector-pixel coordinates (0-indexed).
# Add or remove entries here; the rest of the pipeline picks them up
# automatically via  fix_bad_pixels()  in utils.py.
# ─────────────────────────────────────────────────────────────────────────────

BAD_PIXELS = [
    (101, 147),
    (98, 170),
    (234, 156),
]
