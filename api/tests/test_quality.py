"""Unit tests for the document quality checklist (ING-4, ING-5, ING-6 regressions).

Each check runs on a synthetic list of ``QSeg`` (text, block type).
"""

from __future__ import annotations

from hearnarro.quality import (
    QSeg,
    check_chapter_number_segments,
    check_dangling_hyphens,
    check_duplicate_runs,
    check_empty_text_document,
    check_leader_dots,
    check_ligature_artifacts,
    check_midsentence_breaks,
    check_punctuation_only,
    check_single_letter_segments,
    check_title_filename_like,
    check_toc_leak,
    check_tracked_lines,
    run_checks,
)


def body(*texts: str) -> list[QSeg]:
    return [QSeg(t, "body") for t in texts]


def test_quality_dangling_hyphens() -> None:
    bad = check_dangling_hyphens(body("The inter- national market.", "A well-known fact."))
    assert (bad.count, bad.passed) == (1, False)
    assert bad.examples == ["The inter- national market."]
    assert check_dangling_hyphens(body("A well-known fact.", "Pages 3 - 5.")).passed


def test_quality_ligature_artifacts() -> None:
    bad = check_ligature_artifacts(body("The e!ect of di#erent o$ces."))
    assert (bad.count, bad.passed) == (1, False)
    assert check_ligature_artifacts(body("Wow! amazing", "C# and $5")).passed


def test_quality_single_letter_segments_and_chapter_numbers() -> None:
    segs = [QSeg("W", "heading"), QSeg("e start here.", "body"), QSeg("3", "heading")]
    bad = check_single_letter_segments(segs)
    assert (bad.count, bad.passed) == (1, False)
    info = check_chapter_number_segments(segs)
    assert info.count == 1 and info.threshold is None and info.passed
    assert check_single_letter_segments([QSeg("A", "table")]).passed  # not prose


def test_quality_tracked_lines() -> None:
    bad = check_tracked_lines(body("C H A P T E R one"))
    assert (bad.count, bad.passed) == (1, False)
    assert check_tracked_lines(body("Plan A or B is fine.")).passed


def test_quality_leader_dots() -> None:
    assert check_leader_dots(body("Introduction . . . . 5")).count == 1
    assert check_leader_dots(body("Introduction.......5")).count == 1
    assert check_leader_dots(body("Wait... what?", "Wait . . then")).passed


def test_quality_midsentence_breaks() -> None:
    segs = body("The cat sat on", "the mat.", "It was (mostly) fine.") + body(*["Ok."] * 97)
    bad = check_midsentence_breaks(segs)
    assert bad.count == 1 and bad.value == 0.01 and bad.passed  # ratio 1/100 <= 0.01
    worse = check_midsentence_breaks(segs + body("and then", "(maybe) not."))
    assert worse.count == 2 and not worse.passed
    assert check_midsentence_breaks(body("He said:", "yes.", "Done", "Next.")).count == 0
    # a heading between the two pieces is not a body-body pair
    assert check_midsentence_breaks([QSeg("Intro", "body"), QSeg("x", "heading")]).count == 0
    assert check_midsentence_breaks(body("It went", "“quietly” away.")).count == 1


def test_quality_toc_leak() -> None:
    segs = [QSeg("Contents", "heading")] + body("Introduction 1", "Methods 12", "xiv", "Fine.")
    bad = check_toc_leak(segs)
    assert (bad.count, bad.passed) == (3, False)
    assert check_toc_leak(body("Introduction 1")).passed  # no "Contents" marker
    far = [QSeg("Table of Contents", "heading")] + body(*["Ok."] * 60) + body("Late 5")
    assert check_toc_leak(far).passed


def test_quality_punctuation_only() -> None:
    bad = check_punctuation_only(body("* * *", "—", "Fine."))
    assert (bad.count, bad.passed) == (2, False)
    assert check_punctuation_only(body("1.", "A")).passed


def test_quality_duplicate_runs() -> None:
    bad = check_duplicate_runs(body("The same sentence.", "The same sentence."))
    assert (bad.count, bad.passed) == (1, False)
    assert check_duplicate_runs(body("Short.", "Short.")).passed  # under 12 chars
    heads = [QSeg("Chapter One", "heading")] + body("Text.") + [QSeg("Chapter One", "heading")]
    assert check_duplicate_runs(heads).count == 1
    far = [QSeg("Chapter One", "heading")] + body(*["x."] * 25) + [QSeg("Chapter One", "heading")]
    assert check_duplicate_runs(far).passed


def test_quality_title_filename_like() -> None:
    five = body(*["Ok."] * 5)
    assert not check_title_filename_like("Naval_Book.indd", five).passed
    assert not check_title_filename_like("Report2020", five).passed
    assert check_title_filename_like("The Almanack of Naval Ravikant", five).passed
    assert check_title_filename_like("Short", five[:4]).passed  # fewer than 5 segments


def test_quality_empty_text_document() -> None:
    assert not check_empty_text_document([], max_page_chars=500).passed
    assert check_empty_text_document([], max_page_chars=150).passed
    assert check_empty_text_document(body("Ok."), max_page_chars=500).passed


def test_quality_run_checks_overall() -> None:
    good = run_checks(body(*["A fine sentence."] * 1), title="A Good Title", max_page_chars=300)
    assert good.passed
    names = [c.name for c in good.checks]
    assert len([c for c in good.checks if c.threshold is not None]) == 11
    assert "chapter_number_segments" in names
    bad = run_checks(body("inter- national"), title="A Good Title", max_page_chars=300)
    assert not bad.passed
    assert [c.name for c in bad.checks if not c.passed] == ["dangling_hyphens"]
    assert bad.to_dict()["passed"] is False
