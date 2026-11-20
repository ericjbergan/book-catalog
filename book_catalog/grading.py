"""Paperback grading rubric — the single source of truth.

Used by the ChatGPT edition-matching prompt in ebay/match.py, and referenced
from README.md so human readers see the same definitions the code enforces.
Change here and both stay in sync.
"""

GRADES = ["Fine", "Near Fine", "Very Good", "Good", "Fair", "Poor"]

# Ordered best → worst. Rendered into the ChatGPT prompt as-is.
GRADING_RUBRIC = """\
- **Fine (F)**: Appears unread, no defects, no creases, clean pages, tight binding, minimal wear
- **Near Fine (NF)**: Very minor defects, slight edge wear, no reading crease, clean pages
- **Very Good (VG)**: Shows careful use, may have reading crease, slight creases/scuffs, minor browning, all pages present
- **Good (G)**: More wear, multiple creases, may have markings, some wear to edges/corners, binding intact
- **Fair**: Significant wear, may have tears, heavy creasing, noticeable defects, but complete
- **Poor**: Heavy wear, missing pages, significant damage"""

# Heuristic hints for grading from a listing description when the seller didn't
# fill in the official Condition field.
DESCRIPTION_HINTS = """\
- "no creases" or "no reading crease" suggests Fine or Near Fine
- "some creasing" or "minor creasing" suggests Very Good
- "reading crease" or "spine crease" suggests Very Good to Good
- "wear on edges" or "corner wear" suggests Very Good to Good depending on severity
- "marks" or "writing" suggests Good or lower
- "tears" or "damage" suggests Fair or lower"""
