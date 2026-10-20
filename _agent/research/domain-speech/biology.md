# Reading biology, life-science and medical notation aloud (domain-speech-biology)

Research note for the supervisor, 2026-10-19 (task domain-speech-biology). Shape follows spec
`_agent/specs/m5-academic-reading.md` §3c: lower case, one wording per pattern, numbers stay digits (the
backend's `num2words` shim speaks them), punctuation is prosody only. Where a biology string reuses a maths
symbol (`=`, `<`, `±`, `×`, `²`, `→`, `/` in a ratio), the §3c wording is reused, never a second one.
Today's behaviour is in `_agent/results/860_biology_probe_today.txt` (15 strings; 0 fully correct).
"Proposed" means no source prescribes the spoken form; it is how lecturers commonly say it, and the
supervisor decides.

## 1. What a teacher does

A biology or medicine lecturer never reads the punctuation of a symbol: "TP53" is "t p fifty-three",
"Trp53−/−" is "trp fifty-three minus minus" (or "knockout"), "c.524G>A" is "c dot five twenty-four g to a",
and "5 mg/kg PO b.i.d." is "five milligrams per kilogram by mouth twice a day". Units are always spoken as
full unit names with "per" for the slash, abbreviations that are Latin instructions (b.i.d., q8h, PRN) are
always expanded into their English meaning, and genus abbreviations ("E. coli") are read as the letter then
the species name with no pause. Gene symbols are read as a word when they are pronounceable and established
as words in the field (SOX2 "sox two", KRAS "k ras", BRCA1 "bracka one"), otherwise letter by letter with the
digits as numbers (CDK4 "c d k four"). Silently, the reader relies on italics (gene vs protein), superscripts
(alleles, ion charges, powers) and subscripts (N_e, F_ST); aloud, the student must hear the distinction that
those typographic cues carried, so the narrator has to say "minus minus", "plus", "squared", "sub" where the
page used position, and must never let ">", "/", "µ", "^" or a bare "-/-" reach the voice.

## 2. Notation classes

### 2.1 Gene and protein symbols, genotypes (class `gene`)

**Detection.** 2-10 character tokens of capitals and digits, optionally a hyphen and a digit or Greek
letter (TP53, BRCA1, CDK4, SOX2, IL-6, TNF-α); mouse/rat form capital then lower case then digits (Trp53,
Sox2); protein p53 (lower-case p plus digits). Italics are usually lost in extraction (the font run survives
only if ING keeps font spans). Genotype superscripts flatten to the baseline: `Trp53−/−` becomes `Trp53-/-`
or `Trp53 -/-` (minus may be U+2212, U+2013 or a hyphen); `+/−`, `fl/fl`, `Cre+`. Allele superscripts flatten
into the symbol: `Trp53tm1Brd`.

**Rule.** (a) A symbol in the lexicon (§4) is read as its lexicon word plus its trailing digits ("brca 1",
"sox 2", "kras" as "k ras"). (b) Otherwise letters spelled, digits as a number, a hyphen between letters and a
digit is silent (IL-6 "i l 6"). (c) A Greek suffix after a hyphen is read by name (§3c Greek). (d) Genotype
suffixes are read as written: `-/-` "minus minus", `+/-` "plus minus" (never "plus or minus": that is `±`),
`+/+` "plus plus", `fl/fl` "flox flox". (e) WT, KO, cKO, KI expand when standing alone as a genotype word.
(f) The protein form p53 is read "p 53". Italic vs upright (gene vs protein) is not spoken.

| Pattern | Spoken |
| --- | --- |
| `TP53` | t p 53 |
| `p53` | p 53 |
| `Trp53` | t r p 53 |
| `CDK4` | c d k 4 |
| `SOX2` / `Sox2` | sox 2 |
| `BRCA1` | brca 1 (lexicon: BRAK-uh) |
| `KRAS` | k ras |
| `IL-6` | i l 6 |
| `X-/-`, `X−/−` | x minus minus |
| `X+/-` | x plus minus |
| `X fl/fl` | x flox flox |
| `WT` | wild type |
| `KO` / `cKO` | knockout / conditional knockout |

**Source.** HGNC guidelines (italic gene, upright protein, capitals for human; Latin letters and Arabic
numerals only); MGI rules (mouse case, `tm1` allele superscripts). Spoken forms: proposed.
**Confidence.** Typography sourced; wording proposed.

### 2.2 Species, taxonomy, strains and cell lines (class `taxon`)

**Detection.** Capitalized genus plus lower-case epithet, often italic (lost); abbreviated genus as one
capital and a period (`E. coli`, `S. cerevisiae`, `C. elegans`, `D. melanogaster`); `sp.`, `spp.`, `subsp.`,
`var.`, `cf.`; strains `K-12`, `BL21(DE3)`, `C57BL/6J`; cell lines `HeLa`, `HEK293T`, `CHO-K1`. The period
after a genus initial is a sentence-split hazard (ING sentence segmentation).

**Rule.** A one-capital-plus-period before a lower-case Latin epithet is the genus initial: read the letter,
no pause, never a sentence break. `sp.` "species", `spp.` "species" (plural; same word), `subsp.`
"subspecies", `var.` "variety". Strain codes: letters spelled, digits as numbers, hyphen and slash silent
(`C57BL/6J` "c 57 b l 6 j"; colloquial "black six" is not used). Cell lines: lexicon if a word (HeLa), else
spelled. Latin binomials go to the lexicon (§4).

| Pattern | Spoken |
| --- | --- |
| `E. coli` | e coli |
| `S. cerevisiae` | s cerevisiae |
| `Homo sapiens` | homo sapiens |
| `Streptomyces sp.` / `spp.` | streptomyces species / species |
| `K-12` | k 12 |
| `C57BL/6J` | c 57 b l 6 j |
| `HeLa` | hela (lexicon: HEE-lah) |
| `HEK293T` | h e k 293 t |

**Source.** ICZN/ICN conventions for abbreviated genus (well known; not fetched this task); pronunciation
"ee KOH-lye" from pronunciation pages (low quality, see §7). **Confidence.** proposed.

### 2.3 Sequences and molecular units (class `sequence`)

**Detection.** Runs of only A C G T (U, N) of length ≥ 4 in capitals; 5′ and 3′ (prime may extract as `'`,
`′` or be lost: `5'-ATG-3'`); arrows `→`; amino-acid three-letter codes (Arg, His, Gly) and one-letter
strings (MKTAYIAK); units kb, bp, nt, kDa, aa after a number.

**Rule.** A nucleotide run is spelled letter by letter, lower case. Proposed cap: runs over 24 letters are read
as "a sequence of N bases" (N counted), because a listener cannot hold more. `5′` "5 prime" (§3c prime);
`5′→3′` "5 prime to 3 prime" (§3c "to" between two endpoints; never "goes to", which §3c bans). Units:
`kb` "kilobases", `bp` "base pairs", `nt` "nucleotides", `kDa` "kilodaltons", `aa` "amino acids" (only after a
number). Three-letter amino-acid codes read as written words ("arg"); one-letter peptide strings spelled.

| Pattern | Spoken |
| --- | --- |
| `ACGTTGCA` | a c g t t g c a |
| `5′-ATG-3′` | 5 prime a t g 3 prime |
| `5′→3′` | 5 prime to 3 prime |
| `2.4 kb` / `300 bp` | 2.4 kilobases / 300 base pairs |
| `55 kDa` | 55 kilodaltons |
| `120 aa` | 120 amino acids |
| `Arg` | arg |

**Source.** §3c (prime, arrow); units proposed (kb/bp are not SI; kDa follows the SI-prefix pattern).
**Confidence.** proposed.

### 2.4 Variants, loci and karyotypes (class `variant`)

**Detection.** HGVS `c.524G>A`, `g.`, `n.`, `p.Arg175His`, `p.R175H`, `p.(Arg175His)`, `del`, `dup`, `ins`,
`fs`, `*` stop, `ΔF508` (Δ may extract as `delta`, `D`, or drop), `G12D` (letter digits letter), `rs7412`;
cytogenetic bands `17p13.1`, `Xq28`, `11q23`; karyotypes `46,XY`, `47,XX,+21`, `45,X`.

**Rule.** HGVS: the prefix letter then "dot", position as a number, `>` is "to" (here it is a substitution,
not a relation: context class decided by the `c.`/`g.` prefix), bases spelled. Protein: three-letter codes
read as words, one-letter codes spelled. `ΔF508` "delta f 508". `G12D` "g 12 d". `rs` numbers "r s" then the
number. Bands: chromosome number, arm letter, band number, the sub-band decimal as written ("17 p 13.1").
Karyotype: count, then sex chromosomes spelled; the comma is prosody; `+21` "plus 21".

| Pattern | Spoken |
| --- | --- |
| `c.524G>A` | c dot 524 g to a |
| `p.Arg175His` | p dot arg 175 his |
| `p.R175H` | p dot r 175 h |
| `c.1521_1523delCTT` | c dot 1521 to 1523 del c t t |
| `ΔF508` | delta f 508 |
| `G12D` | g 12 d |
| `rs7412` | r s 7412 |
| `17p13.1` | 17 p 13.1 |
| `Xq28` | x q 28 |
| `46,XY` | 46, x y |
| `47,XX,+21` | 47, x x, plus 21 |

**Source.** HGVS recommendations (den Dunnen et al. 2016) for the syntax; ISCN for band structure; spoken
forms are clinical-genetics practice, proposed. **Confidence.** syntax sourced; wording proposed.

### 2.5 Receptors, enzymes and named compounds with Greek, ions and numerals (class `molecule`)

**Detection.** `β2-adrenergic` (β may extract as `b`, `ß` German sharp s, or `beta`), `TNF-α`, `IFN-γ`,
`Na+/K+-ATPase` (charges flattened: `Na+`, `Ca2+`, `Ca 2+`, `Ca++`), `EC 3.4.21.4`, `CYP3A4`, `P450`, `HbA1c`
(subscript flattened), `NAD+`, `ATP`, `cAMP`.

**Rule.** Greek by name (§3c). An ion charge after an element symbol is "plus" / "minus" with its number
before it (`Ca2+` "c a 2 plus"); proposed exception: a named enzyme or channel with ions gets a lexicon phrase
("sodium potassium atpase") because no lecturer says "n a plus k plus". `ß` immediately before a digit or
hyphen in a molecular name is beta (extraction artefact). EC numbers: "e c" then the four numbers joined by
"point". Enzyme families spelled except lexicon words (CYP "sip", ATPase "a t p ase").

| Pattern | Spoken |
| --- | --- |
| `β2-adrenergic` | beta 2 adrenergic |
| `TNF-α` | t n f alpha |
| `IL-6` | i l 6 |
| `Na+/K+-ATPase` | sodium potassium a t p ase |
| `Ca2+` | c a 2 plus |
| `EC 3.4.21.4` | e c 3 point 4 point 21 point 4 |
| `CYP3A4` | cyp 3 a 4 (lexicon: sip) |
| `cytochrome P450` | cytochrome p 450 |
| `HbA1c` | h b a 1 c |
| `NAD+` | n a d plus |
| `cAMP` | cyclic a m p |

**Source.** §3c Greek and chemistry (letter by letter with digits); ion and enzyme phrases proposed.
**Confidence.** proposed.

### 2.6 Laboratory quantities and protocol shorthand (class `lab_unit`)

**Detection.** Number then unit with micro sign `µ` (U+00B5) or Greek `μ` (U+03BC), sometimes extracted as
`u` or `m` (Symbol font): `µg/mL`, `ug/ml`, `ng/µL`, `mM`, `nM`, `µM`, `U/mL`; `10^6`, `10⁶`, `106`
(superscript flattened, the dangerous case); `×g`, `x g`, `xg`; `rpm`; `37 °C`, `37°C`, `37 oC`; `5% CO2`;
`pH 7.4`; `OD600`, `OD 600`; `1:1000`; `P3`; time units `h`, `min`, `s`, `o/n`, `RT`.

**Rule.** §3c units: prefix word plus unit word, US spelling, plural unless 1. The unit slash is "per"
(NIST SP 811: a unit formed by division uses "per", not a solidus); this is the units reading, distinct from
§3c's maths `a/b` "over". Molar: `M` "molar" with prefixes ("millimolar"; concentration units do not
pluralize). `10^6`/`10⁶` "10 to the 6" (§3c power). `×g` "times g". `rpm` "r p m". `°C` stays with ING-6.
`CO2` "c o 2" (§3c). `pH` "p h". `OD600` "o d 600". Ratio `1:1000` "1 to 1000". `P3` after "passage" or in a
culture context "passage 3". `h`, `min`, `s` after a number "hours", "minutes", "seconds"; `o/n` "overnight";
`RT` "room temperature" (only in a protocol sentence). A flattened `106 cells` cannot be repaired from text
alone: open question.

