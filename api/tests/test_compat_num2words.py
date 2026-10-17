"""D15 licence shim: our own num2words replaces the LGPL distribution for misaki (SYN-4)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys

import pytest

from hearnarro.synthesis import compat
from hearnarro.synthesis.compat.num2words import num2words


@pytest.mark.parametrize(
    ("args", "kwargs", "expected"),
    [
        ((0,), {}, "zero"),
        ((21,), {}, "twenty-one"),
        ((123,), {}, "one hundred and twenty-three"),
        ((1_000_000,), {}, "one million"),
        ((-5,), {}, "minus five"),
        ((1,), {"to": "ordinal"}, "first"),
        ((21,), {"to": "ordinal"}, "twenty-first"),
        ((1984,), {"to": "year"}, "nineteen eighty-four"),
        ((1905,), {"to": "year"}, "nineteen oh five"),
        ((1900,), {"to": "year"}, "nineteen hundred"),
        ((2005,), {"to": "year"}, "two thousand and five"),
        ((2010,), {"to": "year"}, "twenty ten"),
        ((3.2,), {}, "three point two"),
        ((0.05,), {}, "zero point zero five"),
        ((7.0,), {}, "seven"),
    ],
)
def test_syn4_compat_num2words_english(args: tuple, kwargs: dict, expected: str) -> None:
    assert num2words(*args, **kwargs) == expected


def test_syn4_compat_num2words_rejects_other_languages_and_modes() -> None:
    with pytest.raises(NotImplementedError):
        num2words(3, lang="fr")
    with pytest.raises(NotImplementedError):
        num2words(3, to="currency")


def test_syn4_compat_install_registers_shim_not_lgpl_package() -> None:
    compat.install()
    mod = sys.modules["num2words"]
    assert mod.__name__ == "hearnarro.synthesis.compat.num2words"
    assert mod.num2words(42) == "forty-two"


@pytest.mark.skipif(importlib.util.find_spec("misaki") is None, reason="tts extra not installed")
def test_syn4_compat_misaki_en_imports_without_num2words_distribution() -> None:
    """In a subprocess, so this test process never loads torch/spaCy (keeps timing tests honest)."""
    code = (
        "import importlib.metadata as md\n"
        "try:\n    md.distribution('num2words'); raise SystemExit('LGPL num2words installed')\n"
        "except md.PackageNotFoundError: pass\n"
        "from hearnarro.synthesis import compat; compat.install()\n"
        "from misaki import en\n"
        "print(en.num2words(1984, to='year'))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], check=False, capture_output=True, text=True, timeout=120
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "nineteen eighty-four"
