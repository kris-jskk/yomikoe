"""Shipped academic pronunciation lexicon (TERM-1), consulted before misaki's own lexicon.

``ACADEMIC`` maps a domain (``math``, ``stats``, ``physics``, ``chem``, ``bio``, ``cs``,
``latin_greek``, ``surname``) to entries in the format of ``lexicon_overrides.OVERRIDES``: a
lower-case word to its phonemes in misaki/Kokoro's US alphabet (``ˈ``/``ˌ`` before the stressed
vowel; ``A`` = "ay", ``I`` = "eye", ``O`` = "oh", ``W`` = "ow", ``Y`` = "oy", ``ɹ`` = r,
``ʃ`` = sh, ``ʒ`` = zh, ``ʤ`` = j). Data written by the project; no third-party lexicon.

Precedence in ``KokoroBackend`` (and in ``build_g2p``, which the evals share): a user
respelling (``SynthContext.lexicon``, TERM-2) > ``lexicon_overrides.OVERRIDES`` > ``ACADEMIC``
> misaki's gold lexicon > misaki's general lexicon. ``flat()`` is written into misaki's gold
lexicon first and ``OVERRIDES`` after it, so the hand escape hatch still wins a shared key.

Rule (same as ``OVERRIDES``): an entry is added only where every tier is wrong for the word,
with the EVAL-4 ``term_*`` pair that shows it as the comment (``_agent/results/1000``-``1003``).
A word misaki already says correctly gets no entry even when the pair's hyphenated respelling
scores below 1.0 (the respelling is split into one phoneme token per syllable).
"""

from __future__ import annotations

ACADEMIC: dict[str, dict[str, str]] = {
    "math": {
        "cauchy": "kˈOʃi",  # term_math_04: misaki kˈɔʧi ("CAW-chee")
        "fourier": "fˈʊɹiˌA",  # term_math_12: misaki fˈɔɹiəɹ ("FOR-ee-er")
        "banach": "bˈɑnɑk",  # term_math_13: misaki bˈænək ("BAN-uck")
        "galois": "ɡˌælwˈɑ",  # term_math_14: misaki ɡəlˈYz ("guh-LOYZ")
        "poincaré": "pwˌɑnkɑɹˈA",  # term_math_16: misaki pˈYnkˌɑɹ ("POIN-car")
        "dirichlet": "dˌiɹiklˈA",  # term_math_20, term_stats_16: misaki dˈɪɹɪkəlt
    },
    "stats": {
        "heteroscedastic": "hˌɛtəɹOskədˈæstɪk",  # term_stats_02: misaki hˌɛtəɹəsətsˈɑfɪk
        "homoscedastic": "hˌOmOskədˈæstɪk",  # term_stats_03: misaki hˌɑməsədˈɛstɪkəs
        "heteroskedasticity": "hˌɛtəɹOskˌɛdæstˈɪsəTi",  # term_stats_18: misaki hˌɛtəɹOsɛktəfˈɪsti
        "bonferroni": "bˌɑnfəɹˈOni",  # term_stats_04: misaki bOnfɹˈʌni
        "poisson": "pwˈɑsOn",  # term_stats_08: misaki pˈYzsən
    },
    "physics": {
        "schrödinger": "ʃɹˈOdɪŋəɹ",  # term_physics_04: misaki ʃɹdˈɪŋəɹ (no first vowel)
        "heisenberg": "hˈIzənbˌɜɹɡ",  # term_physics_09: misaki hˈIsənbəɹɡ (s for z)
        "feynman": "fˈInmən",  # term_physics_20: misaki fˈAnmən ("FAIN-mun")
    },
    "chem": {
        "cation": "kˈætˌIən",  # term_chem_11: misaki kˈædˌIən ("CAD-eye-un")
    },
    "bio": {
        "nematode": "nˈɛmətˌOd",  # term_bio_11: misaki nˈimətˌOd ("NEE-muh-tode")
        "escherichia": "ˌɛʃəɹˈɪkiə",  # term_bio_17: misaki ɛskˈɛɹiəʃə
    },
    "cs": {
        "regex": "ɹˈɛʤɛks",  # term_cs_08: misaki ɹˈɛɡɛks (hard g)
        "nginx": "ˈɛnʤɪnˌɛks",  # term_cs_18: misaki ˈɪŋk ("ink")
    },
    "latin_greek": {
        "sui": "sˈui",  # term_latin_greek_06: misaki swˈA ("sway")
    },
    "surname": {
        "nguyen": "wˈɪn",  # term_surname_01, term_citation_15: misaki nujˈɛn
        "schmidhuber": "ʃmˈɪthˌubəɹ",  # term_surname_02: misaki ʃmˈɪfʧəɹd
        "kolmogorov": "kˌOlməɡˈɔɹɔf",  # term_surname_05, term_stats_05: misaki kˈOlməɡˌɔɹəp
        "tversky": "tvˈɛɹski",  # term_surname_06: misaki təɹvsˈɛɹki
        "szegedy": "sˈɛɡədi",  # term_surname_09: misaki ʃˈiʤdi
        "sutskever": "sʊtskˈɛvəɹ",  # term_surname_10: misaki sˈʌtkəvsəɹ
        "hochreiter": "hˈOkɹˌItəɹ",  # term_surname_11: misaki hˈɑkɹˌItəɹ
        "krizhevsky": "kɹɪʒˈɛvski",  # term_surname_12: misaki kɹɪvˈɛskəɹi
        "erdős": "ˈɛɹdˌʌʃ",  # term_surname_13: misaki ˈɜɹdˈɛs
        "grothendieck": "ɡɹˈOtəndˌik",  # term_surname_14: misaki ɡɹˈɑθəndɪkˌi
        "noether": "nˈɜɹtəɹ",  # term_surname_15: misaki nˈOðəɹ
        "leibniz": "lˈIbnɪts",  # term_surname_17: misaki lˈibnɪz
        "huang": "hwˈɑŋ",  # term_surname_18: misaki hwˈæŋ
        "zhang": "ʤˈɑŋ",  # term_surname_19, term_citation_20: misaki ʒˈæŋ
        "xu": "ʃˈu",  # term_surname_20: misaki sˈu
    },
}


def flat() -> dict[str, str]:
    """Every entry of every domain in one table (a word in two domains: the later wins)."""
    out: dict[str, str] = {}
    for entries in ACADEMIC.values():
        out.update(entries)
    return out
