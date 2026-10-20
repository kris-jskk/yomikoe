# PRD: domain notation read aloud (M6 "Domain reading")

As of 2026-10-19 · Sowmya · Status: **decided 2026-10-19**, scheduled as milestone **M6 "Domain reading"** (after M5's gate passes; Classroom view renumbered M7, Sources and formats M8 in `docs/PRD.md`). The user accepted every recommendation of the proposal on 2026-10-19; they are recorded in "Decisions (2026-10-19)" below. Nothing here is built or tested yet. Companion to `docs/PRD.md`; it extends the M5 MATH and TERM requirements and the reading convention of `_agent/specs/m5-academic-reading.md` §3c. Its design decisions are D45–D51, all confirmed 2026-10-19 and logged in `docs/TECHNICAL_DESIGN.md` ("M6 decisions"); ids up to D44 are taken (`docs/TECHNICAL_DESIGN.md`, `docs/PRD_KINDLE.md`).

Sources for this document: six research notes under `_agent/research/domain-speech/` (`chemistry.md`, `physics.md`, `biology.md`, `finance.md`, `history.md`, `cs_stats.md`), each with sections 1–8 (teacher behaviour, notation classes, ambiguities, lexicon, pairs, hooks, sources, open questions), and their probe runs `_agent/results/850_chemistry_probe_today.txt`, `855_physics_probe_today.txt`, `860_biology_probe_today.txt`, `865_finance_probe_today.txt`, `870_history_probe_today.txt`, `875_cs_stats_probe_today.txt`. A row below cites its note as `<note>.md §2.x`. Wordings the notes mark "proposed" are not sourced; this PRD does not promote them.

## Overview

M5 teaches the narrator to read mathematics as a teacher would (MATH-1 to MATH-6, the §3c convention). Students outside mathematics meet a second layer of notation that is not maths and that the normalizer does not know: `$4.2bn`, `SO42−`, `Trp53-/-`, `Henry VIII`, `t(23) = 2.14, p < .05`, `9.8 m/s²`. Silent reading decodes these from typography; a listener hears whatever symbol soup reaches the voice. This PRD specifies "domain notation read aloud": per-field reading rules on the same engine, with the same §3c principles (lower case, one wording per symbol and role, numbers stay digits, punctuation is prosody only).

**The finding.** A teacher reads the role, not the glyph: a unit as one phrase with "per" ("meters per second squared"), a formula letter by letter with counts ("h 2 o"), an amount with its magnitude and currency last ("4.2 billion dollars"), a ruler's numeral as an ordinal ("henry the eighth"), a test statistic with its degrees of freedom ("t with 23 degrees of freedom"), and Latin shorthand as its meaning ("three times a day", "circa", "pages"). Today's `normalize()` does none of this outside the M5 symbol table: 3 of 90 probe strings come out right.

| Domain | Probe file | Correct | Wrong | Symbol leaked | Of |
| --- | --- | --- | --- | --- | --- |
| Chemistry | `_agent/results/850_chemistry_probe_today.txt` | 0 | 6 | 9 | 15 |
| Physics | `_agent/results/855_physics_probe_today.txt` | 1 | 7 (also leaked) | 7 | 15 |
| Biology and medicine | `_agent/results/860_biology_probe_today.txt` | 0 | 9 | 6 | 15 |
| Finance and economics | `_agent/results/865_finance_probe_today.txt` | 1 | 7 | 7 | 15 |
| History, humanities, law | `_agent/results/870_history_probe_today.txt` | 0 | 5 | 10 | 15 |
| Computer science and statistics | `_agent/results/875_cs_stats_probe_today.txt` | 1 | 4 | 10 | 15 |
| **Total** | | **3** | **38** | **49** | **90** |

Counts are the tally lines and per-line verdicts in each file (physics records 7 lines as "wrong + symbol leaked", counted here under Wrong). The probes run the normalizer only; how the voice renders a leaked token is unverified except for the finance tokens run through misaki G2P (`_agent/results/866_finance_misaki_g2p.txt`).

**Why a separate PRD.** The main PRD names domains only inside TERM-1 (lexicon categories) and MATH-3 (units and chemical formulas). The six notes add about 70 notation classes, a profile extension (a field flag beside the ING-11 class), per-document reading settings, data tables shared across fields (element symbols, units, currencies), an eval suite and about 50 open questions. That was a scope decision for the user, not a row in M5; the user placed it as its own milestone, M6, on 2026-10-19.

## Goals, non-goals and success metrics

**Goals**

- A student in any of the six fields hears every notation class of the "Reading conventions by domain" section as words, with no raw symbol reaching the voice (DOM-1 to DOM-21).
- Shared notation (units, scientific notation, ranges, uncertainty, statistics reporting) has one grammar used by every field (DOM-1 to DOM-6, DOM-13).
- Field-dependent readings are switched by a detected and overridable document field (DOM-22, D45), never guessed per word when the document can decide.
- Every rule is measured by an eval suite over raw → spoken pairs (DOM-27).

**Non-goals**

- **No LLM rewriting** of text for speech, at ingestion or playback. Rules and tables only (the evals rule's "no LLM-as-judge" extends to production).
- **No semantic paraphrase of equations**: `F = ma` stays "f equals m a"; quantity names only under an opt-in setting and only when the document defines them (DOM-23, physics.md §2.10).
- **No new TTS model** and no change to `TTSBackend`'s signature in the first phases; the IPA-to-phonemes idea (history.md §2.10) is an open question, not a goal.
- No common-name substitution (`CH4` is never read "methane" unless written so), no ticker-to-company mapping, no historical spelling modernisation.
- No recovery of notation that extraction destroyed beyond what font-size runs prove (see risks).

**Success metrics**

| Metric | Target | How measured |
| --- | --- | --- |
| EVAL-11 domain speech, per domain | ≥ 0.95 mean word-sequence score per domain once that domain's phase lands; ≥ 0.90 for every class with ≥ 3 pairs | EVAL-11 record, same scorer as EVAL-10 (D14-style, lower-cased, punctuation stripped) |
| Probe strings | ≥ 13 of 15 correct per domain after its phase (from 0–1 today) | Re-run of the six probe scripts, saved under `_agent/results/` |
| No regressions | EVAL-1 to EVAL-10 tier 0 show no unexplained D33 regression | `python -m hearnarro.evals compare` |
| Leak check | 0 raw symbols outside the allowed set in EVAL-11 output | The convention checker (`api/scripts/check_math_convention.py`) extended to EVAL-11 |

## Users and use cases

| Student | Notation that matters most (note §1) | What they do |
| --- | --- | --- |
| Chemistry | formulas and counts (`C6H12O6`), charges (`SO4 2−`), reaction arrows and states | Listen to a lab manual or an organic paper and follow which letters form one element and where a reaction side ends |
| Physics and engineering | units with prefixes and powers, scientific notation, vector and quantum decorations | Listen to a problem set where the unit says what the number is |
| Biology and medicine | gene symbols and genotypes, lab units, clinical shorthand (`PO t.i.d.`) | Listen to a methods section or a drug chart and hear doses and frequencies as meaning |
| Finance and economics | currency with magnitude, percentage points versus basis points, fiscal periods | Listen to an annual report or an econometrics paper with regression tables |
| History, humanities, law | regnal numerals, eras and circa, citation apparatus, case names and sections | Listen to a monograph whose footnotes cite folios, Herodotus and the U.S. Code |
| Computer science and statistics | asymptotic bounds, APA test reporting, numeric literals and data units | Listen to a systems or ML paper and its results tables |

## Functional requirements

Requirement family `DOM-n`, new on 2026-10-19. No MATH, TERM, ING or EVAL id is reused or renumbered; EVAL-11 is the next free eval id (EVAL-10 is the last in `docs/PRD.md`). Examples are raw → spoken under the §3c conventions; "Field" names the profile field that gates a row (D45), "all" means it runs in every document.

**Shared notation grammar**

| ID | Pri | Field | Requirement | From |
| --- | --- | --- | --- | --- |
| DOM-1 | P0 | all | Unit expressions after a number are one phrase: prefix + unit word, US spelling, plural unless the value is 1; product as a space, quotient as "per" before each denominator unit, `²`/`³` as "square"/"cubic" before a numerator length and "squared"/"cubed" after a denominator unit, negative power as "per"; micro sign and Greek mu, ohm sign and capital omega both accepted. `9.8 m/s²` → "9.8 meters per second squared"; `J mol⁻¹ K⁻¹` → "joules per mole kelvin" | physics.md §2.1, chemistry.md §2.7, biology.md §2.6, cs_stats.md §2.3 |
| DOM-2 | P0 | all | Unit or variable, magnitude or unit: a letter is a unit only directly after a number (upright when font runs exist, not followed by `=` or `(`); `M` after a number is "molar", after a currency symbol "million"; `k` after a currency or before a noun is "thousand"; `B` is "bytes" after a data prefix, "billion" for counts; `b` is "bits". `V = 5 V` → "v equals 5 volts"; `$5M` → "5 million dollars" | physics.md §2.2, chemistry.md §3, finance.md §3, cs_stats.md §2.2–2.3 |
| DOM-3 | P0 | all | Scientific notation: `a × 10^n`, `a·10^n`, `a x 10^n` and a flattened `× 10-19` read "a times 10 to the n"; E-notation per decision 6; `~` or `≈` with no left operand before a number reads "about". `1.6 × 10-19 C` → "1.6 times 10 to the minus 19 coulombs"; `~10⁻¹⁹ J` → "about 10 to the minus 19 joules" | physics.md §2.3, cs_stats.md §2.2, biology.md §2.6 |
| DOM-4 | P0 | all | Ranges, ratios, uncertainty: a dash between numbers is "to" and an abbreviated end year is completed; digit-colon-digit is "to" unless a scripture or edition reference claims it (DOM-17); `±` "plus or minus"; concise `1.2345(6)` expands to the `±` form; `s.f.`, `d.p.` expand. `2019–24` → "2019 to 2024"; `1.2345(6) kg` → "1.2345 plus or minus 0.0006 kilograms" | physics.md §2.4, finance.md §2.9, history.md §2.2, biology.md §2.6 |
| DOM-5 | P1 | all | Flattened scripts: a superscript or subscript extracted onto the baseline is restored only when ING-3 font-size runs show it or the token is unambiguous by table (`SO42−` by the polyatomic-ion table, `m s-2` by the unit grammar, `× 10` + hyphen-digits); otherwise left as letters and digits. `SO42−` → "s o 4, 2 minus"; `Ksp` → per decision 9 | chemistry.md §2.2, biology.md §3, cs_stats.md §3, physics.md §2.3 |
| DOM-6 | P0 | all | Numbers: digits stay digits (backend `num2words`), with exceptions only as listed in decision 7; a leading-dot decimal reads "point" then digits; a version or dotted standard number reads components with "point"; an IPv4 address with "dot". `p < .05` → "p is less than point 0 5"; `Python 3.11` → "python 3 point 11" | cs_stats.md §2.4, §2.12; chemistry.md §3.10; history.md general rules |

**Per domain**

| ID | Pri | Field | Requirement | From |
| --- | --- | --- | --- | --- |
| DOM-7 | P0 | chemistry (formula detection in all, with a digit, charge or arrow) | Formulas letter by letter with counts, group multipliers after a pause, hydrate dot "dot"; charges after the formula; oxidation-state Roman numerals as digits; nuclides as element name + mass number (118-row element table). `Ca(OH)2` → "c a, o h, 2"; `235U fission` → "uranium 235 fission" | chemistry.md §2.1–2.4 |
| DOM-8 | P1 | chemistry | Reaction arrows as verbs, state symbols as words, `[X]` in a rate law "the concentration of", standard-state `°` "naught", NMR data groups, IUPAC locants (hyphens silent), group abbreviations (`Me` "methyl"), electron configurations "1 s 2". `N2 + 3H2 ⇌ 2NH3` → "n 2 plus 3 h 2 is in equilibrium with 2 n h 3"; `[Ne] 3s1` → "neon core, 3 s 1" | chemistry.md §2.5–2.13 |
| DOM-9 | P1 | physics | Vector and quantum decorations: `×` between vector operands "cross", `∇·` "del dot", `ẍ` "x double dot", upper tensor index "sup", bra/ket, `ħ` "h bar", `†` "dagger", operator `[A, B]` "the commutator of"; nuclear and particle reactions. `∇×B = μ₀J` → "del cross b equals mu sub 0 j"; `⟨φ|ψ⟩` → "bra phi ket psi" | physics.md §2.5–2.8 |
| DOM-10 | P1 | physics | Circuits, angles, astronomy, geoscience: `∠` "angle", sexagesimal `°′″` with compass words, arcseconds in astronomy, `M☉` "solar masses", `Ma`/`Gyr` after a number, two-letter dimensionless numbers by name before a relation. `51°30′N` → "51 degrees 30 minutes north"; `Re = 2000` → "reynolds number equals 2000" | physics.md §2.8, §2.9, §2.11; history.md §2.7 |
| DOM-11 | P0 | biology | Gene and protein symbols (lexicon word or spelled, trailing digits as a number), genotype suffixes as written, `WT`/`KO` expanded; genus initial plus epithet with no sentence break, `spp.` "species"; nucleotide runs spelled, `5′→3′` "5 prime to 3 prime", `kb`/`bp`/`kDa`/`aa`. `Trp53-/-` → "t r p 53 minus minus"; `E. coli K-12` → "e coli k 12" | biology.md §2.1–2.3 |
| DOM-12 | P1 | biology, clinical | HGVS variants (`>` "to" after `c.`/`p.`/`g.`), karyotypes, bands; ions and named enzymes; clinical dose, route and frequency expanded (`q6h` "every 6 hours"), vitals, chart shorthand. `c.524G>A` → "c dot 524 g to a"; `500 mg PO t.i.d.` → "500 milligrams by mouth three times a day" | biology.md §2.4, §2.5, §2.7, §2.9 |
| DOM-13 | P0 | statistics (and biology, finance, cs) | Statistics reporting: `t(df)`, `F(df1, df2)`, `χ²(df)` "with N degrees of freedom"; APA abbreviations expanded in statistics position (abbreviation then `=` and a number, or a column header); `CI` "confidence interval" (dash form "1.2 to 3.4", bracket form "from 1.2 to 3.4", never a citation); `R²` "r squared"; stars per decision 12. `t(23) = 2.14` → "t with 23 degrees of freedom equals 2.14"; `M = 3.2, SD = 1.1` → "mean equals 3.2, standard deviation equals 1.1" | cs_stats.md §2.12–2.13, biology.md §2.8, finance.md §2.6 |
| DOM-14 | P0 | finance (currency rule in all) | Amount, magnitude word, then currency word; ISO codes as currency names; cents; parenthesized amounts in statements and money columns "minus"; `pp` "percentage points", `bp` "basis points", a multiple `22x` "times". `$4.2bn` → "4.2 billion dollars"; `$(0.12)` → "minus 12 cents" | finance.md §2.1–2.2 |
| DOM-15 | P1 | finance | Fiscal periods (`FY` "fiscal", `YoY` "year on year", `TTM`), tenors, ratio names (`P/E` "p e"), `&` in acronyms "and", table marks (`▲` "up", `n/m` "not meaningful"), money headers, month abbreviations. `1H25 sales rose 4% QoQ` → "h 1 25 sales rose 4 percent quarter on quarter"; `S&P 500` → "s and p 500" | finance.md §2.3–2.5, §2.8, §2.9 |
| DOM-16 | P0 | humanities | Regnal numerals as "the" + ordinal word after a ruler name (structural numerals keep today's cardinal rule); eras spelled; `c.`, `fl.`, `r.`, `b.`, `d.` before a year expanded. `Louis XIV's court` → "louis the fourteenth's court"; `Charlemagne (r. 768–814)` → "charlemagne, reigned 768 to 814" | history.md §2.1–2.2 |
| DOM-17 | P1 | humanities, law, classics | Citation apparatus (`pp.` "pages", `fol. 12r` "folio 12 recto", `op. cit.`), classical and scripture references by their levels (book, chapter, line; chapter, verse), legal citations (`v.` by jurisdiction setting, `§` "section", neutral-citation year kept). `Hdt. 7.228` → "herodotus, book 7, chapter 228"; `42 U.S.C. § 1983` → "42 u s c section 1983" | history.md §2.3–2.5 |
| DOM-18 | P2 | humanities, linguistics | £sd money, imperial units, military units and times, editorial marks (`[sic]` aside, ellipsis a pause, `&c.` "et cetera"), Kant/Akademie/TLP references, linguistics `*` "star", `>` "becomes", `<` "from"; IPA spans skipped with a cue per decision 24. `£3 4s 6d` → "3 pounds 4 shillings and 6 pence"; `*kʷ > p` → "star k w becomes p" | history.md §2.7–2.10 |
| DOM-19 | P0 | computing | Asymptotic notation (`O(` "big o of", `Θ(` "big theta of"), complexity classes spelled, hex and binary literals, magnitude suffixes on counts, data units with binary prefixes and rates. `O(n log n)` → "big o of n log n"; `4 KiB` → "4 kibibytes" | cs_stats.md §2.1–2.3 |
| DOM-20 | P1 | computing | Paths, flags and addresses; pseudocode (`←` "gets", `for i ← 1 to n` "for i from 1 to n", floor/ceiling); typing judgements (`⊢` "proves", `:` "has type"); grammars (`→` "is", `|` "or"); ML operators (`⊙` "elementwise times", concatenation `∥`); dimensions `×` "by"; code operators in prose; distributions after `∼` by full name. `x ← x + A[i]` → "x gets x plus a of i"; `shape B × T × D` → "shape b by t by d" | cs_stats.md §2.4–2.11, §2.14–2.15 |
| DOM-21 | P2 | finance, computing, statistics | Results and regression tables read row by row ("row label, header value, ...") under a per-document setting: header `↑` "higher is better", standard errors and t statistics from the table note, footnote marks dropped, empty cells per decision 13. `Education 0.042*** (0.011)` → "education 0.042, 3 stars, standard error 0.011"; `Acc. ↑` → "accuracy, higher is better" | cs_stats.md §2.16, finance.md §2.6, §2.8 |

**Profile, lexicon, abbreviations, eval**

| ID | Pri | Field | Requirement | From |
| --- | --- | --- | --- | --- |
| DOM-22 | P0 | all | ING-11 profile gains `fields`: a set of field flags computed at ingestion from token densities (formula tokens and reaction arrows; unit tokens; gene and clinical tokens; currency tokens and parenthesized amounts; regnal, era and citation-apparatus tokens; complexity, code and APA tokens), shown in the library badge and overridable per document; an override re-normalizes without re-ingesting (the existing renormalize path). Rules a note marks unambiguous run in every document. A paper with `CuSO4` and `0.1 M` → fields {chemistry}; a methods section with `q8h`, `PO` → {biology, clinical} | chemistry.md §6, physics.md §3, biology.md §6, finance.md §6, history.md §6, cs_stats.md §3 |
| DOM-23 | P1 | per document | Reading settings stored with the document: `jurisdiction` (us, england_wales, scotland; default us, inferred from a neutral citation shape), `read_quantity_names` (off), `read_tables` (announce or rows; default announce), `quote_marks` ("quote … end quote" around block quotations; off). `R v Smith` with england_wales → "the crown against smith"; `F = ma` with names on and a glossary → "force equals mass times acceleration" | history.md §2.5, §2.8; physics.md §2.10; cs_stats.md §2.16 |
| DOM-24 | P0 | per field | TERM-1 lexicon gains the respellings of each note's §4 (about 240 entries: eponyms, Latin, symbol names, spoken acronyms) under EVAL-4 categories chemistry, physics, biology_medicine, finance_economics, humanities_law, computing_statistics. `Nernst` → NAIRNST; `Dirichlet` → dee-ree-KLAY | all notes §4 |
| DOM-25 | P1 | per field | The TERM-4 expansion table gains per-field rows (`spp.`, `b.i.d.`, `PRN`, `pp.`, `fol.`, `op. cit.`, `s.a.`, `SAAR`, `lr`, `w.h.p.`) and the SYN-4 acronym table gains per-field spoken and spelled overrides that win over the heuristic (FTSE "footsie", SEC and tickers spelled, KRAS "k ras", MAP spelled in statistics). `Streptomyces spp.` → "streptomyces species"; `FTSE 100` → "footsie 100" | finance.md §2.4, chemistry.md §2.9, biology.md §2.1, §2.7, history.md §2.3, cs_stats.md §4 |
| DOM-26 | P1 | all | Sentence segmentation: a dot that ends a known abbreviation (genus initial before a lower-case epithet, `b.i.d.`, `c.`, `fl.`, `pp.`, `et al.`) is not a sentence end. `E. coli was` stays one sentence; `(fl. 731) wrote` stays one sentence | biology.md §2.2, §2.7; history.md general rules |
| DOM-27 | P0 | evals | EVAL-11 "domain speech": `evals/data/domain_speech.jsonl` raw → spoken pairs with `domain` and `class`; scored by the EVAL-10 scorer; aggregates per domain and per class; tier 0. Floors per success metrics. `{"domain": "physics", "raw": "a torque of 12 N·m", "spoken": "a torque of 12 newton meters"}`; `{"domain": "history", "raw": "Hdt. 7.228", ...}` | all notes §5 |

## Shared symbols and cross-domain rules

The six notes reuse §3c wherever they can, and disagree where a symbol has a different role in a field. The resolution is D46 (confirmed 2026-10-19): **one wording per symbol per role**, the role decided by operand class or span type (the §3c bar `|` already has three such readings). Each conflict below lists every alternative and the note that proposed it; a row that names a decision number is settled in "Decisions (2026-10-19)".

| Symbol or rule | Readings and who proposed them | Resolution |
| --- | --- | --- |
| `→` | §3c "approaches" (limits) and "to" (after a colon); "reacts to form" between chemical formulas (chemistry.md §2.5, sourced MathCAT); "yields" between nuclides or particles (physics.md §2.7, wants one word shared with chemistry, physics.md §8.3); "to" for `5′→3′` (biology.md §2.3) and `n→π*` (chemistry.md §2.11); "is" in a grammar production (cs_stats.md §2.7); "to" between types (cs_stats.md §2.6) | Role-keyed (D46). Chemical formula sides: "reacts to form". Nuclide or particle sides: decision 3, "yields". Others as listed. "goes to" stays banned |
| `/` | §3c "over"; "per" inside a unit expression (physics.md §2.1, biology.md §2.6, chemistry.md §2.7, NIST); "over" for blood pressure (biology.md §2.7); letters for ratio names `P/E` "p e" and "to" in `EV/EBITDA` (finance.md §2.2); silent in genotypes `-/-` and strains `C57BL/6J` (biology.md §2.1–2.2); "shillings and pence" with a currency cue, a pause in Kant `A51/B75` (history.md §2.7, §2.9); "slash" in paths, CIDR, `ViT-B/16` (cs_stats.md §2.4, §2.10); `y/y`, `n/m`, `o/n` expanded whole (finance.md, biology.md) | Role-keyed. Unit expression → "per" (DOM-1, decision 4 confirms); maths → "over"; the rest by token tables. Order: whole-token tables first, then unit grammar, then §3c |
| `~` `∼` | §3c "distributed as"; "about" before a number with no left operand (physics.md §2.3, physics.md §8.2; cs_stats.md §3 agrees); "home" at the start of a path (cs_stats.md §2.4); "bitwise not" in code (cs_stats.md §2.11) | Role-keyed; decision 2 confirms "about" |
| `Δ` `∆` | §3c "capital delta" (kept by chemistry.md §8.5 and finance.md §8.3, both noting teachers say "delta h" or "change in"); "heat" above a reaction arrow (chemistry.md §2.5); "delta" in `ΔF508` (biology.md §2.4) | Decision 10: §3c everywhere except the arrow condition and the HGVS idiom |
| `Ω` | §3c "capital omega"; "ohms" after a number, "kilohms" with a prefix (physics.md §2.1); "big omega of" before an asymptotic argument (cs_stats.md §2.1) | Role-keyed, no conflict left: unit position, asymptotic position, otherwise §3c |
| `×` `x` | §3c "times"; "cross" between vector operands (physics.md §2.5); "by" for dimensions and designs (cs_stats.md §2.9, §2.13); "times g" for `×g` (biology.md §2.6); "times" for a multiple `22x` (finance.md §2.2); an extracted hydrate dot (chemistry.md §2.1) | Role-keyed. Note "2 by 2 design" (cs) versus a teacher's "2 times 2" never arises: "by" only after a dimension noun or inside `ℝ^{…}` |
| `°` and subscript 0 | ING-6 "degrees"; "naught" after a thermodynamic quantity (chemistry.md §2.6); `ε₀` "epsilon sub 0" with classroom "naught" as an alternative (physics.md §8.9); `R0` "r nought" (biology.md §2.10; lexicon spells it "nought", chemistry.md §4 spells "naught") | Decision 9; one spelling "naught" in the lexicon |
| Flattened subscript labels | `Ksp`, `Ka` "k s p", "k a" without "sub" (chemistry.md §2.6, §8.2); `Ne`, `Fst` "n sub e", "f sub s t" (biology.md §2.10); `kBT` "k sub b t" (physics.md §2.8); `log₁₀` "log base 10" (physics.md §2.9) versus §3c "log sub 10"; `log2FC` "log 2 fold change" (biology.md §2.8) | Decision 9 |
| `±` and `+/-` | `±` "plus or minus" everywhere; `+/-` after a gene symbol "plus minus" (biology.md §2.1, §3), but an extracted `±` can arrive as `+/-` | Before a number: `±`; after a gene symbol: genotype |
| `*` | §3c "star"; Kleene star (cs_stats.md §2.7); linguistic "star" (history.md §2.10); significance stars "3 stars" (finance.md §2.6, biology.md §2.8) versus silent (cs_stats.md §2.12, §2.16); footnote marker dropped (finance.md §2.8, cs_stats.md §2.16) | Decision 12 for significance stars |
| `[ ]` | §3c interval; numeric citation (ING-6, ING-11); "the concentration of" (chemistry.md §2.12); complex silent, noble-gas core (chemistry.md §2.11); commutator with operator operands (physics.md §2.6); CI bracket "from a to b" (cs_stats.md §2.13); neutral-citation year kept (history.md §2.5); editorial `[sic]` aside (history.md §2.8); concatenation `[h₁ ∥ h₂]` (cs_stats.md §2.8); array index `A[i]` "a of i" (cs_stats.md §2.5) | Role-keyed by content and field; the ING-11 rule that a bracket starting with 0 is an interval stays |
| `:` between digits | "to" for a ratio (physics.md §2.4, chemistry.md §2.10, biology.md §2.6, finance.md §2.2); "chapter … verse" after a scripture book, "volume … page" after `Ak.` (history.md §2.4, §2.9) | Reference tables first, ratio otherwise |
| `′` `″` | §3c "prime"; "minutes"/"seconds" after a `°` value (physics.md §2.11, history.md §2.7); "arcminutes"/"arcseconds" standalone in astronomy (physics.md §2.11) | Agreed across notes |
| `>` `<` | §3c relations; "to" in an HGVS substitution (biology.md §2.4); "becomes"/"from" between linguistic forms (history.md §2.10) | Role-keyed by token shape |
| `↑` `↓` | "up"/"down" before a figure (finance.md §2.8); "higher/lower is better" in a header (cs_stats.md §2.16); "gas"/"precipitate" after a product (chemistry.md §2.5); "up"/"down" inside a ket (physics.md §2.6) | Role-keyed |
| `⟨ ⟩` | §3c "the inner product of"; "the tuple" for three or more (cs_stats.md §2.6); "the expectation value of" for one argument (physics.md §2.6) | Decision 18 |
| `p.`, `c.`, `n.` | "page", "circa", "note" (history.md §2.2–2.3); HGVS "p dot", "c dot", "n dot" when glued to a position (biology.md §2.4); `c.` "chapter" in a statute (history.md §2.5) | Glued to a position or base → HGVS; before a year → circa; before a number with a space → page or note |
| Roman numerals | ordinal word after a ruler (history.md §2.1); cardinal word after a structural word (today's rule, history.md §2.1); digit in an oxidation state `Fe(III)` "f e 3" (chemistry.md §2.3) and cranial nerves `CN VII` "cranial nerve 7" (biology.md §2.9); `IV` as a route "i v" (biology.md §2.7) | Decision 7 for words versus digits; route `IV` only after a dose |
| Units grammar | Agreed: prefix + unit word, "per", "squared/cubed", US spelling. Differences: plural rule (§3c "unless 1" versus NIST "only above 1", physics.md §8.1); attributive singular "a 10 kilohm resistor" (physics.md §5 note, biology.md §8.7); `M` "molar" not pluralised (biology.md §2.6, chemistry.md §2.7); "kilo electronvolts" as two words (physics.md §2.1) versus one-word prefixes elsewhere | Decision 5 |
| Numbers | Digits stay digits (all). Exceptions proposed: ordinal words for rulers, "the twenties", "oh six hundred hours" (history.md §8.1); mass-number grouping "two thirty-eight" (physics.md §8.7); E-notation "3 e minus 4" (cs_stats.md §2.2) versus "6.022 times 10 to the 23" (physics.md §2.3) for the same shape; leading-dot "point 0 5" (cs_stats.md §8.8); long decimals read digit by digit today (chemistry.md §8.8); years "nineteen fourteen" unprobed (history.md §8.2) | Decisions 6, 7, 8 |
| Abbreviation reading | Agreed: SYN-4 decides spoken versus spelled, per-field overrides win. Differences: `SD` spelled "s d" (biology.md §2.8) versus "standard deviation" in statistics position (cs_stats.md §2.13); `SE` "standard errors" (finance.md §2.6); `ibid.` word (history.md §8.3) versus TERM-4 expansion; `BC` kept spelled (history.md §2.2); model sizes "7 b" or "7 billion" (cs_stats.md §8.3) | Decisions 11, 19 |
| Profile field | A `chemistry` class or a toggle (chemistry.md §8.7); engineering, quantum and astronomy vocabulary flags (physics.md §3); `bio`/`clinical` (biology.md §8.6); `finance` (finance.md §8.7); `field` set history, law, classics, linguistics plus `jurisdiction` (history.md §8.7); `stats` flag or a sentence rule (cs_stats.md §8.7) | D45: one multi-valued `fields` set beside the class (DOM-22); decision 1 |

## Reading conventions by domain

Condensed from each note's §2 (at most 15 rows per domain); the note has the full wording tables, detection artefacts and sources. Confidence is the note's own label.

**Chemistry** (`chemistry.md`)

| Class | Detection | Wording | Confidence |
| --- | --- | --- | --- |
| Formula | element symbols + digits, not a word | `C6H12O6` "c 6 h 12 o 6" | sourced |
| Group, hydrate | `( )` multiplier, `·` | `Ca(OH)2` "c a, o h, 2"; `·5H2O` "dot 5 h 2 o" | proposed |
| Charge | trailing `+ − 2+`, fused `SO42−` | "s o 4, 2 minus" | proposed (pause sourced) |
| Oxidation state | Roman after element | `iron(III)` "iron 3" | proposed |
| Isotope | mass number before symbol | `14C` "carbon 14" | proposed order |
| Reaction arrow | `→ ⇌ ←` between formulas | "reacts to form", "is in equilibrium with" | sourced |
| State symbol | `(s) (l) (g) (aq)` | "solid", "liquid", "gas", "aqueous" | sourced |
| Thermo quantity | `ΔG°`, `Ksp`, `pKa` | "capital delta g naught", "k s p", "p k a" | proposed |
| Concentration unit | `M`, `mM`, `mol dm−3` | "molar", "millimolar", "moles per cubic decimeter" | sourced |
| Nomenclature | locants, `(R)-`, `tert-` | `2-methylpropan-2-ol` "2 methylpropan 2 ol" | proposed |
| Group abbreviation | `Me Et tBu`, `THF` | "methyl", "tert butyl", "t h f" | proposed |
| NMR data | `δ 7.26 (d, J = 8.0 Hz, 2H)` | "delta 7.26 (doublet, j equals 8.0 hertz, 2 h)" | proposed |
| Configuration | `1s2 2s2 2p6` | "1 s 2, 2 s 2, 2 p 6" | proposed |
| Rate law | `[A]` in an equation | "the concentration of a" | proposed |
| Bond | `C=O`, `C≡N` | "c double bond o" | sourced |

**Physics and engineering** (`physics.md`)

| Class | Detection | Wording | Confidence |
| --- | --- | --- | --- |
| Units | number + unit expression | `kg m⁻³` "kilograms per cubic meter" | sourced |
| Unit vs variable | letter after a number, upright | `T = 300 K` "t equals 300 kelvins" | proposed |
| Scientific notation | `× 10^n`, `e23` | "times 10 to the 23" | proposed |
| Uncertainty | `±`, `1.2345(6)` | "plus or minus 0.0006" | meaning sourced |
| Vector ops | `×` with vector operands, `∇·` | "cross", "del dot" | proposed |
| Time derivative | `ẍ` | "x double dot" | proposed |
| Tensor index | upper Greek index | "sup mu" | proposed |
| Dirac | `⟨φ|ψ⟩`, `|ψ⟩` | "bra phi ket psi", "ket psi" | names sourced |
| Operators | `ħ`, `A†`, `[x̂, p̂]` | "h bar", "a dagger", "the commutator of" | proposed |
| Nuclide, particle | `²³⁸U`, `e⁻`, `→` | "uranium 238", "e minus", "yields" | nuclide sourced |
| Constants | `k_B`, `ε₀` | "k sub b", "epsilon sub 0" | §3c |
| Dimensionless | `Re = `, `Ma >` | "reynolds number", "mach number" | proposed |
| Circuits | `kΩ`, `∠30°`, `dBm` | "kilohms", "angle 30 degrees", "d b m" | units sourced |
| Angles, astronomy | `51°30′N`, `0.75″`, `M☉` | "minutes north", "arcseconds", "solar masses" | angles sourced |
| Geoscience | `66 Ma`, `4.5 Gyr` | "million years ago", "billion years" | proposed |

**Biology and medicine** (`biology.md`)

| Class | Detection | Wording | Confidence |
| --- | --- | --- | --- |
| Gene, protein | capitals + digits, `p53` | `CDK4` "c d k 4", `SOX2` "sox 2" | wording proposed |
| Genotype | `-/-`, `+/-`, `fl/fl` | "minus minus", "plus minus", "flox flox" | proposed |
| Taxon | genus initial + epithet, `spp.` | "e coli", "species" | proposed |
| Strain, cell line | `C57BL/6J`, `HEK293T` | "c 57 b l 6 j", "h e k 293 t" | proposed |
| Sequence | ACGT runs, `5′`, `kb` | "a c g t …", "5 prime", "kilobases" | proposed |
| HGVS variant | `c.524G>A`, `p.R175H` | "c dot 524 g to a" | syntax sourced |
| Karyotype, band | `47,XX,+21`, `17p13.1` | "47, x x, plus 21", "17 p 13.1" | proposed |
| Molecule | `β2-`, `TNF-α`, `Ca2+`, `cAMP` | "beta 2", "t n f alpha", "c a 2 plus", "cyclic a m p" | proposed |
| Lab units | `µg/mL`, `mM`, `×g`, `rpm` | "micrograms per milliliter", "times g", "r p m" | units sourced |
| Lab shorthand | `o/n`, `RT`, `P3`, `1:1000` | "overnight", "room temperature", "passage 3", "1 to 1000" | proposed |
| Clinical | `PO t.i.d.`, `q6h`, `PRN` | "by mouth three times a day", "every 6 hours", "as needed" | meanings sourced |
| Vitals | `BP 120/80 mmHg`, `HR 72 bpm` | "b p 120 over 80 millimeters of mercury" | proposed |
| Stats report | `OR`, `CI`, `**`, `log2FC` | "odds ratio", "confidence interval", "2 stars", "log 2 fold change" | proposed |
| Anatomy | Latin terms, `CN VII` | lexicon; "cranial nerve 7" | proposed |
| Popgen | `Ne`, `Fst`, `R0` | "n sub e", "f sub s t", "r nought" | §3c, `R0` proposed |

**Finance and economics** (`finance.md`)

| Class | Detection | Wording | Confidence |
| --- | --- | --- | --- |
| Currency + magnitude | symbol or ISO code, `bn`, `m`, `mm` | `€3.5m` "3.5 million euros" | order sourced |
| Cents | `$4.20`, `$0.12` | "4 dollars and 20 cents", "12 cents" | sourced |
| Negative amount | `(1,234)`, `$(0.12)` | "minus 1,234" | parentheses sourced |
| Points | `pp`, `bp` | "percentage points", "basis points" | sourced |
| Multiple | `22x`, `3.5x EBITDA` | "22 times" | proposed |
| Ratio name | `P/E`, `EV/EBITDA` | "p e", "e v to ebitda" | proposed |
| Period | `Q3 FY2024`, `1H25` | "q 3 fiscal 2024", "h 1 25" | proposed |
| Change period | `YoY`, `QoQ`, `TTM` | "year on year", "quarter on quarter", "trailing 12 months" | proposed |
| Acronym | EBITDA, FTSE, SEC, tickers | "ebitda", "footsie", "s e c", "a a p l" | FTSE, REIT, EBITDA sourced |
| `&` compounds | `S&P`, `M&A` | "s and p", "m and a" | proposed |
| Economics | `s.a.`, `SAAR`, `(2015=100)` | "seasonally adjusted", "2015 equals 100" | proposed |
| Regression | `0.042*** (0.011)`, `Adj. R²` | "0.042, 3 stars, standard error 0.011" | meaning sourced |
| Formula | `PV`, `CF_t`, `N(d₁)` | "p v", "c f sub t", "n of d sub 1" | §3c |
| Table marks | `▲`, `n/m`, lone dash | "up", "not meaningful", "nil" | proposed |
| Year range | `2019–24` | "2019 to 2024" | proposed |

**History, humanities and law** (`history.md`)

| Class | Detection | Wording | Confidence |
| --- | --- | --- | --- |
| Regnal | Roman after a ruler name | `Henry VIII` "henry the eighth" | sourced |
| Structural Roman | after chapter, act, vol. | "volume three", "chapter four" | today's rule |
| Era | `BC`, `BCE`, `AD`, `AH` | "480 b c" | proposed |
| Approximation | `c.`, `fl.`, `r.`, `b.`, `d.` before a year | "circa", "flourished", "reigned", "born", "died" | proposed |
| Decade | `'20s` | "the twenties" | proposed |
| Apparatus | `ibid.`, `op. cit.`, `pp.`, `n.`, `ff.` | "ibid", "in the work cited", "pages", "note", "and following" | proposed |
| Manuscript | `fol. 12r`, `Add. MS` | "folio 12 recto", "additional manuscript" | proposed |
| Classical ref | `Hom. Il. 1.1–5`, `Rep. 514a` | "homer, iliad, book 1, lines 1 to 5", "republic 514 a" | structure sourced |
| Scripture ref | `John 3:16`, `1 Cor 13:4` | "john, chapter 3, verse 16", "first corinthians" | sourced |
| Case name | `v.` between parties | "versus" (US), "and", "the crown against" (E&W) | sourced |
| Statute | `§`, `§§`, `¶`, `Art. 3(2)`, `s 3(2)` | "section", "sections", "paragraph", "article 3, paragraph 2" | `§` sourced |
| Old money | `£3 4s 6d`, `10/-` | "3 pounds 4 shillings and 6 pence", "10 shillings" | sourced |
| Military | `3rd Bn`, `0600` | "3rd battalion", "oh six hundred hours" | time sourced |
| Editorial | `[sic]`, `[...]`, `&c.` | "sic" aside, a pause, "et cetera" | proposed |
| Linguistics | `*form`, `>`, `<`, IPA | "star", "becomes", "from"; IPA open | proposed |

**Computer science and statistics** (`cs_stats.md`)

| Class | Detection | Wording | Confidence |
| --- | --- | --- | --- |
| Asymptotic | `O(`, `Θ(`, `Ω(`, `o(` | "big o of", "big theta of", "little o of" | "big o" sourced |
| Complexity class | `NP-hard`, `PSPACE`, `#P` | "n p hard", "p space", "sharp p" | proposed |
| Literal | `0x1F`, `0b1010`, `3e-4`, `175B` | "hex 1 f", "binary 1 0 1 0", open, "175 billion" | proposed |
| Data units | `KiB`, `Gbps`, `MB/s` | "kibibytes", "gigabits per second" | sourced |
| Version, address | `v2.3.1`, `192.168.0.1:8080` | "version 2 point 3 point 1", "… dot 1 port 8080" | proposed |
| Path, flag | `/usr/bin`, `--verbose` | "slash usr slash bin", "dash dash verbose" | proposed |
| Pseudocode | `←`, `for i ← 1 to n`, `⌊x⌋` | "gets", "for i from 1 to n", "the floor of" | "gets" sourced |
| Logic, types | `⊢`, `⊨`, `::`, `λx.` | "proves", "models", "has type", "lambda x dot" | proposed |
| Grammar | `::=`, production `→`, `|` | "is", "or" | proposed |
| ML operators | `⊙`, `⊕`, `[a ∥ b]` | "elementwise times", "o plus", "concatenated with" | proposed |
| Shapes | `B × T × D`, `ℝ^{d×k}` | "b by t by d", "r to the d by k" | proposed |
| Code in prose | `!=`, `&&`, `+=`, `Ctrl+C` | "not equals", "and", "plus equals", "control c" | proposed |
| Test report | `t(23)`, `F(2, 45)`, `χ²(1)`, `.05` | "t with 23 degrees of freedom", "point 0 5" | shapes sourced |
| Descriptives | `M`, `SD`, `Mdn`, `ηp²`, `95% CI [a, b]` | "mean", "standard deviation", "partial eta squared", "from a to b" | meanings sourced |
| Distributions | `∼ Bin(n, p)`, `i.i.d.`, `MLE` | "distributed as binomial of", "i i d", "m l e" | proposed |

## Architecture and stack

All rules hook into existing stages; nothing changes in synthesis, audio delivery (D5) or the player (D10). Per the notes' §6:

| Hook (existing) | What the domain rules add | DOM rows |
| --- | --- | --- |
| ING-6 prose normalizer, `api/hearnarro/ingestion/normalize.py` | A domain pass: units grammar, scientific notation, ranges and uncertainty, numbers, currency and periods, regnal and era rules, citation and reference tables, HGVS and clinical shorthand, numeric literals, versions and paths, statistics reporting | DOM-1 to DOM-4, DOM-6, DOM-7, DOM-11 to DOM-20 |
| MATH-3 symbol table, `_speak_symbols` with `api/hearnarro/ingestion/math_symbols.py` and `api/scripts/math_convention.json` | Role-keyed entries (D46): reaction arrows, bond words, cross, dagger, bra and ket, big O, gets, proves, elementwise times | DOM-8, DOM-9, DOM-19, DOM-20 |
| Mathspeak (MATH-1, MATH-2) | Bracket-as-concentration and commutator under a field; orbital terms; upper tensor indices; dimensions "by" | DOM-8, DOM-9, DOM-20 |
| ING-11 profile (`compute_profile`) | `fields` set (D45) and per-document settings (D51) | DOM-22, DOM-23 |
| SYN-4 acronym table (`acronyms.decide()`, seen in `_agent/results/865_finance_probe_today.txt`) | Per-field spoken and spelled overrides | DOM-25 |
| TERM-1 lexicon, TERM-4 expansion table | Six new lexicon categories; per-field abbreviation rows | DOM-24, DOM-25 |
| Sentence splitting (stage 5) | Abbreviation dots are not sentence ends | DOM-26 |
| ING-3 font runs and table blocks; ING-10 code listings | Superscript restoration; row-by-row tables; pseudocode block detection | DOM-5, DOM-20, DOM-21 |
| Evals (`api/hearnarro/evals/`) | EVAL-11 suite over `domain_speech.jsonl` | DOM-27 |

**Pipeline order inside normalization** (D49): (1) sentence-split protections for abbreviation dots; (2) whole-token tables (references, citations, tickers, gene symbols, `y/y`, `n/m`, HGVS) so that their `/`, `:`, `>` and `.` are claimed before any symbol rule; (3) number-anchored grammar (currency, units, scientific notation, uncertainty, ranges, ratios, data units, coordinates) so that `′`, `/` and `°` after a number are claimed before `_speak_symbols`; (4) field-gated rules (formulas, regnal numerals, clinical shorthand, statistics position); (5) today's `_speak_symbols` and mathspeak with role-keyed entries; (6) SYN-4 and the lexicon in the backend. History.md §6 and physics.md §2.11 both depend on step 3 preceding step 5 (today `51°30′N` comes out as "51 degrees30′N" with the prime leaked, `_agent/results/871_history_probe_roman_structural.txt` as quoted in `_agent/reports/domain-speech-history.md`).

**Decisions** (all confirmed 2026-10-19 by the user; logged in `docs/TECHNICAL_DESIGN.md`, "M6 decisions")

- **D45** ING-11 profile gains a multi-valued `fields` set beside the `prose`/`mixed`/`math` class, detected from token densities, user-overridable, re-normalizing without re-ingesting. Confirmed 2026-10-19.
- **D46** "One wording per symbol per role": `math_convention.json` entries may carry role-keyed wordings selected by operand class or span type; banned wordings stay banned in every role. Confirmed 2026-10-19.
- **D47** Units are parsed as expressions (prefix, unit, power, product, quotient), not token by token; "per" is the units reading of `/`, "over" the maths reading. Confirmed 2026-10-19.
- **D48** Shared data tables in one place under `api/hearnarro/ingestion/` (element symbols and names, polyatomic ions, units and prefixes, currencies, per-field abbreviations, reference works), each a data file with its own unit tests; no table is duplicated per field. Confirmed 2026-10-19.
- **D49** The normalization order above. Confirmed 2026-10-19.
- **D50** EVAL-11 with per-domain floors, tier 0, same scorer as EVAL-10. Confirmed 2026-10-19.
- **D51** Per-document reading settings (`jurisdiction`, `read_quantity_names`, `read_tables`, `quote_marks`) stored with the document like the ING-11 override. Confirmed 2026-10-19.

## Data model and API

| Item | Values | Notes |
| --- | --- | --- |
| Profile `fields` (D45) | `chemistry`, `physics`, `biology`, `clinical`, `finance`, `humanities`, `law`, `linguistics`, `computing`, `statistics` | Stored with the existing ING-11 profile; whether that needs an Alembic migration is checked in the build spec (unverified). Shown beside the class badge in LIB-1 |
| `jurisdiction` (D51) | `us` (default), `england_wales`, `scotland` | Inferred from neutral citations such as `[2019] UKSC 41`; user-set wins |
| `read_quantity_names` | off (default), on | Uses only the document's own glossary |
| `read_tables` | `announce` (default, today's ING-7 cue), `rows` | DOM-21 |
| `quote_marks` | off (default), on | DOM-18 |
| Dataset | `evals/data/domain_speech.jsonl`: `id`, `domain`, `class`, `raw`, `spoken`, `block` | Staging copy `_agent/research/domain-speech/domain_speech.jsonl`, assembled by a parallel task (not read here). The notes' §5 carry the source pairs; ids run to chemistry_44, physics_57, biology_45, finance_40, history_45, cs_stats_47 (278 rows, counted from the note files in `_agent/results/880_prd_domains_shape.txt`) |
| Settings | none new in `settings.py` | Tables are data files, not settings |

**API.** `GET /documents/{id}` and the library rows carry `profile.fields` and the four reading settings; `PATCH` of the document profile (the existing ING-11 override path) accepts them and triggers re-normalization. No new endpoint.

## Non-functional requirements

| Area | Requirement |
| --- | --- |
| Licensing | No new dependency: rules are Python and data tables. Data tables are written by the project from the public standards the notes cite (NIST SP 811, IUPAC, HGVS, APA); no copyleft word list is imported. `api/scripts/check_licences.py` stays green |
| Eval time | Tier 0 stays near today's 15 s: EVAL-11 runs the normalizer only, on about 280 pairs; target under 2 s added (proposed, unverified) |
| Throughput | The domain pass adds under 10 % to normalization time on the 15 EVAL-1 fixtures (proposed, measured in the first phase) |
| Determinism | The same text, profile and settings give the same spoken text; no network, no model |
| Evals rule | Every change to `api/hearnarro/ingestion/` or the lexicon and acronym tables runs tier-0 before and after and cites the compare (`CLAUDE.md`) |
| Privacy | Pairs are written by the project; no user documents in datasets |

## Milestones

Placement decided 2026-10-19 (decision 29): **milestone M6 "Domain reading"**, its own milestone after M5 closes. It starts after the M5 gate passes (`CLAUDE.md` milestone rule) and in a fresh session. Classroom view is renumbered M7 and Sources and formats M8 (`docs/PRD.md`, "Milestones"); neither depends on M6. Alternatives not chosen: a late M5 phase for DOM-1 to DOM-6 only, with the domains after v1; or phases inside the Classroom view milestone.

Phase order by payoff: the shared grammar first, because every domain's probe fails on it (units, scientific notation, ranges, numbers and abbreviation dots appear in all six probe files). The probe failure counts are flat (14 or 15 of 15 in every domain, table above), so they do not rank the domains; the order below is a judgement (unverified) on how many probe lines each domain still fails after the shared phase, and the first step of phase 2 is to re-run the six probes and reorder by the remaining failures.

| Phase | Rows | Why here |
| --- | --- | --- |
| 0 | DOM-27 (EVAL-11 and dataset), DOM-22 profile fields | Gate tests before features; the suite measures every later phase |
| 1 | DOM-1 to DOM-6, DOM-26 | Shared grammar; touches all six probes |
| 2 | DOM-13 statistics reporting, DOM-19 | Shared by biology, cs_stats and finance; APA and asymptotic lines dominate the cs_stats probe |
| 3 | DOM-7, DOM-11, DOM-14, DOM-16 | The P0 core of chemistry, biology, finance and history |
| 4 | DOM-24, DOM-25 lexicon and abbreviation tables | Needs EVAL-4 runs with the real backend (tier 1) |
| 5 | DOM-8, DOM-9, DOM-10, DOM-12, DOM-15, DOM-17, DOM-20, DOM-23 | P1 per-domain classes |
| 6 | DOM-18, DOM-21 | P2 |

**Gate test (specified, not written).** `api/tests/test_dom_gate.py::test_dom27_domain_speech_floor`: EVAL-11 over `evals/data/domain_speech.jsonl` scores ≥ 0.95 per landed domain and ≥ 0.90 per class with ≥ 3 pairs, with zero raw-symbol leaks; and `test_dom_probe_strings`: the 90 probe strings of results 850–875 reach ≥ 13 of 15 correct per domain.

## Decisions and risks

### Decisions (2026-10-19)

The notes raise 50 open questions (8 per note, 10 in physics). They reduce to the 29 decisions below. The proposal gave a recommendation for each; the user accepted every recommendation on 2026-10-19, and the "Decision" column records it with the notes that raised the question (`note §8.n`).

| # | Question | Decision | Raised by |
| --- | --- | --- | --- |
| 1 | How field-dependent rules are switched | D45 `fields` set, detected, overridable; rules a note calls unambiguous run everywhere | chemistry §8.7, biology §8.6, finance §8.7, history §8.7, cs_stats §8.7 |
| 2 | Role-dependent second wordings (`~` "about", `Re(` "the real part of", dimensionless numbers by name, `Θ(` "big theta of") | Accept under D46 | physics §8.2, §8.4 |
| 3 | Reaction arrow wording | "reacts to form" between chemical formulas (sourced); "yields" between nuclides or particles; not chosen: "yields" for both, "forms", "decays to" | physics §8.3 (with chemistry §2.5) |
| 4 | `/` in units | "per" inside a unit expression; "over" stays for maths and blood pressure | biology §8.1 |
| 5 | Unit plural and attributive use | Keep §3c "plural unless 1"; add attributive singular before a noun ("a 2.4 kilobase insert"); concentration units unpluralised | physics §8.1, biology §8.7 |
| 6 | E-notation `3e-4` | "3 times 10 to the minus 4" in prose and maths; "3 e minus 4" inside code listings only | cs_stats §8.4 |
| 7 | Exceptions to "numbers stay digits" | Accept regnal ordinal words, "the twenties", military "oh six hundred hours"; no mass-number grouping; oxidation states and cranial nerves stay digits | history §8.1, physics §8.7 |
| 8 | Decimal readings | Leading-dot "point 0 5" in every document; long decimals: run a probe first (digit-by-digit may be a `num2words` artefact); probe how the backend reads years such as 1914 before the humanities phase | chemistry §8.8, cs_stats §8.8, history §8.2 |
| 9 | Flattened or zero subscripts | §3c "sub" by default; idiom table for fixed readings: `Ksp`/`Ka`/`pKa` letters, `R0` "r nought", `log₁₀` "log base 10", `log2FC` "log 2 fold change"; `ε₀` stays "epsilon sub 0"; lexicon spelling "naught" | chemistry §8.2, physics §8.5, §8.9, biology §8.5 |
| 10 | `Δ` | §3c "capital delta"; "heat" only above an arrow; `ΔF508` "delta f 508" as an HGVS idiom; no "change in" | chemistry §8.5, finance §8.3 |
| 11 | Statistics abbreviations | Expand in statistics position by the sentence rule plus the `statistics` field; `SD` "standard deviation" there, spelled elsewhere | cs_stats §8.7 (biology §2.8 spells SD) |
| 12 | Significance stars | Read as a count ("3 stars") in every field; cs_stats's silent reading drops information when the legend is off the page | finance §8.6 (biology §2.8 agrees; cs_stats §2.16 silent) |
| 13 | Results tables | `read_tables` setting, default announce; empty cell "nil" under `finance`, "not reported" elsewhere | cs_stats §8.6 (finance §2.8 "nil") |
| 14 | Genotype `-/-` | Read as written ("minus minus"); never interpret as "knockout" | biology §8.2 |
| 15 | Long nucleotide runs | Spell up to 24 bases, then "and N more bases" | biology §8.3 |
| 16 | Named-thing exceptions | Lexicon phrases allowed for named enzymes (`Na+/K+-ATPase`); no automatic common names; hydrate keeps "dot" | biology §8.4, chemistry §8.1, §8.6 |
| 17 | Isotopes and configurations | "carbon 14" (name first); "1 s 2" (count, not power) | chemistry §8.3, §8.4 |
| 18 | Maths conventions in statistics and physics | Keep §3c `N` "n of" and "to the minus 1"; accept `⟨x⟩` "the expectation value of x" for a single argument under `physics` | cs_stats §8.1, §8.2, physics §8.8 |
| 19 | House choices in the acronym table | "basis points", spelled tickers, "q 3" and "fiscal 24", `ibid` read as the word, SQL "s q l", MAP spelled in statistics, ViT spoken, "7 b" inside a model name | finance §8.1, §8.4, §8.5, history §8.3, cs_stats §8.3, §8.5 |
| 20 | Negative amounts | "minus 1,234" (one word for negatives) | finance §8.2 |
| 21 | `read_quantity_names` default | Off for every profile | physics §8.10 |
| 22 | `v.` jurisdiction | Setting, default US, inferred from neutral-citation shape | history §8.4 |
| 23 | Block quotation cue | Setting, off by default | history §8.5 |
| 24 | IPA spans | Skip with a short cue now; a phoneme path through `TTSBackend` is a separate decision after v1 | history §8.6 |
| 25 | Footnote digits glued to words | Drop in every profile, as numeric citations | history §8.8 |
| 26 | Extraction repair | Font-size superscript restoration in ING-3 (DOM-5, P1); `µ`→`m` flagged, not fixed | biology §8.8 |
| 27 | Geological ages | "million years ago" after a number under `physics`; "megaannum" not used | physics §8.6 |
| 28 | Dataset hygiene | Map the notes' `paragraph` to the EVAL-10 value `body`, add `table`; lower-case every `spoken` (physics pairs keep prose case; the scorer lower-cases anyway) | finance §8.8 |
| 29 | Placement | Own milestone after M5: M6 "Domain reading"; Classroom view becomes M7, Sources and formats M8 | this PRD |

**Risks**

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| Flattened superscripts: `3.0 × 10⁸` arrives as `× 108`, `10⁶ cells` as `106 cells`, `Ca²⁺` as `Ca2+`, `p²` as `p2` (physics.md §2.3, biology.md §3) | High | DOM-5 restores only from font-size runs or unambiguous tables; otherwise read as written, never guessed |
| Symbol-font `µ` extracted as `m`: `µM` becomes `mM`, a 1000× error read confidently (biology.md §3, chemistry.md §2.7) | Medium | Not fixable from text; flag in the profile when Symbol-font runs are present; never "correct" silently |
| Genus initials and Latin abbreviations as sentence ends (`E. coli`, `b.i.d.`) split a segment mid-phrase (biology.md §2.2, §2.7) | High | DOM-26 runs before segmentation |
| Other Symbol-font artefacts: `→` as `®`, `Δ` as `D`, `Ω` as `W`, `⟩` as `i`, `β` as `ß` or `b`, `ſ` as `f`, `±` as `+/-` (chemistry.md §2.5, physics.md §2.6, §2.9, biology.md §2.5, history.md §2.8) | Medium | Map only where context proves it (`ß` before a digit in a molecule name); leave the rest |
| Field misdetection turns `CO` into "c o" or `PO` into "by mouth" in the wrong paper | Medium | Field gating (D45), user override, EVAL-11 negative pairs |
| Role rules collide (the same `/`, `:`, `[ ]`, `*` claimed by two rules) | Medium | D49 order and one test per conflict row in "Shared symbols" |
| Many wordings are "proposed", not sourced | High | User review of the conventions tables before phase 1; EVAL-11 pairs fixed only after that review |
| Lexicon respellings untested on Kokoro | Medium | EVAL-4 tier 1 per category (DOM-24) |
