"""Names of mathematical symbols for the MATH-1 fallback (ING-6; PRD MATH-1, D36-D37).

When structured maths is not recovered, the PRD's MATH-1 fallback reads "the symbols left to
right by name, never silence and never symbol soup". This module is the data for that fallback:
one table from a character to its spoken English name, in ClearSpeak style. It is data, not code,
so M5 (MATH-1 / MATH-2 proper) can extend it. The rule that applies it, with its spacing and its
guards, is ``hearnarro.ingestion.normalize._speak_symbols``.

Three groups need context and are therefore not in ``SYMBOL_NAMES``:
``CONTEXT_NAMES`` ("<", ">", "·", "−") are spoken only in a maths position (see the rule);
``LETTER_NAMES`` (blackboard bold) replace a letter with a letter and are never padded with spaces.
"""

from __future__ import annotations

RELATIONS: dict[str, str] = {
    "≥": "greater than or equal to",
    "⩾": "greater than or equal to",
    "≤": "less than or equal to",
    "⩽": "less than or equal to",
    "≈": "approximately equal to",
    "≍": "asymptotically equal to",
    "≪": "much less than",
    "≫": "much greater than",
    "∼": "is similar to",
    "≡": "is identical to",
    "∝": "is proportional to",
}

SETS_AND_LOGIC: dict[str, str] = {
    "∈": "in",
    "∉": "not in",
    "⊂": "subset of",
    "⊆": "subset of",
    "⊃": "superset of",
    "⊇": "superset of",
    "∪": "union",
    "∩": "intersect",
    "∅": "the empty set",
    "∀": "for all",
    "∃": "there exists",
    "∧": "and",
    "∨": "or",
    "¬": "not",
}

OPERATORS: dict[str, str] = {
    "×": "times",
    "±": "plus or minus",
    "∓": "minus or plus",
    "÷": "divided by",
    "∘": "composed with",
    "⊗": "tensor",
    "⊕": "direct sum",
    "∇": "nabla",
    "∂": "partial",
    "∑": "sum",
    "∏": "product",
    "∫": "integral",
    "√": "square root of",
    "∞": "infinity",
    "→": "goes to",
    "↦": "maps to",
    "⇒": "implies",
    "⇔": "if and only if",
}

_GREEK = [
    ("α", "Α", "alpha"),
    ("β", "Β", "beta"),
    ("γ", "Γ", "gamma"),
    ("δ", "Δ", "delta"),
    ("ε", "Ε", "epsilon"),
    ("ζ", "Ζ", "zeta"),
    ("η", "Η", "eta"),
    ("θ", "Θ", "theta"),
    ("ι", "Ι", "iota"),
    ("κ", "Κ", "kappa"),
    ("λ", "Λ", "lambda"),
    ("μ", "Μ", "mu"),
    ("ν", "Ν", "nu"),
    ("ξ", "Ξ", "xi"),
    ("ο", "Ο", "omicron"),
    ("π", "Π", "pi"),
    ("ρ", "Ρ", "rho"),
    ("σ", "Σ", "sigma"),
    ("τ", "Τ", "tau"),
    ("υ", "Υ", "upsilon"),
    ("φ", "Φ", "phi"),
    ("χ", "Χ", "chi"),
    ("ψ", "Ψ", "psi"),
    ("ω", "Ω", "omega"),
]
# Lower and upper case by name; capitals read the same name ("Σ" -> "sigma"); variant forms too.
GREEK: dict[str, str] = {
    **{lower: name for lower, _, name in _GREEK},
    **{upper: name for _, upper, name in _GREEK},
    "ς": "sigma",
    "ϕ": "phi",
    "ϑ": "theta",
    "ϵ": "epsilon",
    "ϱ": "rho",
    "ϖ": "pi",
    "ℓ": "ell",
}

# Spoken in a maths position only (rule in normalize._speak_symbols).
CONTEXT_NAMES: dict[str, str] = {
    ">": "greater than",
    "<": "less than",
    "·": "dot",
    "⋅": "dot",
    "−": "minus",
}

# Blackboard bold: a letter for a letter, so "ℝ3" reads like "R3"; no spaces added.
LETTER_NAMES: dict[str, str] = {"ℝ": "R", "ℕ": "N", "ℤ": "Z", "ℚ": "Q", "ℂ": "C"}

# Every symbol always spoken by name (glued to a letter or digit, it is separated by spaces).
SYMBOL_NAMES: dict[str, str] = {**RELATIONS, **SETS_AND_LOGIC, **OPERATORS, **GREEK}

# Variation selectors U+FE00-U+FE0F ride on "∫" and "(" in PDF-extracted text; removed.
VARIATION_SELECTORS = frozenset(chr(c) for c in range(0xFE00, 0xFE10))
