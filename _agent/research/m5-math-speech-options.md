# M5 survey: spoken English for PDF mathematics (ING-3, ING-6, ING-7)

Evidence: `_agent/results/607_math_speech_licences.md` (every URL and quoted licence is there; fetched 2026-10-17, summarised by the fetch tool, so verdicts are as reliable as package metadata). "Unverified" = not read or not stated.

## 1. Licence verdicts (candidate and required runtime deps)

| Candidate | Verdict | Basis |
|---|---|---|
| (a) speech-rule-engine (npm) | ALLOWED (Apache-2.0). Needs Node. Deps commander, @xmldom/xmldom, wicked-good-xpath: licences unverified (commonly MIT/BSD-style, not read). | https://registry.npmjs.org/speech-rule-engine/latest ; https://raw.githubusercontent.com/Speech-Rule-Engine/speech-rule-engine/master/LICENSE |
| (b) MathCAT (Rust) | ALLOWED (MIT). Rust crate deps unverified one by one. Python binding MathCATForPython: MIT, but no PyPI package found (libmathcat-py 404), built for NVDA via scons; integration cost is high. | https://raw.githubusercontent.com/NSoiffer/MathCAT/main/LICENSE ; https://github.com/NSoiffer/MathCATForPython |
| (c) pix2tex | Code ALLOWED (MIT). Weights: release notes reportedly say CC BY-NC-SA -> EXCLUDED if confirmed (second-hand, unverified wording). Deps torch/transformers/timm/albumentations licences unverified. | https://pypi.org/pypi/pix2tex/json ; https://github.com/lukas-blecher/LaTeX-OCR/releases |
| (d) Nougat | Code MIT, weights "CC-BY-NC" -> EXCLUDED. | https://raw.githubusercontent.com/facebookresearch/nougat/main/README.md |
| (e) UniMERNet | Code Apache-2.0; weights licence not stated (unverified). Pix2Text: package MIT, but requires `doclayout-yolo<0.1`, which is AGPL-3.0 -> EXCLUDED as a transitive import (PyMuPDF is also a core dep; its AGPL status is unverified here). The Pix2Text MFR weights alone are MIT (https://huggingface.co/breezedeus/pix2text-mfr-1.5) and could be run through plain transformers/ONNX without the pix2text package. | https://raw.githubusercontent.com/opendatalab/UniMERNet/main/README.md ; https://pypi.org/pypi/pix2text/json ; https://pypi.org/pypi/doclayout-yolo/json |
| (f) pylatexenc | ALLOWED (MIT, no deps). Parses LaTeX to nodes / unicode text; does not speak. | https://pypi.org/pypi/pylatexenc/json |
| (g) latex2mathml | ALLOWED (MIT, no deps). LaTeX -> MathML only. | https://pypi.org/pypi/latex2mathml/json |
| (h) others | `latext` 0.0.7 MIT, no deps, alpha, symbol substitution only (https://pypi.org/pypi/latext/json). `accessible-math-reader` 0.4.1 MIT, LaTeX/MathML -> speech, deps gtts (online Google TTS, unwanted) and lxml; no Node, espeak not mentioned (https://pypi.org/pypi/accessible-math-reader/json). `latex-to-speech` (npm) wraps MathJax + SRE, Node, licence unverified. No `latex2speech`/`mathspeak` PyPI package found. | 607 |

## 2. Image-to-markup versus markup-to-speech

| Candidate | Input -> output | Weights |
|---|---|---|
| pix2tex | equation image -> LaTeX | auto-downloaded checkpoints (size not stated); reportedly CC BY-NC-SA |
| Nougat | page image -> Markdown/LaTeX | base/small; CC-BY-NC (excluded) |
| UniMERNet | equation image -> LaTeX | tiny 441MB, small 773MB, base 1.3GB (README); licence unstated |
| Pix2Text MFR | equation image -> LaTeX | MIT weights, size unstated |
| latex2mathml | LaTeX -> MathML | none |
| pylatexenc | LaTeX -> parsed nodes / unicode | none |
| SRE | MathML (LaTeX via CLI `-t` for some locales) -> speech | none (rule files shipped) |
| MathCAT | MathML -> speech (15 languages) | none (rules shipped) |
| latext, accessible-math-reader | LaTeX (and MathML) -> speech | none |

The pipeline has glyph text, not images, so image OCR is only needed for scanned PDFs or glyph-poor math.

## 3. Dependency-free rule approach (viable for simple cases)

| Can express | Cannot express reliably |
|---|---|
| Greek letters, operators, relations, set/logic symbols via a Unicode-to-words table (same pattern as the degree-sign rule in normalize.py) | Operator precedence and grouping without explicit brackets |
| Sub/superscripts from existing span flags ("x sub i", "x squared", "x to the n") | Nested scripts, multi-level scripts |
| Simple fractions from stacked bboxes ("a over b", or "the fraction a over b, end fraction" when long) | Radicals, big operators with limits (sum, integral bounds), matrices, multi-line alignment, stretchy CMEX pieces |
| Inline math already joined into its sentence (stage 3) | Disambiguating "x(y+z)" function versus product; full ClearSpeak-quality phrasing |

Estimate (unverified, no run): covers most inline math in typical prose papers; display equations with fractions of fractions or sums need structure.

## 4. Promising full pipelines (all sizes/speeds are README claims or absent; none run)

1. Rule table + bbox structure -> own small tree -> English. No download, CPU trivially fast (unverified).
2. Glyph/bbox structure -> LaTeX/MathML builder (own code, `latex2mathml` optional) -> MathCAT or SRE. MathCAT: Rust, no model, no perf claim found. SRE: Node subprocess, no perf claim found. Rules shipped, so no model download (unverified size of package).
3. Image OCR (UniMERNet tiny 441MB or Pix2Text MFR MIT weights) -> LaTeX -> latex2mathml -> SRE/MathCAT, for scanned PDFs only. No CPU latency claim in either README (unverified; under 2 s per equation not established). UniMERNet weights licence must be checked first.

## 5. Reading conventions

SRE implements domains `mathspeak` (MathSpeak, with brief/sbrief styles) and `clearspeak` (preferences joined by `:`) (README, URL in 607). MathCAT supports many languages; the pages I could read did not name ClearSpeak or MathSpeak and the docs page 404'd (unverified; MathCAT's own docs mention ClearSpeak and SimpleSpeak from my background knowledge, not read). No docs page I fetched shows a reading of x_i^2/(2 sigma^2); that example is NOT available from sources read. Do not assert one; the supervisor can get it from a 5-minute local SRE run.

## Recommendation

Rank by licence clarity, CPU, PDF glyph input. 1) Own rule engine over pdfplumber glyphs (nothing to license, CPU-only, takes glyph input directly) for M5; it fits normalize.py and the char_map. 2) Optional later layer: emit MathML from the glyph structure and speak it with MathCAT (MIT, Rust, no model) or SRE (Apache-2.0, needs Node subprocess) for display equations; MathCAT is lighter to ship if a Python wrapper can be built, but none is published. 3) Image OCR only for scanned PDFs, with Pix2Text MFR (MIT weights, run without the AGPL-tainted pix2text package) or UniMERNet after confirming weight licence. Exclude Nougat (CC-BY-NC weights), pix2tex weights (reported CC BY-NC-SA) and the pix2text package (AGPL doclayout-yolo).