| Pattern | Spoken |
| --- | --- |
| `10 µg/mL` | 10 micrograms per milliliter |
| `50 ng/µL` | 50 nanograms per microliter |
| `150 mM` / `10 nM` / `5 µM` | 150 millimolar / 10 nanomolar / 5 micromolar |
| `1 × 10^6 cells/mL` | 1 times 10 to the 6 cells per milliliter |
| `300 ×g` | 300 times g |
| `3000 rpm` | 3000 r p m |
| `37 °C` | 37 degrees celsius |
| `5% CO2` | 5 percent c o 2 |
| `pH 7.4` | p h 7.4 |
| `OD600` | o d 600 |
| `1:1000` | 1 to 1000 |
| `P3` (passage) | passage 3 |
| `2 h` / `30 min` / `o/n` | 2 hours / 30 minutes / overnight |

**Source.** NIST SP 811 ch. 9 ("per", plurals, degree Celsius); §3c units and chemistry. Lab shorthand
expansions proposed. **Confidence.** units sourced; shorthand proposed.

### 2.7 Medical and clinical notation (class `clinical`)

**Detection.** Dose then route then frequency: `500 mg PO t.i.d.`, `1 g PO q6h PRN`, `5 mg/kg IV`; Latin
frequency abbreviations with or without periods (`b.i.d.`, `bid`, `BID`, `t.i.d.`, `q.i.d.`, `q4h`, `q8h`,
`qd`, `PRN`, `prn`, `stat`); routes `PO`, `IV`, `IM`, `SC`/`SQ`; vitals `BP 120/80 mmHg`, `HR 72 bpm`,
`RR 16`, `SpO2 98%`, `T 37.2 °C`; chart shorthand `Pt`, `Hx`, `Dx`, `Rx`, `Tx`, `Sx`, `c/o`; codes `ICD-10
E11.9`. Periods inside `b.i.d.` are sentence-split hazards.

