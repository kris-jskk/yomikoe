"""300-page soak fixture generator (M4 gate clause 1; PRD "300-page soak").

``generate_soak_pdf`` writes a text PDF with reportlab (BSD-3, dev dependency only): A4 pages,
11 pt Helvetica body text, about 20 varied English sentences per page in paragraphs of five,
and a "Chapter N" heading at the top of every tenth page (pages 1, 11, 21, ...). The sentence
generator is seeded, so the document is the same on every run, and it varies subjects, verbs,
objects, numbers and years so segment texts differ. Generated at test time; never committed.
"""

from __future__ import annotations

import random
from pathlib import Path

SUBJECTS = (
    "The harbour committee",
    "A small research team",
    "The regional council",
    "Our field engineer",
    "The village librarian",
    "An independent auditor",
    "The night shift",
    "The museum curator",
    "A visiting geologist",
    "The rail operator",
    "The school board",
    "A local farmer",
    "The volunteer crew",
    "The weather station",
    "The city archivist",
    "A retired pilot",
)
VERBS = (
    "reviewed",
    "measured",
    "rebuilt",
    "documented",
    "questioned",
    "inspected",
    "moved",
    "catalogued",
    "repaired",
    "photographed",
    "estimated",
    "compared",
    "replaced",
    "described",
)
OBJECTS = (
    "the old pumping station",
    "the northern footbridge",
    "the flood records",
    "the copper roof",
    "the orchard boundary",
    "the signal cabin",
    "the tidal gauges",
    "the parish ledgers",
    "the grain silos",
    "the coastal path",
    "the solar array",
    "the mill wheel",
    "the survey maps",
    "the water mains",
    "the lighthouse lens",
    "the market hall",
)
TAILS = (
    "after a long dry summer",
    "before the spring tides arrived",
    "during the autumn storms",
    "with help from two neighbours",
    "despite a tight budget",
    "while the river ran high",
    "under a cloudless sky",
    "as the season turned",
    "without stopping for lunch",
    "ahead of the annual inspection",
)
UNITS = ("metres", "kilograms", "litres", "hours", "volunteers", "pages", "kilometres", "panels")


def _sentence(rng: random.Random) -> str:
    kind = rng.randrange(4)
    s, v, o, t = rng.choice(SUBJECTS), rng.choice(VERBS), rng.choice(OBJECTS), rng.choice(TAILS)
    n, unit, year = rng.randint(2, 980), rng.choice(UNITS), rng.randint(1850, 2024)
    if kind == 0:
        return f"{s} {v} {o} in {year} {t}."
    if kind == 1:
        return f"In {year}, {s.lower()} {v} {o} and counted {n} {unit}."
    if kind == 2:
        return f"{s} {v} {o}, which took {n} {unit} {t}."
    return f"By {year} {o} had been {v} twice, and {s.lower()} noted {n} {unit} along the way."


def generate_soak_pdf(path: Path, pages: int = 300, seed: int = 300) -> Path:
    """Write the soak PDF to ``path`` and return it."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import simpleSplit
    from reportlab.pdfgen import canvas

    rng = random.Random(seed)
    width, height = A4
    margin, size, leading = 72.0, 11.0, 14.0
    text_width = width - 2 * margin
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setTitle("Soak Test Volume")
    for page in range(1, pages + 1):
        y = height - margin
        if page % 10 == 1:
            c.setFont("Helvetica-Bold", 18)
            c.drawString(margin, y - 18, f"Chapter {page // 10 + 1}")
            y -= 18 + 2 * leading
        c.setFont("Helvetica", size)
        for _paragraph in range(4):
            text = " ".join(_sentence(rng) for _ in range(5))
            for line in simpleSplit(text, "Helvetica", size, text_width):
                y -= leading
                c.drawString(margin, y, line)
            y -= leading * 0.8
        c.showPage()
    c.save()
    return path
