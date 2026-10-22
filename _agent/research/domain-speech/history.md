# Domain speech note: history, humanities, classics, law, literature

Task `domain-speech-history` (2026-10-19). Shape follows spec `_agent/specs/m5-academic-reading.md` §3c:
lower case in the spoken column, one wording per pattern, numbers stay digits unless this note says why
not, punctuation is prosody only (a comma is a pause, never the word "comma"). Evidence of today's
behaviour: `_agent/results/870_history_probe_today.txt` (15 strings), `_agent/results/871_history_probe_roman_structural.txt`
(Roman numerals after structural words, coordinates, asterisk, `<`/`>` in prose).

**Shared conventions in this note (general rules)**

| Rule | Wording |
| --- | --- |
| Ranges `a–b`, `a-b` between numbers in prose | "a to b" (same as ING-6 today and §3c "equations 3 to 5"); an abbreviated second year is completed: `1914–18` "1914 to 1918" |
| Roman numeral after a structural word (chapter, part, act, book, volume, canto, war...) | cardinal word, as today's `_STRUCTURAL` rule does ("chapter four", "act two"; result 871) |
| Roman numeral after a ruler's name | "the" + ordinal word ("henry the eighth") |
| Arabic numbers | stay digits; ordinals stay `18th` |
| Abbreviation ending in a dot | expanded to its word (TERM-4 table, extended below); the dot is not a sentence end |
| Brackets `[ ]` `( )` | silent; content read; editorial-only brackets follow class 8 |
| Reused maths wordings | `*` after a form is "star" (§3c `x^*`); `°` "degrees" (ING-6); `/` between numbers keeps §3c "over" except in the contexts listed in section 3 |
| Lower case | the spoken column is lower case, as in `math_speech.jsonl`; names are cased by the backend's lexicon, not by the text |

## 1. What a teacher does