**Rule.** Frequencies and routes are always expanded (a student hears the meaning, which is also what ISMP
asks for in place of error-prone forms). `q` + N + `h` "every N hours". `IV`, `IM` spelled ("i v", the way
clinicians say them); `PO` "by mouth"; `SC` "subcutaneously". `mg/kg` "milligrams per kilogram" (2.6 "per").
Blood pressure `120/80` "120 over 80" (the clinical reading, which coincides with §3c's slash "over");
`mmHg` "millimeters of mercury"; `bpm` "beats per minute". Chart shorthand expands: `Pt` "patient", `Hx`
"history", `Dx` "diagnosis", `Rx` "prescription", `Tx` "treatment", `Sx` "symptoms". ICD codes: "i c d 10" then
the code letter and the number as written.

| Pattern | Spoken |
| --- | --- |
| `500 mg PO t.i.d.` | 500 milligrams by mouth three times a day |
| `b.i.d.` / `q.i.d.` / `qd` | twice a day / four times a day / once a day |
| `q6h` / `q8h` | every 6 hours / every 8 hours |
| `PRN` | as needed |
| `IV` / `IM` / `SC` | i v / i m / subcutaneously |
| `15 mg/kg` | 15 milligrams per kilogram |
| `BP 120/80 mmHg` | b p 120 over 80 millimeters of mercury |
| `HR 72 bpm` | heart rate 72 beats per minute |
| `SpO2 98%` | s p o 2 98 percent |
| `Pt` / `Hx` / `Dx` / `Rx` | patient / history / diagnosis / prescription |
| `ICD-10 E11.9` | i c d 10 e 11.9 |

**Source.** ISMP List of Error-Prone Abbreviations (expand rather than abbreviate; "by mouth" for PO);
meanings of BID/TID/PRN/qNh from pharmacy-calculation texts (§7). **Confidence.** meanings sourced;
spoken forms proposed.

### 2.8 Statistics as reported in life-science papers (class `stats_report`)

**Detection.** `n = 24`, `N=12`, `p < 0.05`, `P<0.001`, `p = 0.003`, `95% CI 1.2–3.4` (en dash may extract as
`-` or `to`), `95% CI [1.2, 3.4]`, `OR 2.1`, `HR 0.74`, `RR`, `mean ± SD`, `± SEM`, significance stars `*`,
`**`, `***`, `ns`, `2.5-fold`, `log2FC` (subscript flattened), `R²`, `r = 0.62`.

**Rule.** Symbols use §3c: `=` "equals", `<` "is less than", `±` "plus or minus". Idioms: `CI` "confidence
interval"; a range dash between two numbers after CI "to" (as §3c `Eqs. 3–5` "3 to 5"); `OR` "odds ratio",
`HR` "hazard ratio" only before a number in a statistics sentence (else heart rate, 2.7); `RR` "relative
risk"; `SD`, `SEM` spelled; stars attached to a value or column are read "star", "2 stars", "3 stars"
(proposed); `ns` "not significant"; `-fold` "fold"; `log2FC` "log 2 fold change"; `R²` "r squared".

| Pattern | Spoken |
| --- | --- |
| `n = 24` | n equals 24 |
| `p < 0.05` | p is less than 0.05 |
| `p = 0.003` | p equals 0.003 |
| `95% CI 1.2–3.4` | 95 percent confidence interval 1.2 to 3.4 |
| `OR 2.1` / `HR 0.74` | odds ratio 2.1 / hazard ratio 0.74 |
| `mean ± SD` | mean plus or minus s d |
| `**` | 2 stars |
| `ns` | not significant |
| `log2FC` | log 2 fold change |
| `R² = 0.81` | r squared equals 0.81 |

**Source.** §3c relations; AMA Manual of Style statistics conventions (abbreviation meanings; not fetched
this task). **Confidence.** symbol wording sourced (§3c); idioms proposed.

### 2.9 Anatomy, physiology and eponyms (class `anatomy`)

**Detection.** Latin anatomical terms (`musculus biceps brachii`, `vena cava`, `corpus callosum`), Greek/Latin
affixes, eponyms (`Golgi`, `Purkinje`, `Ranvier`, `Wernicke`, `Broca`, `Langerhans`, `Schwann`), plurals
(`foramina`, `ganglia`), cranial nerves `CN VII` (Roman numeral).

**Rule.** No text rewrite; spelling is already right. Each term goes to the TERM-1 lexicon (§4). Cranial
nerve Roman numerals after `CN` read as numbers ("cranial nerve 7"). Possessive eponyms unchanged.

| Pattern | Spoken |
| --- | --- |
| `Golgi apparatus` | golgi apparatus (lexicon: GOHL-jee) |
| `Purkinje cells` | purkinje cells (lexicon: pur-KIN-jee) |
| `CN VII` | cranial nerve 7 |

**Source.** proposed; lexicon respellings from standard medical-dictionary pronunciations (not fetched).
**Confidence.** proposed.

### 2.10 Ecology, evolution and population genetics (class `popgen`)

**Detection.** `N_e` flattened to `Ne` (collides with neon), `F_ST` to `FST`/`Fst`, `r` and `K` as
parameters, `p² + 2pq + q² = 1` (superscripts may flatten to `p2`), `dN/dt = rN(1 − N/K)`, `λ`, `R0` (R
nought), `θ`, `π` (nucleotide diversity), `dN/dS`.

**Rule.** Everything inside a maths span follows §3c exactly (subscripts "sub", powers "squared",
juxtaposition silent, "times" before a parenthesized factor, `d N/d t` "d n over d t"). Flattened forms out of
maths: `Ne` in a popgen sentence "n sub e"; `Fst`/`FST` "f sub s t"; `R0` "r nought" (the fixed epidemiology
reading, proposed exception to "r sub 0"); `dN/dS` "d n over d s".

| Pattern | Spoken |
| --- | --- |
| `p² + 2pq + q² = 1` | p squared plus 2 p q plus q squared equals 1 |
| `dN/dt = rN(1 − N/K)` | d n over d t equals r n times 1 minus n over k |
| `Ne = 500` | n sub e equals 500 |
| `FST = 0.12` | f sub s t equals 0.12 |
| `R0 = 2.5` | r nought equals 2.5 |

**Source.** §3c (scripts, juxtaposition, fractions). **Confidence.** sourced (via §3c) except `R0`, proposed.

## 3. Context rules and ambiguities

- **`>`**: "to" inside an HGVS description (preceded by `c.`/`g.`/`n.`/`m.`/`r.` and a position), else §3c
  "is greater than". Decided by the token shape alone.
- **`+/-`**: "plus minus" when attached to a gene symbol or after a genotype word; `±` (single glyph) always
  "plus or minus". Extraction that turns `±` into `+/-` (seen in some PDFs) is ambiguous: before a number it is
  `±`; after a gene symbol it is a genotype.
- **`HR`**: hazard ratio before a number in a statistics sentence (near CI, p); heart rate in a vitals list
  (near BP, bpm). Needs the sentence.
- **`P3`, `P0`, `P7`**: passage in a cell-culture sentence; postnatal day (`P7` "postnatal day 7") in
  developmental biology; a protein name otherwise. Needs the sentence; the profile cannot decide.
- **`Ne`, `Fst`, `K`, `r`**: parameters only in a population-genetics or ecology context; `Ne` is neon in
  chemistry. A document-level topic flag (new ING-11 field, see §6) could decide.
- **Abbreviated genus `E.`**: never a sentence end when followed by a lower-case Latin word; this is an ING
  sentence-split rule, not a speech rule.
- **Superscript loss**: `10^6` vs flattened `106`, `Ca2+` vs `Ca 2+`, `p2` vs `p²`. Font-size spans from
  ING (if kept) decide; from text alone `106` cannot be repaired.
- **Gene as word vs spelled**: the SYN-4 heuristic would speak some symbols wrongly (it would say "brca" as a
  word attempt, may speak "TNF" spelled correctly by luck). A biology lexicon override set is the deciding
  input, not the heuristic.
- **`µ` vs `m` artefact**: Symbol-font PDFs extract `µ` as `m`, turning `µM` into `mM` (a 1000x error). Not
  decidable from text; flag only.
- **What ING-11 could decide**: a `bio`/`clinical` sub-profile could switch on the clinical expansions
  (2.7) and the popgen flattened forms (2.10), and keep them off in a computer-science paper where `PO`,
  `IV`, `HR` mean other things.

## 4. Pronunciation lexicon needs (TERM-1)

| Term | Respelling | Note |
| --- | --- | --- |
| BRCA1 / BRCA | BRAK-uh (one) | spoken as a word in clinic |
| SOX2 | soks | word |
| KRAS | KAY-ras | letter K then "ras" |
| CYP (CYP3A4) | sip | family name as word |
| HeLa | HEE-lah | cell line |
| E. coli (coli) | ee KOH-lye | species epithet |
| Escherichia | esh-uh-RIK-ee-uh | genus |
| cerevisiae | sair-uh-VIS-ee-ee | yeast epithet |
| elegans (C. elegans) | EL-uh-ganz | |
| melanogaster | mel-uh-noh-GAS-ter | |
| sapiens | SAY-pee-enz | |
| Golgi | GOHL-jee | eponym |
| Purkinje | pur-KIN-jee | eponym |
| Ranvier | RAHN-vee-ay | eponym |
| Wernicke | VUR-ni-kuh | eponym |
| Langerhans | LAHNG-er-hahnz | eponym |
| Schwann | shwahn | eponym |
| ATPase | ay-tee-PEE-ayz | suffix -ase |
| amoxicillin | uh-mok-sih-SIL-in | drug name |
| paracetamol | par-uh-SEE-tuh-mol | drug name |
| corpus callosum | KOR-pus kuh-LOH-sum | Latin |
| foramina | foh-RAM-ih-nuh | Latin plural |
| nought (R0) | nawt | fixed reading |

## 5. Example pairs

```jsonl
{"id": "biology_01", "class": "gene", "raw": "Loss of TP53 in Trp53-/- mice compared with WT littermates.", "spoken": "loss of t p 53 in t r p 53 minus minus mice compared with wild type littermates", "block": "paragraph"}
{"id": "biology_02", "class": "gene", "raw": "p53 accumulates after DNA damage.", "spoken": "p 53 accumulates after d n a damage", "block": "paragraph"}
{"id": "biology_03", "class": "gene", "raw": "CDK4 and SOX2 are amplified.", "spoken": "c d k 4 and sox 2 are amplified", "block": "paragraph"}
{"id": "biology_04", "class": "gene", "raw": "Brca1+/- females", "spoken": "brca 1 plus minus females", "block": "paragraph"}
{"id": "biology_05", "class": "gene", "raw": "Pten fl/fl mice crossed with KO controls", "spoken": "pten flox flox mice crossed with knockout controls", "block": "paragraph"}
{"id": "biology_06", "class": "taxon", "raw": "Cells were grown in E. coli K-12.", "spoken": "cells were grown in e coli k 12", "block": "paragraph"}
{"id": "biology_07", "class": "taxon", "raw": "S. cerevisiae and Streptomyces spp.", "spoken": "s cerevisiae and streptomyces species", "block": "paragraph"}
{"id": "biology_08", "class": "taxon", "raw": "C57BL/6J mice and HEK293T cells", "spoken": "c 57 b l 6 j mice and h e k 293 t cells", "block": "paragraph"}
{"id": "biology_09", "class": "sequence", "raw": "The probe reads ACGTTGCA.", "spoken": "the probe reads a c g t t g c a", "block": "paragraph"}
{"id": "biology_10", "class": "sequence", "raw": "read 5′→3′ with a 2.4 kb insert", "spoken": "read 5 prime to 3 prime with a 2.4 kilobases insert", "block": "paragraph"}
{"id": "biology_11", "class": "sequence", "raw": "a 55 kDa protein of 480 aa", "spoken": "a 55 kilodaltons protein of 480 amino acids", "block": "paragraph"}
{"id": "biology_12", "class": "sequence", "raw": "300 bp amplicon", "spoken": "300 base pairs amplicon", "block": "paragraph"}
{"id": "biology_13", "class": "variant", "raw": "The variant c.524G>A (p.Arg175His) was found.", "spoken": "the variant c dot 524 g to a, p dot arg 175 his, was found", "block": "paragraph"}
{"id": "biology_14", "class": "variant", "raw": "p.R175H", "spoken": "p dot r 175 h", "block": "paragraph"}
{"id": "biology_15", "class": "variant", "raw": "KRAS G12D and CFTR ΔF508 carriers", "spoken": "kras g 12 d and c f t r delta f 508 carriers", "block": "paragraph"}
{"id": "biology_16", "class": "variant", "raw": "rs7412 genotype", "spoken": "r s 7412 genotype", "block": "paragraph"}
{"id": "biology_17", "class": "variant", "raw": "deletion at 17p13.1", "spoken": "deletion at 17 p 13.1", "block": "paragraph"}
{"id": "biology_18", "class": "variant", "raw": "karyotype 47,XX,+21", "spoken": "karyotype 47, x x, plus 21", "block": "paragraph"}
{"id": "biology_19", "class": "variant", "raw": "46,XY with a gain at Xq28", "spoken": "46, x y with a gain at x q 28", "block": "paragraph"}
{"id": "biology_20", "class": "molecule", "raw": "β2-adrenergic receptor and TNF-α", "spoken": "beta 2 adrenergic receptor and t n f alpha", "block": "paragraph"}
{"id": "biology_21", "class": "molecule", "raw": "IL-6 and IFN-γ release", "spoken": "i l 6 and i f n gamma release", "block": "paragraph"}
{"id": "biology_22", "class": "molecule", "raw": "Na+/K+-ATPase activity", "spoken": "sodium potassium a t p ase activity", "block": "paragraph"}
{"id": "biology_23", "class": "molecule", "raw": "trypsin (EC 3.4.21.4)", "spoken": "trypsin, e c 3 point 4 point 21 point 4", "block": "paragraph"}
{"id": "biology_24", "class": "molecule", "raw": "metabolized by CYP3A4; HbA1c 6.5%", "spoken": "metabolized by cyp 3 a 4, h b a 1 c 6.5 percent", "block": "paragraph"}
{"id": "biology_25", "class": "molecule", "raw": "Ca2+ influx raises cAMP", "spoken": "c a 2 plus influx raises cyclic a m p", "block": "paragraph"}
{"id": "biology_26", "class": "lab_unit", "raw": "Add 10 µg/mL puromycin and 50 ng/µL DNA.", "spoken": "add 10 micrograms per milliliter puromycin and 50 nanograms per microliter d n a", "block": "paragraph"}
{"id": "biology_27", "class": "lab_unit", "raw": "in 150 mM NaCl with 10 nM drug", "spoken": "in 150 millimolar n a c l with 10 nanomolar drug", "block": "paragraph"}
{"id": "biology_28", "class": "lab_unit", "raw": "Seed 1 × 10^6 cells/mL.", "spoken": "seed 1 times 10 to the 6 cells per milliliter", "block": "paragraph"}
{"id": "biology_29", "class": "lab_unit", "raw": "spin at 300 ×g for 5 min", "spoken": "spin at 300 times g for 5 minutes", "block": "paragraph"}
{"id": "biology_30", "class": "lab_unit", "raw": "incubate at 37 °C in 5% CO2, pH 7.4", "spoken": "incubate at 37 degrees celsius in 5 percent c o 2, p h 7.4", "block": "paragraph"}
{"id": "biology_31", "class": "lab_unit", "raw": "Measure OD600 o/n; antibody 1:1000, passage P3.", "spoken": "measure o d 600 overnight, antibody 1 to 1000, passage 3", "block": "paragraph"}
{"id": "biology_32", "class": "clinical", "raw": "amoxicillin 500 mg PO t.i.d.", "spoken": "amoxicillin 500 milligrams by mouth three times a day", "block": "paragraph"}
{"id": "biology_33", "class": "clinical", "raw": "paracetamol 1 g PO q6h PRN", "spoken": "paracetamol 1 gram by mouth every 6 hours as needed", "block": "paragraph"}
{"id": "biology_34", "class": "clinical", "raw": "15 mg/kg IV b.i.d.", "spoken": "15 milligrams per kilogram i v twice a day", "block": "paragraph"}
{"id": "biology_35", "class": "clinical", "raw": "BP 120/80 mmHg, HR 72 bpm", "spoken": "b p 120 over 80 millimeters of mercury, heart rate 72 beats per minute", "block": "paragraph"}
{"id": "biology_36", "class": "clinical", "raw": "Pt with Hx of asthma; Dx: ICD-10 J45.9", "spoken": "patient with history of asthma, diagnosis, i c d 10 j 45.9", "block": "paragraph"}
{"id": "biology_37", "class": "stats_report", "raw": "n = 24, p < 0.05", "spoken": "n equals 24, p is less than 0.05", "block": "paragraph"}
{"id": "biology_38", "class": "stats_report", "raw": "OR 2.1 (95% CI 1.2–3.4), p = 0.003", "spoken": "odds ratio 2.1, 95 percent confidence interval 1.2 to 3.4, p equals 0.003", "block": "paragraph"}
{"id": "biology_39", "class": "stats_report", "raw": "values are mean ± SD; ** p < 0.01", "spoken": "values are mean plus or minus s d, 2 stars p is less than 0.01", "block": "paragraph"}
{"id": "biology_40", "class": "stats_report", "raw": "genes with log2FC > 1 and HR 0.74", "spoken": "genes with log 2 fold change is greater than 1 and hazard ratio 0.74", "block": "paragraph"}
{"id": "biology_41", "class": "anatomy", "raw": "Purkinje cells and the Golgi apparatus", "spoken": "purkinje cells and the golgi apparatus", "block": "paragraph"}
{"id": "biology_42", "class": "anatomy", "raw": "lesion of CN VII", "spoken": "lesion of cranial nerve 7", "block": "paragraph"}
{"id": "biology_43", "class": "popgen", "raw": "p² + 2pq + q² = 1", "spoken": "p squared plus 2 p q plus q squared equals 1", "block": "equation"}
{"id": "biology_44", "class": "popgen", "raw": "dN/dt = rN(1 − N/K)", "spoken": "d n over d t equals r n times 1 minus n over k", "block": "equation"}
{"id": "biology_45", "class": "popgen", "raw": "Fst = 0.12, Ne = 500 and R0 = 2.5", "spoken": "f sub s t equals 0.12, n sub e equals 500 and r nought equals 2.5", "block": "paragraph"}
```

## 6. Where it hooks in HearNarro (proposal)

- `gene`: SYN-4 acronym table (biology `SPELLED`/`SPOKEN` overrides: TP53 spelled, KRAS, SOX, BRCA spoken) plus
  an ING-6 rule for genotype suffixes (`-/-`, `+/-`, `fl/fl`) and WT/KO expansion.
- `taxon`: ING sentence segmentation (genus initial is not a sentence end) plus ING-6 (`sp.`, `spp.`) plus
  TERM-1 (binomials, cell lines).
- `sequence`: ING-6 (nucleotide runs spelled, 5′/3′, kb/bp/kDa/aa units) reusing MATH-3 prime and arrow.
- `variant`: a new ING-6 HGVS/ISCN tokenizer (c./p./rs/bands/karyotypes); `>` as "to" only there.
- `molecule`: MATH-3 Greek and chemistry; TERM-1 for named enzyme phrases and CYP; ING-6 for EC numbers.
- `lab_unit`: MATH-3 units table (add molar, daltons, bases, "per" for unit slash) plus ING-6 lab shorthand.
- `clinical`: ING-6 expansion table (TERM-4-style, configurable), gated by a new ING-11 `bio`/`clinical` flag.
- `stats_report`: MATH-3 relations (already §3c) plus a TERM-4-style idiom table (CI, OR, HR, SD, ns, stars).
- `anatomy`: TERM-1 lexicon only (biology and Latin categories, EVAL-4).
- `popgen`: mathspeak MATH-1/MATH-2 inside maths; ING-6 flattened forms (`Ne`, `Fst`, `R0`) gated by the profile.

## 7. Sources

- https://genenames.org/about/old-guidelines/ and current HGNC guidelines (via search summary): human gene
  symbols upper case, italic; Latin letters and Arabic numerals only; HGNC does not govern protein names.
- https://casrai.org/guides/scientific-nomenclature-examples : human all capitals vs mouse first-letter capital.
- https://radiopaedia.org/articles/gene-and-protein-notation : italic gene vs upright protein; full name upright.
- https://www.informatics.jax.org/mgihome/nomen/gene.shtml and https://informatics.jax.org/faq/GM_nomen.shtml :
  MGI gene and allele symbols (Trp53, `tm1` targeted alleles with lab code).
- https://pmc.ncbi.nlm.nih.gov/articles/PMC3039125 : human vs mouse allele table (Trp53tm1Brd example).
- https://www.hgmd.cf.ac.uk/docs/mut_nom.html : HGVS-era syntax, c.76A>T, p. descriptions.
- https://figshare.le.ac.uk/articles/journal_contribution/HGVS_Recommendations_for_the_Description_of_Sequence_Variants_2016_Update_/10132955/1 :
  current HGVS recommendations (den Dunnen et al. 2016, doi 10.1002/humu.22981).
- https://siesascs.edu.in/docs/notes/Chromosome%20band%20numbering%20%20(Dr_87321.pdf and
  https://rarechromo.org/media/information/Chromosome%2017/17p13.1%20and%2017p13.2%20microdeletions%20FTNW.pdf :
  band address structure (chromosome, arm p/q, band, sub-band); no spoken form prescribed.
- https://online.ecri.org/hubfs/ISMP/Resources/ISMP_ErrorProneAbbreviation_List.pdf and
  https://home.ecri.org/blogs/ismp-resources/list-of-error-prone-abbreviations : expand error-prone
  abbreviations; "by mouth"/"orally" for PO.
- https://library.kendallhunt.com/PES/PharmCalc7E/kh_book/pages/03_ch03-section03.html : meanings of
  bid/tid/prn/qNh; avoid periods in those abbreviations.
- https://nist.gov/pml/special-publication-811/nist-guide-si-chapter-9-rules-and-style-conventions-spelling-unit-names :
  "per" not solidus for spelled unit names; plurals by English grammar; "degree Celsius".
- https://nist.gov/pml/special-publication-811/nist-guide-si-chapter-7-rules-and-style-conventions-expressing-values :
  no spelled-out number with a unit symbol; standard symbols only.
- https://pronounce.tv/word/e-coli and https://brainbound.blog/escherichia-pronunciation : "ee KOH-lye",
  "esh-uh-RIK-ee-uh" (low-quality sources; stress contested).
- `_agent/specs/m5-academic-reading.md` §3c and `api/scripts/math_convention.json` : all reused maths wordings.

Not consulted this task (budget): ClearSpeak/MathSpeak chemistry rules, NVDA/JAWS behaviour, DAISY/NISO,
CSE Scientific Style and Format, AMA Manual of Style, ICZN/ICN codes. Every rule resting on them above is
marked proposed.

## 8. Open questions for the supervisor

1. Unit slash "per" (2.6, NIST) vs §3c `a/b` "over": accept "per" as the units-only reading and add it to
   `math_convention.json` under units, or keep one wording? (Blood pressure keeps "over".)
2. Genotype `-/-`: read as written ("minus minus", proposed) or interpret ("knockout")? Interpreting is
   wrong for non-null alleles.
3. Long nucleotide runs: cap at 24 letters then "a sequence of N bases" (proposed), or always spell?
4. Named enzymes with ions (`Na+/K+-ATPase` "sodium potassium a t p ase") break §3c's "chemical formulas
   letter by letter"; allow a lexicon phrase exception?
5. `R0` "r nought" and `log2FC` "log 2 fold change" are idioms that depart from §3c ("r sub 0", "log sub 2");
   accept idioms outside maths spans?
6. Add a `bio`/`clinical` field to the ING-11 profile to gate clinical expansions and popgen flattened forms?
7. Plural after a unit used as a modifier ("a 2.4 kilobases insert", "300 base pairs amplicon") is what the
   plural rule gives; should a unit before a noun take the singular ("2.4 kilobase insert")? Teachers use
   the singular; §3c is silent.
8. Flattened superscripts (`106 cells/mL`) and `µ`→`m` Symbol-font artefacts cannot be fixed from text; is
   a font-span repair in ING in scope for M5?