A history or law lecturer never reads the apparatus symbol by symbol: "Henry VIII" is "Henry the
Eighth", "c. 1500" is "circa fifteen hundred", "Roe v. Wade" is "Roe versus Wade" in an American
classroom and "R v Smith" is "the Crown against Smith" in an English one. Citation machinery (ibid., pp.,
fol. 12r, Hdt. 7.228) is expanded into the words it abbreviates ("pages", "folio 12 recto", "Herodotus,
book 7, chapter 228") or, when it adds nothing for a listener, passed over quickly with a pause. Quoted
sources are framed so the student knows where the quotation starts and ends, and editorial marks ([sic],
[emphasis added]) are said as a short aside. A student listening without the page must hear: who and
which ruler, when (with era and approximation), where in a source a passage sits, and whose words are
being quoted; they must never hear raw letters ("vee eye eye eye", "pee pee", "ess dee") or symbol names
that belong to maths ("is less than", "over") where the text meant "derived from" or "shillings".

## 2. Notation classes

### 2.1 Regnal and ordinal numbers, Roman numerals in other roles (`regnal`)

- **Detection**: a Roman numeral token (I–MMM, upper case) directly after a capitalised name from a ruler
  list or after a capitalised word that is itself preceded by a title (King, Queen, Pope, Emperor, Tsar,
  Pharaoh, Sultan, Shah) or followed by a possessive. Structural Roman numerals (after chapter, part,
  vol., ch., act, book, canto, war, phase) keep today's rule. Extraction artefacts: small caps flattened
  to lower case (`Henry viii`), the numeral split from a trailing full stop (`VIII.`), possessive
  `XIV's`, French ordinals `XXe` / `XIXe siècle`, letter I confused with digit 1 or `l` in OCR (`Henry Vlll`).
- **Rule**: ruler + Roman → name + "the" + ordinal word. Structural word + Roman → cardinal word.
  `WWII` / `WW2` / `World War II` → "world war two". `XXe siècle` → "20th century" in English narration
  (the French ordinal suffix `e` = `-ième`). A lone `I` after a name is regnal only when the name is in
  the ruler list and the next token is not a verb (`Elizabeth I died` vs `Then I said`).
- **Wording table**

| Pattern | Spoken |
| --- | --- |
| `Henry VIII` | henry the eighth |
| `Louis XIV's` | louis the fourteenth's |
| `Pope John XXIII` | pope john the twenty-third |
| `Elizabeth II` | elizabeth the second |
| `Ramesses II` | ramesses the second |
| `Vol. III`, `vol. iii` | volume three |
| `ch. IV` | chapter four |
| `Act II` | act two |
| `WWII`, `World War II` | world war two |
| `XXe siècle` | 20th century |

- **Source**: Wiktionary "VIII" (numeral = eighth, especially in names of monarchs and popes); pronounce.tv
  "Henry VIII" ("Henry the eighth"); structural rule = today's normalizer (result 871).
- **Confidence**: sourced (regnal ordinal); structural reading sourced from existing behaviour; French
  `XXe` proposed.

### 2.2 Dates and eras (`date`)

- **Detection**: a number of 1–4 digits followed or preceded by an era token (`BC`, `BCE`, `AD`, `CE`,
  `AH`, `BP`, `AUC`), with or without dots (`B.C.`, `A.D.`); the abbreviations `c.`, `ca.`, `circa`,
  `fl.`, `r.`, `d.`, `b.` directly before a year or year range (often inside parentheses after a name);
  decades `1960s`, `'20s` (curly apostrophe `’20s` from extraction); `18th c.`; ranges with en dash,
  hyphen or a flattened minus `1914−18`. Extraction artefacts: small-caps era `bc`/`ad`, `c.1500` with
  no space, the en dash lost (`1914 18`).
- **Rule**: era tokens are spelled letter by letter (SYN-4 already spells `BC`, `BCE`; keep, do not
  expand to "before Christ"). `c.`/`ca.` → "circa"; `fl.` → "flourished"; `r.` → "reigned"; `d.` → "died";
  `b.` → "born"; only before a year or range. `18th c.` → "18th century". Abbreviated second year in a
  range is completed from the first. `'20s` → "the twenties" (the century is unknown, so it cannot be
  written as digits); `1960s` stays.
- **Wording table**

| Pattern | Spoken |
| --- | --- |
| `480 BC`, `480 B.C.` | 480 b c |
| `AD 79` | a d 79 |
| `31 BCE` | 31 b c e |
| `1445 AH` | 1445 a h |
| `c. 814`, `ca. 814`, `c.814` | circa 814 |
| `(r. 768–814)` | reigned 768 to 814 |
| `(fl. 731)` | flourished 731 |
| `(b. 1770, d. 1827)` | born 1770, died 1827 |
| `1914–18` | 1914 to 1918 |
| `the '20s` | the twenties |
| `18th c.` | 18th century |
| `4th millennium BCE` | 4th millennium b c e |

- **Source**: Chicago Manual of Style era abbreviations and `c.`/`fl.`/`r.` (CMOS 10.39–10.41, from
  knowledge, unverified in this task); spoken expansion proposed.
- **Confidence**: proposed (no source prescribes the spoken form; the expansions are the Latin/English
  words the abbreviations stand for).

### 2.3 Scholarly citation apparatus (`citation`)

- **Detection**: `ibid.`, `Ibid.`, `op. cit.`, `loc. cit.`, `idem`, `id.`, `passim`, `et seq.`, `cf.`,
  `p.`/`pp.` before a number or range, `ff.`/`f.` after a page, `n.`/`nn.` before a number, `fol.`/`fols.`/`f.`
  + number + `r`/`v`, `MS`/`MSS`, `s.v.`, `q.v.`, `vol.`/`no.`, archival shelfmarks (`BL Add. MS 4793`,
  `TNA SP 1/105`). Artefacts: the dot lost after `pp` at a line end, `ff` ligature U+FB00 (`ﬀ.`),
  footnote-reference digits glued to the preceding word (`claim.12`), superscript footnote numbers split
  onto their own line.
- **Rule**: expand per TERM-4 (the PRD already lists ibid., op. cit., cf., et seq.). Footnote-reference
  digits glued to a word are dropped (as numeric citations are in ING-6). A shelfmark is read token by
  token: known collection prefixes expand (`Add.` "additional"), capitals spelled by SYN-4, numbers as digits.
- **Wording table**

| Pattern | Spoken |
| --- | --- |
| `ibid.` | ibid (lexicon respelling, section 4); configurable expansion "the same source" |
| `op. cit.` | in the work cited |
| `loc. cit.` | in the place cited |
| `idem`, `id.` | the same author |
| `passim` | passim (lexicon) |
| `et seq.` | and following |
| `cf.` | compare |
| `p. 12`, `pp. 12–15` | page 12, pages 12 to 15 |
| `pp. 12 ff.` / `p. 12 f.` | pages 12 and following / page 12 and the next |
| `n. 3`, `nn. 3–5` | note 3, notes 3 to 5 |
| `fol. 12r`, `fols. 12v–13r` | folio 12 recto, folios 12 verso to 13 recto |
| `MS`, `MSS` | manuscript, manuscripts |
| `s.v. "virtus"` | under the word virtus |
| `q.v.` | which see |
| `vol. 2, no. 3` | volume 2, number 3 |
| `BL Add. MS 4793` | b l additional manuscript 4793 |

- **Source**: TERM-4 (PRD); Latin meanings of the abbreviations (Chicago 14.34 "ibid.", from knowledge);
  spoken forms proposed.
- **Confidence**: proposed (expansions follow the Latin meaning; no style guide prescribes speech).

### 2.4 Classical and scripture references (`classical_ref`, `scripture_ref`)

- **Detection**: an author or work abbreviation from the Oxford Classical Dictionary list (`Hom.`, `Il.`,
  `Od.`, `Hdt.`, `Thuc.`, `Pl.`, `Rep.`, `Arist.`, `Eth. Nic.`, `Verg.`, `Aen.`, `Cic.`, `Liv.`, `Tac.`, `Ann.`)
  followed by dotted numbers `1.1`, `7.228`, or a Stephanus/Bekker locus `514a`, `1094a1`; a book of the
  Bible (SBL abbreviations `Gen`, `Exod`, `Matt`, `1 Cor`, `Ps`) or a full book name followed by `N:N`
  (`John 3:16`, `3:16–18`); `Q 2:255` (Qur'an sura:verse); a play title + `N.N.N` (act.scene.line);
  `ll.`/`l.` before line numbers. Artefacts: the colon replaced by a ratio sign `∶` or a period
  (`John 3.16`, British style), `1 Cor` split across lines, en dash lost.
- **Rule**: dotted numbers in a classical citation are never decimals: name the levels the work uses
  (Homer, Virgil: book, line; Herodotus, Thucydides, Livy: book, chapter; Shakespeare: act, scene, line;
  Dante: canto, line). Expand the author and work abbreviations by the table. Stephanus/Bekker loci read
  as number then letter ("514 a"; Bekker "1094 a 1"). Scripture: book name, "chapter", "verse(s)".
  `Q N:N` → "quran, sura N, verse N".
- **Wording table**

| Pattern | Spoken |
| --- | --- |
| `Hom. Il. 1.1–5` | homer, iliad, book 1, lines 1 to 5 |
| `Hdt. 7.228` | herodotus, book 7, chapter 228 |
| `Thuc. 2.40.1` | thucydides, book 2, chapter 40, section 1 |
| `Plato Rep. 514a` | plato, republic 514 a |
| `Arist. Eth. Nic. 1094a1` | aristotle, nicomachean ethics 1094 a 1 |
| `Aen. 6.851` | aeneid, book 6, line 851 |
| `John 3:16` | john, chapter 3, verse 16 |
| `John 3:16–18` | john, chapter 3, verses 16 to 18 |
| `Gen 1:1`, `Gen. 1.1` | genesis, chapter 1, verse 1 |
| `1 Cor 13:4` | first corinthians, chapter 13, verse 4 |
| `Q 2:255` | quran, sura 2, verse 255 |
| `Hamlet 3.1.56` | hamlet, act 3, scene 1, line 56 |
| `ll. 10–12`, `l. 5` | lines 10 to 12, line 5 |

- **Source**: Oxford Classical Dictionary abbreviation list and SBL Handbook book abbreviations (from
  knowledge; not fetched); Wikipedia "Stephanus pagination" and proofed.com (page + section letter);
  reading-in-church guidance (LMAP training page: separate chapter and verse with words so two numbers
  are not confused).
- **Confidence**: sourced (scripture "chapter … verse"; Stephanus number-plus-letter structure); level
  names per author proposed (they follow each edition's own divisions).

### 2.5 Legal citations (`legal`)

- **Detection**: `v.` / `v` / `vs.` between two capitalised party names in a sentence or italic run;
  `R v`, `R. v.`; reporter shapes `410 U.S. 113 (1973)`, `F. Supp. 2d`, `Cal. 3d`, `F.3d`, `S. Ct.`;
  neutral citations `[2019] UKSC 41`, `[2001] EWCA Civ 1`; `§`, `§§`, `¶`, `Art.`, `r`, `s`, `ss`, `reg.`
  before numbers; codes `U.S.C.`, `C.F.R.`; regnal-year statutes `28 Hen. 8 c. 10`. Artefacts: `§` lost
  as `S` or `$` in OCR, `¶` as `P`, the year bracket read as a numeric citation (result 870 line 11).
- **Rule**: `v.` by jurisdiction (document setting, default US): US "versus"; England and Wales civil
  "and", criminal (party `R`, `The Queen`, `The King`, `DPP`) "against"; Scotland "against". `R` as a
  party → "the crown". `§` "section", `§§` "sections", `¶` "paragraph", `Art. 3(2)` "article 3, paragraph
  2", UK statute `s 3(2)` "section 3, subsection 2", `r 4.1` "rule 4.1". Reporter abbreviations: spelled
  by SYN-4 unless in a reporter table (`F. Supp. 2d` "f supp second"). A neutral citation's bracketed year
  is never dropped as a citation (ING-11 rule exception: four-digit year alone in brackets followed by a
  court code). Regnal-year statute: "28 henry 8, chapter 10".
- **Wording table**

| Pattern | Spoken |
| --- | --- |
| `Roe v. Wade` (US) | roe versus wade |
| `R v Smith` (E&W) | the crown against smith |
| `Smith v Jones` (E&W civil) | smith and jones |
| `410 U.S. 113 (1973)` | 410 u s 113, 1973 |
| `42 U.S.C. § 1983` | 42 u s c section 1983 |
| `§§ 2–4` | sections 2 to 4 |
| `¶ 12` | paragraph 12 |
| `Art. 3(2)` | article 3, paragraph 2 |
| `s 3(2)` (UK statute) | section 3, subsection 2 |
| `r 4.1` | rule 4.1 |
| `[2019] UKSC 41` | 2019 u k s c 41 |
| `F. Supp. 2d` | f supp second |
| `28 Hen. 8 c. 10` | 28 henry 8, chapter 10 |

- **Source**: Wikipedia "Case citation" (Commonwealth civil "and", criminal "against", Scotland
  "against", US "versus"); Wikipedia "Section sign" (§ "section", §§ "sections"); Rebecca Jowers, US/UK
  case citation.
- **Confidence**: sourced (`v.`, `§`, `§§`); `¶`, `Art.`, reporters, regnal statutes proposed.

### 2.6 Names with particles, honorifics, diacritics, classical names (`name`)

- **Detection**: particles `de`, `van`, `van der`, `von`, `al-`, `ibn`, `bin`, `ben`, `Mac`/`Mc`, `Ó`/`O'`,
  `d'`; diacritics (`Ó`, `ñ`, `ø`, `ł`, `ğ`); Latinised and Greek names (`-es`, `-eus`, `-ae` endings).
  Artefacts: combining diacritics split from the base letter (`O´`), `ﬁ`/`ﬂ` ligatures inside names,
  hyphen at a line break inside `al-Ghazali`.
- **Rule**: no text rewrite; NFC-normalise, rejoin ligatures (already ING), and route the name to the
  TERM-1 lexicon (section 4). Honorifics expand: `St.` before a name "saint", `Fr.` "father", `Abp.`
  "archbishop", `Bp.` "bishop".
- **Wording table**

| Pattern | Spoken |
| --- | --- |
| `St. Augustine` | saint augustine |
| `Abp. Laud` | archbishop laud |
| `Thucydides` | thucydides (lexicon) |
| `al-Ghazālī` | al-ghazali (lexicon) |

- **Source**: proposed (BBC Pronunciation Unit practice of per-name respelling, from knowledge).
- **Confidence**: proposed.

### 2.7 Historical money, weights and measures; military designations; coordinates (`money_measure`, `military`, `coordinates`)

- **Detection**: `£N Ns Nd`, `Ns. Nd.`, `N/-`, `N/N` after a currency cue (cost, paid, price, wage) ;
  `gns`, `livres`, `talents`, `denarii`, `drachmae`; `oz`, `lb`, `cwt`, `st`, `yd`, `ft` after a number;
  `HMS`, `USS`, `SS`; `Bn`, `Bde`, `Div.`, `Regt`, `Coy`; four-digit times `0600`, `1430` after "at" or
  before "hours"/"hrs"; `51°30′N 0°7′W`. Artefacts: prime `′` as apostrophe `'`, the degree sign as
  superscript `o` (`51o`), `d.` = pence colliding with `d.` = died.
- **Rule**: £sd as "N pounds N shillings and N pence"; `N/-` "N shillings"; `2/6` with currency cue
  "2 shillings and 6 pence" (else §3c "over"). Imperial units by name, plural unless 1 (MATH-3 style).
  Ship prefixes spelled (SYN-4). Unit abbreviations expand. A four-digit time in military context
  "oh six hundred hours" (exception to the digits rule: the backend would say "six hundred"; words
  written out). Coordinates: degrees, minutes (not "prime"), seconds, and the compass word.
- **Wording table**

| Pattern | Spoken |
| --- | --- |
| `£3 4s 6d` | 3 pounds 4 shillings and 6 pence |
| `5s.` | 5 shillings |
| `10/-` | 10 shillings |
| `2/6` (currency cue) | 2 shillings and 6 pence |
| `3 gns` | 3 guineas |
| `12 oz`, `1 lb`, `3 cwt` | 12 ounces, 1 pound, 3 hundredweight |
| `HMS Victory` | h m s victory |
| `3rd Bn`, `2nd Bde`, `51st Div.` | 3rd battalion, 2nd brigade, 51st division |
| `at 0600`, `0600 hrs` | at oh six hundred hours |
| `1430 hours` | fourteen thirty hours |
| `51°30′N 0°7′W` | 51 degrees 30 minutes north, 0 degrees 7 minutes west |

- **Source**: primaryresources.co.uk £sd worksheet ("one pound, 2 (shillings) and 6 (pennies)");
  1900s.org.uk and joyceproject.com on £sd notation; todaysmilitary.com and editorsmanual.com on
  military time ("oh/zero six hundred hours").
- **Confidence**: sourced (£sd order, military time); coordinates and unit expansions proposed.

### 2.8 Quotation apparatus and editorial marks (`editorial`)

- **Detection**: `[sic]`, `[sic!]`, `[...]`, `[…]`, `. . .`, `[emphasis added]`, `[emphasis in original]`,
  `[italics mine]`, square-bracket insertions inside a quotation (`[the king]`), `&c.`, `&`, long s `ſ`,
  `ye`/`yͤ` (thorn), `u`/`v` and `i`/`j` interchange, ING-3 block quotation blocks. Artefacts: `ſ` OCR'd as
  `f` ("fome" for "some", cannot be fixed safely), ellipsis as three separate periods, brackets lost.
- **Rule**: `[sic]` "sic" as a brief aside (pause before and after); ellipsis in any form is a pause, never
  spoken; `[emphasis added]` "emphasis added" as an aside; an editorial insertion is read without the
  brackets; `&c.` "et cetera"; `&` "and"; `ſ` folded to `s` before synthesis; archaic spellings left as
  written (a teacher reads "kyng" as "king" but rewriting needs a historical lexicon; proposed TERM-1). A
  block quotation is opened with "quote" and closed with "end quote" (a teacher's habit; proposed, and a
  setting, since it repeats in heavily quoted texts).
- **Wording table**

| Pattern | Spoken |
| --- | --- |
| `[sic]` | sic |
| `[...]`, `[…]`, `. . .` | (pause) |
| `[emphasis added]` | emphasis added |
| `[the king]` | the king |
| `&c.` | et cetera |
| `Smith & Sons` | smith and sons |
| `ſome` | some |
| block quotation | quote … end quote |

- **Source**: proposed (search found no audiobook or style guide prescribing spoken editorial marks; see
  section 7, search 5).
- **Confidence**: proposed.

### 2.9 Philosophy and literature notation (`philosophy_lit`)

- **Detection**: Kant `A51/B75`, `A 51 / B 75`, `KrV`, `Ak. 4:421` (Akademie volume:page);
  Wittgenstein `TLP 4.1`, `PI §43`; Bible versions `KJV`, `NRSV`; Shakespeare `F1`, `Q2`; Dante `Inf. V.100`,
  `Purg.`, `Par.`; `st.` stanza, `canto`. Artefacts: the slash lost, `A51` glued.
- **Rule**: Kant A/B: "a 51, b 75" (letter spelled, then number); `Ak. 4:421` "akademie edition volume 4,
  page 421"; work abbreviations expand by table; TLP decimal numbers stay as written (read "4.1" as the
  backend reads decimals: "4 point 1", which is how the propositions are cited aloud); `PI §43`
  "philosophical investigations, section 43"; `F1` "the first folio", `Q2` "the second quarto" only in a
  Shakespeare context (else spelled); Dante canto Roman numeral cardinal ("canto 5").
- **Wording table**

| Pattern | Spoken |
| --- | --- |
| `KrV A51/B75` | critique of pure reason, a 51, b 75 |
| `Ak. 4:421` | akademie edition volume 4, page 421 |
| `TLP 4.1` | tractatus 4.1 |
| `PI §43` | philosophical investigations, section 43 |
| `F1`, `Q2` (Shakespeare) | the first folio, the second quarto |
| `Inf. V.100` | inferno, canto 5, line 100 |
| `KJV` | k j v |

- **Source**: Kant A/B pagination and TLP numbering conventions (from knowledge, not fetched); proposed.
- **Confidence**: proposed.

### 2.10 Linguistics and languages (`linguistics`)

- **Detection**: IPA between slashes or square brackets containing IPA characters (`/ˈwɔːtə/`,
  `[ˈwɔːɾɚ]`); a leading asterisk on a word or clause (`*the cats is`, PIE `*wódr̥`); `>` and `<` between
  forms (`*kʷ > p`, `Lat. pater < PIE *ph₂tḗr`); interlinear gloss abbreviations `3SG.PRS`, `NOM`, `ACC`;
  language abbreviations `Lat.`, `Gk.`, `OE`, `ME`, `PIE`, `Fr.`. Artefacts: IPA stress marks lost or
  mapped to apostrophes, subscript ₂ flattened to `2` (`h2`), combining ring under `r̥` dropped.
- **Rule**: an IPA span is not read glyph by glyph: it is spoken as the sound it transcribes, by passing
  the span to the backend as phonemes (TTSBackend hook; Kokoro already consumes IPA-like phonemes), with
  a fallback "the form" + nothing; a leading `*` is "star" (reuse §3c `x^*` "x star") before the form,
  i.e. "star the cats is" (proposed: linguists also say "asterisk"); `>` between forms "becomes", `<`
  "from" (never "is greater than"/"is less than": result 871 shows today's reading "greater than");
  gloss abbreviations expand ("third person singular present"); language abbreviations expand.
- **Wording table**

| Pattern | Spoken |
| --- | --- |
| `/ˈwɔːtə/` | (the sound, via phonemes) |
| `*the cats is` | star the cats is |
| `*kʷ > p` | star k w becomes p |
| `pater < PIE *ph₂tḗr` | pater from p i e star p h 2 ter |
| `3SG.PRS` | third person singular present |
| `Lat.`, `Gk.`, `OE` | latin, greek, old english |

- **Source**: proposed (Leipzig Glossing Rules abbreviations, from knowledge).
- **Confidence**: proposed.

## 3. Context rules and ambiguities

| Ambiguity | What decides it | Who decides |
| --- | --- | --- |
| `v.` = versus / and / against / verse / volume | between two party names → legal (jurisdiction setting); after a Bible book or before a number in scripture → "verse"; `vv.` "verses" | sentence + new per-document jurisdiction setting |
| Roman `I` = pronoun or "the first"; `V`, `X`, `C`, `L`, `D`, `M` = letter or numeral | previous token in ruler list / structural word; following token a verb | sentence |
| `d.` = died / pence | before a year → died; after a number with £ or s → pence | sentence |
| `c.` = circa / chapter (statute) / century | before a year → circa; after `Hen. 8` or a statute → chapter; after an ordinal → century | sentence |
| `/` = over / shillings-and-pence / Kant edition separator / or | currency cue → £sd; `A…/B…` → separator; maths span → §3c "over" | sentence + ING-11 (`math` profile keeps "over") |
| `<` `>` = relations / derived-from / becomes | inside a maths span or with a number on one side → §3c; between word forms with `*` or language tags → linguistics | ING-11 span + sentence |
| `*` = star (maths) / ungrammatical / reconstructed / footnote | before a word at clause start → star; after a word with a footnote marker below → drop | sentence |
| `′` = prime / minutes of arc | after `°` with N/S/E/W → minutes | sentence |
| `[2019]` = numeric citation / neutral citation year | four-digit year in brackets followed by a court code → keep | ING-6 citation rule exception |
| `N.N` = decimal / book.chapter / TLP number | after a classical or work abbreviation → levels; TLP → as decimal | sentence + abbreviation table |
| `Q2` = Qur'an sura 2 / second quarto | `Q N:N` → Qur'an; Shakespeare context → quarto | sentence + document profile (field) |
| `0600` = number / time | "at"/"hours"/"hrs" cue → military time | sentence |
| UK vs US conventions (v., dates, s 3(2)) | document locale | new per-document setting; ING-11 could carry a `field` (history, law, classics, linguistics) and `jurisdiction` guess from the citation style it already detects |

## 4. Pronunciation lexicon needs (TERM-1)

| Term | Respelling |
| --- | --- |
| ibid | IB-id |
| sic | SIK |
| passim | PASS-im |
| circa | SUR-kuh |
| et seq | et SEK |
| recto / verso | REK-toh / VUR-soh |
| folio | FOH-lee-oh |
| Thucydides | thoo-SID-ih-deez |
| Herodotus | heh-ROD-uh-tus |
| Xerxes | ZURK-seez |
| Aristophanes | air-ih-STOF-uh-neez |
| Thermopylae | thur-MOP-ih-lee |
| Aeneid | ih-NEE-id |
| Louis (French kings) | LOO-ee |
| Ramesses | RAM-uh-seez |
| Charlemagne | SHAR-luh-mayn |
| al-Ghazali | al-gah-ZAH-lee |
| Ó Súilleabháin | oh SOOL-uh-vawn |
| van der Weyden | van der VY-den |
| Goethe | GUR-tuh |
| livres | LEE-vruh |
| denarii | dih-NAIR-ee-eye |
| Qur'an | kuh-RAHN |
| Tractatus | trak-TAY-tus |
| akademie | ah-kah-deh-MEE |
| Stephanus | STEF-uh-nus |
| Bekker | BEK-er |
| habeas corpus | HAY-bee-us KOR-pus |
| certiorari | sur-shee-uh-RAIR-eye |
| mens rea | menz REE-uh |

## 5. Example pairs

```jsonl
{"id": "history_01", "class": "regnal", "raw": "Henry VIII broke with Rome.", "spoken": "henry the eighth broke with rome.", "block": "paragraph"}
{"id": "history_02", "class": "regnal", "raw": "Louis XIV's court", "spoken": "louis the fourteenth's court", "block": "paragraph"}
{"id": "history_03", "class": "regnal", "raw": "Pope John XXIII convened the council.", "spoken": "pope john the twenty-third convened the council.", "block": "paragraph"}
{"id": "history_04", "class": "regnal", "raw": "Elizabeth II", "spoken": "elizabeth the second", "block": "paragraph"}
{"id": "history_05", "class": "regnal", "raw": "Vol. III, ch. IV", "spoken": "volume three, chapter four", "block": "paragraph"}
{"id": "history_06", "class": "regnal", "raw": "after WWII", "spoken": "after world war two", "block": "paragraph"}
{"id": "history_07", "class": "date", "raw": "The battle (480 BC) preceded Actium (31 BCE).", "spoken": "the battle, 480 b c, preceded actium, 31 b c e.", "block": "paragraph"}
{"id": "history_08", "class": "date", "raw": "Charlemagne (r. 768–814)", "spoken": "charlemagne, reigned 768 to 814", "block": "paragraph"}
{"id": "history_09", "class": "date", "raw": "Bede (fl. 731)", "spoken": "bede, flourished 731", "block": "paragraph"}
{"id": "history_10", "class": "date", "raw": "c. 1500", "spoken": "circa 1500", "block": "paragraph"}
{"id": "history_11", "class": "date", "raw": "the war of 1914–18", "spoken": "the war of 1914 to 1918", "block": "paragraph"}
{"id": "history_12", "class": "date", "raw": "in the '20s and the 1960s", "spoken": "in the twenties and the 1960s", "block": "paragraph"}
{"id": "history_13", "class": "date", "raw": "the 18th c.", "spoken": "the 18th century", "block": "paragraph"}
{"id": "history_14", "class": "date", "raw": "AD 79", "spoken": "a d 79", "block": "paragraph"}
{"id": "history_15", "class": "citation", "raw": "Ibid., pp. 12–15.", "spoken": "ibid, pages 12 to 15.", "block": "paragraph"}
{"id": "history_16", "class": "citation", "raw": "cf. Smith, op. cit., n. 3", "spoken": "compare smith, in the work cited, note 3", "block": "paragraph"}
{"id": "history_17", "class": "citation", "raw": "BL Add. MS 4793, fol. 12r", "spoken": "b l additional manuscript 4793, folio 12 recto", "block": "paragraph"}
{"id": "history_18", "class": "citation", "raw": "pp. 40 ff.", "spoken": "pages 40 and following", "block": "paragraph"}
{"id": "history_19", "class": "citation", "raw": "s.v. \"virtus\"", "spoken": "under the word \"virtus\"", "block": "paragraph"}
{"id": "history_20", "class": "classical_ref", "raw": "Hom. Il. 1.1–5", "spoken": "homer, iliad, book 1, lines 1 to 5", "block": "paragraph"}
{"id": "history_21", "class": "classical_ref", "raw": "Hdt. 7.228", "spoken": "herodotus, book 7, chapter 228", "block": "paragraph"}
{"id": "history_22", "class": "classical_ref", "raw": "Plato Rep. 514a", "spoken": "plato, republic 514 a", "block": "paragraph"}
{"id": "history_23", "class": "classical_ref", "raw": "Aen. 6.851", "spoken": "aeneid, book 6, line 851", "block": "paragraph"}
{"id": "history_24", "class": "scripture_ref", "raw": "John 3:16", "spoken": "john, chapter 3, verse 16", "block": "paragraph"}
{"id": "history_25", "class": "scripture_ref", "raw": "1 Cor 13:4–7", "spoken": "first corinthians, chapter 13, verses 4 to 7", "block": "paragraph"}
{"id": "history_26", "class": "scripture_ref", "raw": "Q 2:255", "spoken": "quran, sura 2, verse 255", "block": "paragraph"}
{"id": "history_27", "class": "classical_ref", "raw": "Hamlet 3.1.56", "spoken": "hamlet, act 3, scene 1, line 56", "block": "paragraph"}
{"id": "history_28", "class": "legal", "raw": "Roe v. Wade, 410 U.S. 113 (1973)", "spoken": "roe versus wade, 410 u s 113, 1973", "block": "paragraph"}
{"id": "history_29", "class": "legal", "raw": "R v Smith", "spoken": "the crown against smith", "block": "paragraph"}
{"id": "history_30", "class": "legal", "raw": "42 U.S.C. § 1983", "spoken": "42 u s c section 1983", "block": "paragraph"}
{"id": "history_31", "class": "legal", "raw": "§§ 2–4 and ¶ 12", "spoken": "sections 2 to 4 and paragraph 12", "block": "paragraph"}
{"id": "history_32", "class": "legal", "raw": "Art. 3(2)", "spoken": "article 3, paragraph 2", "block": "paragraph"}
{"id": "history_33", "class": "legal", "raw": "[2019] UKSC 41", "spoken": "2019 u k s c 41", "block": "paragraph"}
{"id": "history_34", "class": "legal", "raw": "28 Hen. 8 c. 10", "spoken": "28 henry 8, chapter 10", "block": "paragraph"}
{"id": "history_35", "class": "money_measure", "raw": "He paid £3 4s 6d for 12 oz of silver.", "spoken": "he paid 3 pounds 4 shillings and 6 pence for 12 ounces of silver.", "block": "paragraph"}
{"id": "history_36", "class": "money_measure", "raw": "a fee of 10/-", "spoken": "a fee of 10 shillings", "block": "paragraph"}
{"id": "history_37", "class": "military", "raw": "the 3rd Bn landed at 0600", "spoken": "the 3rd battalion landed at oh six hundred hours", "block": "paragraph"}
{"id": "history_38", "class": "coordinates", "raw": "51°30′N 0°7′W", "spoken": "51 degrees 30 minutes north, 0 degrees 7 minutes west", "block": "paragraph"}
{"id": "history_39", "class": "editorial", "raw": "\"The kyng [sic] came [...] to London &c.\"", "spoken": "\"the kyng, sic, came to london et cetera.\"", "block": "paragraph"}
{"id": "history_40", "class": "editorial", "raw": "\"he must go\" [emphasis added]", "spoken": "\"he must go\", emphasis added", "block": "paragraph"}
{"id": "history_41", "class": "philosophy_lit", "raw": "KrV A51/B75", "spoken": "critique of pure reason, a 51, b 75", "block": "paragraph"}
{"id": "history_42", "class": "philosophy_lit", "raw": "Inf. V.100", "spoken": "inferno, canto 5, line 100", "block": "paragraph"}
{"id": "history_43", "class": "philosophy_lit", "raw": "PI §43", "spoken": "philosophical investigations, section 43", "block": "paragraph"}
{"id": "history_44", "class": "linguistics", "raw": "*the cats is", "spoken": "star the cats is", "block": "paragraph"}
{"id": "history_45", "class": "linguistics", "raw": "Latin *kʷ > p", "spoken": "latin star k w becomes p", "block": "paragraph"}
```

## 6. Where it hooks in YomiKoe (proposal)

| Class | Hook |
| --- | --- |
| regnal | ING-6 prose normalizer: extend the `_STRUCTURAL` Roman rule with a ruler-name list → ordinal words |
| date | ING-6 (era letters stay to SYN-4; `c.`/`fl.`/`r.`/`d.`/`b.` before a year; range completion) |
| citation | TERM-4 expansion table (extend with pp., n., fol., MS, s.v., q.v.); footnote-digit drop in ING-6 |
| classical_ref, scripture_ref | ING-6 with two data tables (OCD author/work abbreviations with level names; SBL book list) |
| legal | ING-6 + new per-document setting `jurisdiction` (US / England and Wales / Scotland); ING-11 citation-rule exception for `[YYYY] COURT N` |
| name | TERM-1 lexicon; honorific expansion in TERM-4 table |
| money_measure, military, coordinates | ING-6 (currency-cue £sd, imperial units like MATH-3 units, military time with cue, coordinates before `_speak_symbols` reads `′` as prime) |
| editorial | ING-6 (brackets, ellipsis, `&c.`, `ſ` fold); block-quote cue in the reader's segment assembly (ING-3 block type) as a setting |
| philosophy_lit | ING-6 + TERM-4 work table (KrV, TLP, PI, Inf.) |
| linguistics | IPA span → TTSBackend phoneme input (new); `*`, `>`, `<` between word forms in ING-6 before `_speak_symbols`; gloss table in TERM-4 |
| all | ING-11 profile gains an optional `field` (history, law, classics, linguistics) to switch the ambiguous readings in section 3 |

## 7. Sources

| URL | What it establishes |
| --- | --- |
| https://en.wikipedia.org/wiki/Case_citation | Commonwealth "v" read "and" (civil) / "against" (criminal), Scotland "against", US "versus"; R v Smith "the Crown against Smith" |
| https://rebeccajowers.com/2016/06/04/legal-english-in-the-us-and-uk-2/ | US/UK difference in reading case names aloud |
| https://en.wikipedia.org/wiki/Section_sign | § spoken "section", §§ "sections" (§§ 13–21 "sections 13 through 21") |
| https://pronounce.tv/word/henry-viii | "Henry VIII" spoken "Henry the eighth" |
| https://wiki.neonvagabond.xyz/content/wiktionary_en_all_nopic_2024-05/A/VIII. | VIII = eighth, especially in names of monarchs and popes |
| https://sites.google.com/lmap.org.au/gathering-support/training/reading-the-bible-in-church | put words between chapter and verse numbers so listeners do not confuse them |
| https://reformedworship.org/resource/reading-scripture-public-worship | announce the reference before reading |
| https://www.primaryresources.co.uk/maths/docs/pounds_shillings_pence.doc | £1 2s 6d read "one pound, 2 shillings and 6 pence" (order and "and") |
| https://www.1900s.org.uk/1900s-coins-writing.htm | £ s d written and spoken forms (not opened; cited by search summary) |
| https://joyceproject.com/notes/010019money.htm | £4 3s. 10d. notation |
| https://www.todaysmilitary.com/life-in-the-military/customs-practices/alphabet-time | whole hours "hundred" ("eleven hundred hours") |
| https://editorsmanual.com/articles/time-24-hour-clock/ | 06:00 "oh six hundred" / "zero six hundred" |
| https://en.wikipedia.org/wiki/Stephanus_pagination | Plato cited by page + section letter a–e |
| https://proofed.com/writing-tips/citing-plato-and-aristotle-stephanus-and-bekker-numbers/amp | Stephanus and Bekker number shapes |

Searches with no usable result: [sic]/ibid read aloud in narration (search 5): no source; class 8 stays
proposed. Not consulted (budget): Chicago, MHRA, MLA, OSCOLA, Bluebook, SBL Handbook, OCD list, ClearSpeak/
MathSpeak, NVDA/JAWS, DAISY/NISO, BBC Pronunciation Unit; any statement attributed to them above is from
knowledge and unverified.

## 8. Open questions for the supervisor

1. Digits rule exceptions: regnal ordinals as words ("the eighth"), "the twenties", "oh six hundred hours".
   Accept as exceptions, or ask the backend's `num2words` shim to speak ordinals and times instead?
2. Years: does the backend read `1914` as "nineteen fourteen"? Not probed here (unverified); if not, every
   history text sounds wrong, which is bigger than any class above.
3. `ibid.`: TERM-4 says expand; a teacher says "ibid". Default to the word, expansion as option?
4. Jurisdiction for `v.`: a per-document setting, or inferred from citation shape (`[2019] UKSC` → E&W)?
5. Block quotation "quote … end quote": on by default for humanities profiles, or a setting only?
6. IPA spans to the backend as phonemes: a new TTSBackend method, or skip IPA with a short cue?
7. Should ING-11 gain a `field` label (history/law/classics/linguistics), or should these rules run in
   every profile (most are unambiguous outside maths spans)?
8. Footnote-reference digits glued to words (`claim.12`): drop in all profiles, matching numeric citations?
