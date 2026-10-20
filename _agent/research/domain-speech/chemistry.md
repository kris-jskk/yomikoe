# Chemistry notation read aloud: a teacher's reading convention for HearNarro

Task domain-speech-chemistry, 2026-10-19. Research note for the supervisor; it proposes, it does not decide.
It follows the shape of spec §3c (`_agent/specs/m5-academic-reading.md`, lines 305-475): lower case, one
wording per symbol, numbers stay digits (the backend's `num2words` speaks them), punctuation is prosody only
(a comma is a pause, never the word "comma"). Where chemistry reuses a maths symbol, §3c's wording is reused
(`·` "dot", `/` "over", `=` "equals", Greek by name, Greek capitals "capital ...", `′` "prime", `*` "star").
Today's behaviour is in `_agent/results/850_chemistry_probe_today.txt` (15 strings: 0 correct, 6 wrong,
9 symbol leaked) and `_agent/results/851_chemistry_decimal_probe.txt`.

## 1. What a teacher does

In class a chemist reads a formula symbol by symbol and count by count: CH4 + 2 O2 → CO2 + 2 H2O is
"C H 4 plus 2 O 2 reacts to form C O 2 plus 2 H 2 O" (a chemistry professor, relayed on the W3C MathML list;
"It is always H 2 O", Soiffer and Moore on the W3C chemistry list). Element names ("hydrogen", "iron") are
used when talking about the substance, and the formula itself is read as letters, never as "cap" or
"subscript" (W3C threads; MathCAT speaks element symbols as bare letters). Charges are said after the
formula ("N A plus", "S O 4, 2 minus"), state symbols are said as words ("aqueous", "gas"), arrows as verbs
("reacts to form", "is in equilibrium with"), square brackets around a species as "the concentration of".
What the student must hear to follow without the page: which letters belong to one element (Co versus C O),
where a count ends and a charge begins (SO4 2−), and where the reactant side ends (the arrow verb). The
silent reader sees all three from typography; the listener needs letters, digits and a short pause.

## 2. Notation classes

Confidence: **sourced** = a cited source prescribes or records this reading; **proposed** = no source
prescribes it, chosen here for consistency with §3c and with common classroom usage (unverified by a source).

### 2.1 Molecular and empirical formulas (incl. hydrates and grouping)

- **Detection.** A token made only of element symbols (capital, optional lower-case letter from the 118-element
  list), digits, `( )` `[ ]` and `·`, with at least one digit or at least two element symbols, not a dictionary
  word (H2O, C6H12O6, NaCl, Ca(OH)2, [Cu(NH3)4]2+). Artefacts: subscripts flattened to the baseline (`H2O`,
  the normal case); subscripts split off with a space (`H 2 O`, `C 6 H 12 O 6`); the hydrate dot extracted as
  `•`, `∙`, `⋅`, `.` or `×`; ligatures inside names next to a formula (`ﬂuoride`).
- **Rule.** Letters lower case, one per letter, a two-letter symbol as its two letters (`Na` "n a"); counts as
  digits after the letter; a leading coefficient as a digit; a parenthesized group read silently with its
  multiplier after it ("o h, 2" is ambiguous with OH2, so a group multiplier carries a pause: "c a, o h, 2");
  the hydrate dot is §3c "dot". MATH-3 already fixes `H2O` "h 2 o".
- **Wording table.**

| Pattern | Spoken |
| --- | --- |
| `H2O` | h 2 o |
| `C6H12O6` | c 6 h 12 o 6 |
| `NaCl` | n a c l |
| `2H2O` (coefficient) | 2 h 2 o |
| `Ca(OH)2` | c a, o h, 2 |
| `(CH3)3CH` | c h 3, 3, c h |
| `[Cu(NH3)4]2+` | c u, n h 3, 4, 2 plus |
| `CuSO4·5H2O` | c u s o 4 dot 5 h 2 o |

- **Source.** W3C MathML4 2020-10 thread (professor's "see aitch four plus two oh two"); W3C chem 2022-08
  ("It is always H 2 O"); spec §3c (MATH-3). Group multiplier pause and hydrate "dot": proposed.
- **Confidence.** Letters and counts sourced; grouping pause and hydrate dot proposed.

### 2.2 Charges and ions

- **Detection.** A formula followed by `+`, `−`, `-`, `2+`, `3−`, superscript `⁺ ⁻ ²⁺`, or a split-off charge
  (`SO4 2-`, `Na +`). Artefacts: superscript charge fused onto a count (`SO42−`, probe line 04, read "SO42
  minus"); minus extracted as hyphen (`Cl-`); `+` lost entirely when set in a superscript font.
- **Rule.** Charge after the formula: magnitude digit then "plus" or "minus"; a pause (comma) before a charge
  that follows a count. A fused `SO42−` is split by a polyatomic-ion table (SO4, PO4, CO3, NO3, NH4, ...):
  the known ion's count is kept and the trailing digit is the charge (proposed).
- **Wording table.**

| Pattern | Spoken |
| --- | --- |
| `Na+` | n a plus |
| `Cl−`, `Cl-` | c l minus |
| `Fe3+` | f e 3 plus |
| `SO4 2−`, `SO42−`, `SO₄²⁻` | s o 4, 2 minus |
| `H3O+` | h 3 o plus |
| `[M+H]+` (mass spectrum) | m plus h, plus |

- **Source.** MathCAT `general.yaml` (pause after a `+`/`-` superscript; it voices no "plus"); classroom
  "Fe three plus" is common usage (unverified). **Confidence.** proposed (wording), sourced (pause).

### 2.3 Oxidation states

- **Detection.** Roman numeral in parentheses right after an element name or symbol (`iron(III)`, `Fe(III)`,
  `Cu(I)`), or a superscript Roman numeral flattened onto the symbol (`FeIII`, `Fe^{II}`).
- **Rule.** Roman numeral read as a cardinal digit after the name or letters; "0" for `(0)`; a sign if written
  (`(−II)` "minus 2").
- **Wording table.**

| Pattern | Spoken |
| --- | --- |
| `iron(III) chloride` | iron 3 chloride |
| `Fe(III)` | f e 3 |
| `Cu(I)` | c u 1 |
| `Mn(VII)` | m n 7 |
| `FeIIIFeII2O4` (flattened superscripts) | f e 3, f e 2, 2, o 4 |

- **Source.** IUPAC Stock notation (Wikipedia "IUPAC nomenclature of inorganic chemistry") fixes the
  written form; the spoken cardinal is classroom usage. **Confidence.** proposed.

### 2.4 Isotopes and nuclides

- **Detection.** A mass number glued before an element symbol (`14C`, `235U`, `2H`, `18O`), superscript or
  flattened; a nuclide with both numbers (`¹⁴₆C`, flattened `146C`, ambiguous); hyphenated name form
  (`carbon-14`); `D` for deuterium, `T` tritium.
- **Rule.** Element name then mass number ("carbon 14"); hyphenated name form the same; an atomic number,
  when given, is dropped (it is implied by the element) unless the document is nuclear physics (open).
- **Wording table.**

| Pattern | Spoken |
| --- | --- |
| `14C`, `¹⁴C`, `carbon-14`, `C-14` | carbon 14 |
| `235U` | uranium 235 |
| `2H`, `D` (as isotope label) | hydrogen 2 / d |
| `¹⁴₆C` | carbon 14 |
| `13C NMR` | carbon 13 n m r |

- **Source.** W3C chem 2022-08/10 threads: nuclides spoken by the element name; one proposal there read the
  mass number first ("forty potassium"). Name-then-number is the common "carbon 14" (unverified by source).
- **Confidence.** proposed (order); sourced (name not letters).

### 2.5 Reaction equations: arrows, conditions, state symbols, coefficients

- **Detection.** Two formula sides joined by `→ ⟶ -> ⇌ ⇄ ⇋ <=> ←`; Symbol-font artefacts: `→` extracted as
  `®`, `⇌` as `D` pairs or private-use glyphs; condition text above the arrow extracted on the line above or
  after the arrow (`Δ`, `hν`, `Pd/C`, `H2SO4 (cat.)`); state symbols `(s) (l) (g) (aq)` glued to formulas.
- **Rule.** `+` between species "plus"; `→` "reacts to form"; `⇌` `⇄` `<=>` "is in equilibrium with";
  `←` "is formed from"; `↔` (resonance) "is a resonance form of". A condition is read after the arrow verb,
  "with" + condition, between pauses: `Δ` "heat", `hν` "light"; reagents read by their own rules. State
  symbols as words. Inside a reaction, `→` never takes §3c's "approaches" or "to".
- **Wording table.**

| Pattern | Spoken |
| --- | --- |
| `→`, `->`, `⟶` (between formulas) | reacts to form |
| `⇌`, `⇄`, `<=>` | is in equilibrium with |
| `←` | is formed from |
| `↔` (resonance) | is a resonance form of |
| `—Δ→` | reacts to form, with heat, |
| `—hν→` | reacts to form, with light, |
| `(s)` `(l)` `(g)` `(aq)` | solid, liquid, gas, aqueous |
| `↑` / `↓` after a product | gas / precipitate |

- **Source.** MathCAT `general.yaml`: "reacts to form" (terse "forms"), "is in equilibrium with", states
  "solid / liquid / gas / aqueous"; W3C professor's "reacts to form". `←`, `↔`, conditions, `↑ ↓`: proposed.
- **Confidence.** sourced (→, ⇌, states); proposed (rest).

### 2.6 Thermodynamic and equilibrium quantities

- **Detection.** `ΔH`, `ΔG°`, `ΔS`, `ΔrH°`, `ΔfH⦵`, `Keq`, `Kc`, `Kp`, `Ka`, `Kb`, `Kw`, `Ksp`, `pKa`, `pH`,
  `pOH`, `E°cell`. Artefacts: `Δ` from Symbol font as `D`; standard-state `°`/`⦵` flattened to `o` (`ΔHo`);
  subscripts flattened (`Ksp`); minus as hyphen in values.
- **Rule.** `Δ` is §3c "capital delta"; the standard-state mark `°` `⦵` after a quantity is "naught";
  equilibrium-constant subscripts read as letters with no "sub" (classroom "K s p"); `p` operator read as the
  letter ("p h", "p k a").
- **Wording table.**

| Pattern | Spoken |
| --- | --- |
| `ΔH` | capital delta h |
| `ΔG°`, `ΔG⦵`, `ΔGo` | capital delta g naught |
| `ΔrH°` | capital delta r h naught |
| `Keq`, `K_eq` | k e q |
| `Ksp`, `Ka`, `Kw` | k s p, k a, k w |
| `pKa`, `pH`, `pOH` | p k a, p h, p o h |
| `E°cell` | e naught cell |

- **Source.** §3c (capital delta). "naught" and letter reading of K subscripts: classroom usage, proposed.
- **Confidence.** proposed. Departs from §3c `x_i` "x sub i" for K subscripts (open question 2).

### 2.7 Concentrations and units

- **Detection.** Number then `M`, `mM`, `µM` (U+00B5) or `μM` (U+03BC), `nM`, `mol/L`, `mol L−1`, `mol dm−3`,
  `ppm`, `ppb`, `% w/v`, `% v/v`, `equiv`, `eq.`, `kJ/mol`, `kJ mol−1`, `kcal/mol`, `cal`, `J K−1 mol−1`.
  Artefacts: `−1`/`−3` exponents flattened with a hyphen (`dm-3`), µ as `m` from font loss.
- **Rule.** §3c units: prefix + unit word, plural unless the value is 1; a negative exponent unit is "per";
  `dm−3` "per cubic decimeter"; `M` after a number is "molar" (not "moles"); `ppm` "p p m".
- **Wording table.**

| Pattern | Spoken |
| --- | --- |
| `0.1 M` | 0.1 molar |
| `5 mM`, `20 µM`, `3 nM` | 5 millimolar, 20 micromolar, 3 nanomolar |
| `mol/L`, `mol L−1` | moles per liter |
| `mol dm−3` | moles per cubic decimeter |
| `kJ/mol`, `kJ mol−1` | kilojoules per mole |
| `J K−1 mol−1` | joules per kelvin per mole |
| `1715 cm−1` | 1715 per centimeter |
| `5 ppm` | 5 p p m |
| `10% w/v`, `5% v/v` | 10 percent weight per volume, 5 percent volume per volume |
| `1.2 equiv` | 1.2 equivalents |

- **Source.** IUPAC Gold Book "amount concentration" (unit mol dm−3, `M` as shorthand); `M` pronounced
  "molar" (Wikipedia, secondary); §3c units. "per centimeter" for cm−1 is proposed (chemists also say
  "wavenumbers" or "reciprocal centimeters").
- **Confidence.** sourced (molar, units); proposed (cm−1, ppm, w/v).

### 2.8 IUPAC nomenclature: locants, stereodescriptors, prefixes

- **Detection.** Digit locants joined by hyphens and commas inside a name (`2-methylpropan-2-ol`,
  `1,2-dichloroethane`); parenthesized descriptors `(R)-`, `(S)-`, `(E)-`, `(Z)-`, `(R,S)-`, `(±)-`; `cis-`,
  `trans-`, `D-`, `L-`, `α-`, `β-`; heteroatom locants `N-`, `O-`, `S-`; primes `5′`, `3′` (often `5'`);
  `tert-`, `sec-`, `iso-`, `n-`, `neo-`; italics lost in extraction.
- **Rule.** Hyphens are silent; locant digits as digits; a comma between locants is a pause; a descriptor
  letter read as a lower-case letter; Greek prefix by name; prime "prime" (§3c); `n-` "n"; `tert-`, `sec-` as
  words (lexicon); `(±)` "racemic" (proposed).
- **Wording table.**

| Pattern | Spoken |
| --- | --- |
| `2-methylpropan-2-ol` | 2 methylpropan 2 ol |
| `1,2-dichloroethane` | 1, 2 dichloroethane |
| `(R)-2-butanol` | r 2 butanol |
| `(E)-but-2-ene` | e but 2 ene |
| `cis-2-butene` | cis 2 butene |
| `α-D-glucose` | alpha d glucose |
| `β-carotene`, `α-helix` | beta carotene, alpha helix |
| `5′-phosphate` | 5 prime phosphate |
| `N-methylaniline`, `O-acetyl` | n methylaniline, o acetyl |
| `tert-butyl`, `sec-butyl`, `n-butyl` | tert butyl, sec butyl, n butyl |
| `(±)-ibuprofen` | racemic ibuprofen |

- **Source.** IUPAC Blue Book written forms (not read); spoken forms are classroom usage. **Confidence.**
  proposed.

### 2.9 Group and reagent abbreviations

- **Detection.** Two- or three-letter mixed-case group tokens next to a formula or name (`Me Et Pr iPr Bu tBu
  Ph Bn Bz Ac Ts Ms Tf Boc Cbz Fmoc TMS TBS`), and all-caps reagent and solvent acronyms (`THF DMSO DMF LDA
  DCM DIBAL NBS mCPBA DMAP TFA`), and formula-shaped reagents (`NaBH4 LiAlH4 MeOH EtOH Et3N`).
- **Rule.** Group symbols expand to the group name (they are read that way in class); all-caps acronyms
  follow SYN-4 (spelled when not pronounceable, which gives "t h f", "d m s o", "l d a"), with lexicon entries
  for the few said as words; formula reagents follow 2.1, except `MeOH`, `EtOH` read as "methanol",
  "ethanol" (proposed).
- **Wording table.**

| Pattern | Spoken |
| --- | --- |
| `Me`, `Et`, `Pr`, `Bu`, `Ph` | methyl, ethyl, propyl, butyl, phenyl |
| `iPr`, `tBu`, `t-Bu` | isopropyl, tert butyl, tert butyl |
| `Bn`, `Bz`, `Ac`, `Ts`, `Tf` | benzyl, benzoyl, acetyl, tosyl, triflyl |
| `Boc`, `Fmoc` | boc, f moc (lexicon) |
| `THF`, `DMSO`, `LDA`, `DCM` | t h f, d m s o, l d a, d c m |
| `DIBAL` | dye-bal (lexicon) |
| `mCPBA` | m c p b a |
| `NaBH4`, `LiAlH4` | n a b h 4, l i a l h 4 |
| `MeOH`, `EtOH`, `Et3N` | methanol, ethanol, triethylamine |

- **Source.** ACS / JOC standard abbreviation lists (meanings; Reich acronym list); spoken forms proposed.
- **Confidence.** proposed.

### 2.10 Spectroscopy and analysis data

- **Detection.** `1H NMR` / `¹H NMR` / `13C{1H} NMR`, `(400 MHz, CDCl3)`, `δ 7.26 (d, J = 8.0 Hz, 2H)`,
  multiplicity letters `s d t q m dd dt br s`, `IR (neat) ν 1715 cm−1`, `m/z 180.0634 [M+H]+`, `HRMS (ESI)`,
  `λmax 254 nm`, `UV–vis`, `92% ee`, `dr 10:1`, `Rf 0.3`, `mp 120–122 °C`, yields `85%`.
- **Rule.** Read in data order; nucleus label as "proton" for `1H`, element + mass for others; multiplicity
  letters expand to words only inside a `δ (...)` data group; `J =` "j equals"; `2H` integral "2 h"; `m/z`
  §3c slash "m over z"; ratios `10:1` "10 to 1"; `Rf` "r f"; `mp` "melting point"; ranges "to".
- **Wording table.**

| Pattern | Spoken |
| --- | --- |
| `1H NMR`, `¹H NMR` | proton n m r |
| `13C NMR` | carbon 13 n m r |
| `CDCl3` | c d c l 3 |
| `δ 7.26` | delta 7.26 |
| `s`, `d`, `t`, `q`, `m` (in δ data) | singlet, doublet, triplet, quartet, multiplet |
| `dd`, `br s` | doublet of doublets, broad singlet |
| `J = 8.0 Hz` | j equals 8.0 hertz |
| `2H` (integral) | 2 h |
| `m/z` | m over z |
| `λmax` | lambda max |
| `UV–vis` | u v vis |
| `92% ee`, `dr 10:1` | 92 percent e e, d r 10 to 1 |
| `mp 120–122 °C` | melting point 120 to 122 degrees celsius |

- **Source.** NMR meaning of multiplicity, J and integration (Widener NMR pages); "proton NMR" is classroom
  usage; spoken forms proposed. **Confidence.** proposed.

### 2.11 Electron configurations and orbitals

- **Detection.** Sequences of `<n><s|p|d|f><count>` (`1s2 2s2 2p6`, `[Ne] 3s1`, `[Ar] 3d10 4s2`) with the
  superscript count flattened; hybrid `sp`, `sp2`, `sp3`, `dsp2`; `σ`, `π`, `σ*`, `π*`, `n→π*`; `HOMO`, `LUMO`.
- **Rule.** Each orbital term as digit, letter, digit with a pause between terms (the count is the electron
  number, not a power; classroom "one s two"); a noble-gas core in brackets "neon core"; hybrid "s p 3";
  `*` "star" (§3c); `n→π*` "n to pi star" (§3c "to" between labels).
- **Wording table.**

| Pattern | Spoken |
| --- | --- |
| `1s2 2s2 2p6`, `1s²2s²2p⁶` | 1 s 2, 2 s 2, 2 p 6 |
| `[Ne] 3s1` | neon core, 3 s 1 |
| `[Ar] 3d10 4s2` | argon core, 3 d 10, 4 s 2 |
| `sp3`, `sp2` | s p 3, s p 2 |
| `π*`, `σ*` | pi star, sigma star |
| `n→π*` | n to pi star |
| `HOMO`, `LUMO` | homo, lumo (SYN-4 spoken) |

- **Source.** proposed (classroom). **Confidence.** proposed; departs from §3c powers ("s squared") on
  purpose (open question 3).

### 2.12 Rate laws, equilibrium expressions and named equations

- **Detection.** Square brackets around a formula or a single capital letter in an equation
  (`rate = k[A]2[B]`, `Kc = [NH3]2/([N2][H2]3)`, `[H+]`); Arrhenius `k = A e−Ea/RT`; Nernst
  `E = E° − (RT/nF) ln Q`; Henderson–Hasselbalch `pH = pKa + log([A−]/[HA])`.
- **Rule.** A bracketed species is "the concentration of" (never §3c's interval); adjacent bracket factors
  take "times" (§3c's rule for bracketed factors); a flattened power after `]` is §3c "squared"/"cubed"/"to
  the n" preceded by the group-closing comma; `Ea` "e a"; the rest is §3c.
- **Wording table.**

| Pattern | Spoken |
| --- | --- |
| `[A]` | the concentration of a |
| `[H+]` | the concentration of h plus |
| `k[A]2[B]` | k times the concentration of a, squared, times the concentration of b |
| `k = A e−Ea/RT` | k equals a e to the minus e a over r t |
| `E = E° − (RT/nF) ln Q` | e equals e naught minus r t over n f natural log q |
| `pH = pKa + log([A−]/[HA])` | p h equals p k a plus log the concentration of a minus over the concentration of h a |

- **Source.** §3c (powers, slash, ln); "the concentration of": proposed. **Confidence.** proposed.

### 2.13 Element symbols in prose, and bonds

- **Detection.** A capitalised one- or two-letter element symbol standing alone in prose or a figure label
  (`the Na atom`, `C–H bond`, `C=O`, `C≡N`); bond dashes extracted as hyphens or en dashes.
- **Rule.** Standing symbols read as letters (as formulas); a bond between symbols: `–` "single bond"
  only when it stands alone in a structure (in prose `C–H bond` the dash is silent: "c h bond"); `=` "double
  bond", `≡` "triple bond".
- **Wording table.**

| Pattern | Spoken |
| --- | --- |
| `C–H bond` | c h bond |
| `C=O` | c double bond o |
| `C≡N` | c triple bond n |
| `the Na atom` | the n a atom |

- **Source.** MathCAT `general.yaml` bond words ("single bond", "double bond", "triple bond");
  W3C (letters). **Confidence.** sourced (bond words, letters); proposed (silent dash in prose).

## 3. Context rules and ambiguities

What decides the reading:

1. **Formula versus word.** `CO` (carbon monoxide) versus "Co" (cobalt) versus "CO" (Colorado, an acronym);
   `NO`, `I`, `In`, `As`, `At`, `Be`, `He`, `Am`, `No`, `Hf`, `Mg`. A token is a formula only with a digit,
   a charge, a state symbol, a neighbouring formula, an arrow, or a chemistry document profile. Needs the
   sentence and the profile.
2. **Count versus charge in a fused superscript.** `SO42−`, `PO43−`: decided by a polyatomic-ion table;
   ambiguous otherwise (`X42−`). Needs data, not the sentence.
3. **`→` reaction versus limit versus mapping.** Formulas on both sides: "reacts to form"; a limit or
   `n → ∞`: §3c "approaches"; `n→π*` transition label: "to". Needs the span.
4. **Square brackets.** Concentration (`[A]`, `[H+]`), coordination complex (`[Cu(NH3)4]2+`, silent),
   noble-gas core (`[Ne]`), citation (`[12]`, ING-6/ING-11), interval (§3c). A bracket that contains only a
   formula or one capital letter inside an equation with `k`, `K`, `rate`: concentration; at the start of a
   configuration: core; followed by a charge: complex.
5. **`M`.** After a number: molar; in `[M+H]+`: the molecule "m"; alone in maths: a variable.
6. **`d`, `s`, `t`, `m`, `q`.** Multiplicity only inside a `δ (...)` group; `d` also deuterium, D-sugar,
   d orbital; `s` also seconds and s orbital.
7. **`2H`.** Integral "2 h" in NMR data; deuterium "hydrogen 2" before NMR or a formula.
8. **`°`.** Degree after a number (ING-6 "degrees"); "naught" after a thermodynamic quantity.
9. **`Δ`.** "capital delta" before a quantity; "heat" as an arrow condition.
10. **Decimal digits.** `180.0634` is read digit by digit today (probe 851); exact masses need the normal
    decimal reading.

What ING-11 could decide: a `chemistry` class (share of formula tokens, arrows between formulas, NMR data
groups, unit tokens M/mM) would switch on 2.1-2.13 and the formula reading of ambiguous tokens (1, 5, 6)
document-wide; a `prose` document keeps "CO" as an acronym unless a digit or charge marks it. What needs the
sentence: 1, 3, 4, 7, 9.

## 4. Pronunciation lexicon needs (TERM-1)

Terms the voice mispronounces even when spelled correctly (respelling in plain English syllables, stress
capitalised; to be converted to the backend's phoneme form by the TERM-1 author; all unverified against
Kokoro until an EVAL-4 run):

| Term | Respelling | Term | Respelling |
| --- | --- | --- | --- |
| tert | TURT | sec (prefix) | SECK |
| ene (suffix, as read alone) | EEN | yne | INE |
| propan (in propan-2-ol) | PRO-pan | -ol (suffix alone) | OLL |
| vis (UV–vis) | VIZ | naught | NAWT |
| DIBAL | DYE-bal | Fmoc | EF-mock |
| Boc | BOCK | tosyl | TOE-sill |
| triflyl | TRY-flill | mesyl | MEZ-ill |
| aqueous | AY-kwee-us | amine | uh-MEEN |
| ligand | LIG-und | chelate | KEE-late |
| enthalpy | EN-thal-pee | entropy | EN-truh-pee |
| Hasselbalch | HAS-ul-balk | Nernst | NAIRNST |
| Arrhenius | uh-REE-nee-us | Le Chatelier | luh SHAT-ul-yay |
| Lewis | LOO-is | Brønsted | BRUN-sted |
| Diels–Alder | DEELZ ALL-der | Grignard | green-YAR |
| Friedel–Crafts | FREE-del KRAFTS | Wittig | VIT-ig |
| Hückel | HUE-kel | Kekulé | KECK-oo-lay |
| zwitterion | TSVIT-er-eye-on | anomer | AN-uh-mer |
| cis | SIS | trans | TRANZ |
| ipso | IP-so | meso | MEE-zo |
| HOMO | HOE-mo | LUMO | LOO-mo |
| DMSO (if spoken as word, variant) | dim-SO | racemic | ray-SEE-mik |

## 5. Example pairs

```jsonl
{"id": "chemistry_01", "class": "formula", "raw": "Water (H2O) was added.", "spoken": "water (h 2 o) was added.", "block": "paragraph"}
{"id": "chemistry_02", "class": "formula", "raw": "C6H12O6", "spoken": "c 6 h 12 o 6", "block": "paragraph"}
{"id": "chemistry_03", "class": "formula", "raw": "NaCl dissolves in water.", "spoken": "n a c l dissolves in water.", "block": "paragraph"}
{"id": "chemistry_04", "class": "formula", "raw": "Ca(OH)2", "spoken": "c a, o h, 2", "block": "paragraph"}
{"id": "chemistry_05", "class": "formula", "raw": "CuSO4·5H2O", "spoken": "c u s o 4 dot 5 h 2 o", "block": "paragraph"}
{"id": "chemistry_06", "class": "formula", "raw": "[Cu(NH3)4]2+", "spoken": "c u, n h 3, 4, 2 plus", "block": "paragraph"}
{"id": "chemistry_07", "class": "charge", "raw": "Na+ and Cl− ions", "spoken": "n a plus and c l minus ions", "block": "paragraph"}
{"id": "chemistry_08", "class": "charge", "raw": "The sulfate ion SO42− is tetrahedral.", "spoken": "the sulfate ion s o 4, 2 minus is tetrahedral.", "block": "paragraph"}
{"id": "chemistry_09", "class": "charge", "raw": "Fe2+ is oxidized to Fe3+.", "spoken": "f e 2 plus is oxidized to f e 3 plus.", "block": "paragraph"}
{"id": "chemistry_10", "class": "charge", "raw": "H3O+", "spoken": "h 3 o plus", "block": "paragraph"}
{"id": "chemistry_11", "class": "oxidation_state", "raw": "iron(III) chloride", "spoken": "iron 3 chloride", "block": "paragraph"}
{"id": "chemistry_12", "class": "oxidation_state", "raw": "Mn(VII) in permanganate", "spoken": "m n 7 in permanganate", "block": "paragraph"}
{"id": "chemistry_13", "class": "isotope", "raw": "Radiocarbon dating uses 14C.", "spoken": "radiocarbon dating uses carbon 14.", "block": "paragraph"}
{"id": "chemistry_14", "class": "isotope", "raw": "235U fission", "spoken": "uranium 235 fission", "block": "paragraph"}
{"id": "chemistry_15", "class": "reaction", "raw": "2H2(g) + O2(g) → 2H2O(l)", "spoken": "2 h 2 gas plus o 2 gas reacts to form 2 h 2 o liquid", "block": "equation"}
{"id": "chemistry_16", "class": "reaction", "raw": "N2 + 3H2 ⇌ 2NH3", "spoken": "n 2 plus 3 h 2 is in equilibrium with 2 n h 3", "block": "equation"}
{"id": "chemistry_17", "class": "reaction", "raw": "AgNO3(aq) + NaCl(aq) → AgCl(s) + NaNO3(aq)", "spoken": "a g n o 3 aqueous plus n a c l aqueous reacts to form a g c l solid plus n a n o 3 aqueous", "block": "equation"}
{"id": "chemistry_18", "class": "reaction", "raw": "CaCO3 —Δ→ CaO + CO2", "spoken": "c a c o 3 reacts to form, with heat, c a o plus c o 2", "block": "equation"}
{"id": "chemistry_19", "class": "thermo", "raw": "ΔH° = −92 kJ/mol", "spoken": "capital delta h naught equals minus 92 kilojoules per mole", "block": "paragraph"}
{"id": "chemistry_20", "class": "thermo", "raw": "ΔG = ΔH − TΔS", "spoken": "capital delta g equals capital delta h minus t capital delta s", "block": "equation"}
{"id": "chemistry_21", "class": "thermo", "raw": "The Ksp of AgCl is 1.8 × 10−10.", "spoken": "the k s p of a g c l is 1.8 times 10 to the minus 10.", "block": "paragraph"}
{"id": "chemistry_22", "class": "thermo", "raw": "acetic acid has a pKa of 4.76", "spoken": "acetic acid has a p k a of 4.76", "block": "paragraph"}
{"id": "chemistry_23", "class": "units", "raw": "a 0.1 M NaOH solution", "spoken": "a 0.1 molar n a o h solution", "block": "paragraph"}
{"id": "chemistry_24", "class": "units", "raw": "5 mM and 20 µM", "spoken": "5 millimolar and 20 micromolar", "block": "paragraph"}
{"id": "chemistry_25", "class": "units", "raw": "1.0 mol dm−3", "spoken": "1.0 moles per cubic decimeter", "block": "paragraph"}
{"id": "chemistry_26", "class": "units", "raw": "at pH 7.4", "spoken": "at p h 7.4", "block": "paragraph"}
{"id": "chemistry_27", "class": "units", "raw": "1.2 equiv of base in 10% w/v", "spoken": "1.2 equivalents of base in 10 percent weight per volume", "block": "paragraph"}
{"id": "chemistry_28", "class": "nomenclature", "raw": "2-methylpropan-2-ol", "spoken": "2 methylpropan 2 ol", "block": "paragraph"}
{"id": "chemistry_29", "class": "nomenclature", "raw": "(R)-2-butanol and (E)-but-2-ene", "spoken": "r 2 butanol and e but 2 ene", "block": "paragraph"}
{"id": "chemistry_30", "class": "nomenclature", "raw": "α-D-glucose and β-carotene", "spoken": "alpha d glucose and beta carotene", "block": "paragraph"}
{"id": "chemistry_31", "class": "nomenclature", "raw": "the 5′-phosphate", "spoken": "the 5 prime phosphate", "block": "paragraph"}
{"id": "chemistry_32", "class": "nomenclature", "raw": "1,2-dichloroethane", "spoken": "1, 2 dichloroethane", "block": "paragraph"}
{"id": "chemistry_33", "class": "abbreviation", "raw": "LDA in THF, then NaBH4 in MeOH", "spoken": "l d a in t h f, then n a b h 4 in methanol", "block": "paragraph"}
{"id": "chemistry_34", "class": "abbreviation", "raw": "the tBu ester and the OMe group", "spoken": "the tert butyl ester and the o methyl group", "block": "paragraph"}
{"id": "chemistry_35", "class": "spectroscopy", "raw": "1H NMR (400 MHz, CDCl3) δ 7.26 (d, J = 8.0 Hz, 2H)", "spoken": "proton n m r (400 megahertz, c d c l 3) delta 7.26 (doublet, j equals 8.0 hertz, 2 h)", "block": "paragraph"}
{"id": "chemistry_36", "class": "spectroscopy", "raw": "IR (neat) 1715 cm−1", "spoken": "i r (neat) 1715 per centimeter", "block": "paragraph"}
{"id": "chemistry_37", "class": "spectroscopy", "raw": "HRMS m/z 180.0634 [M+H]+", "spoken": "h r m s m over z 180.0634 (m plus h, plus)", "block": "paragraph"}
{"id": "chemistry_38", "class": "spectroscopy", "raw": "92% ee, λmax 254 nm", "spoken": "92 percent e e, lambda max 254 nanometers", "block": "paragraph"}
{"id": "chemistry_39", "class": "electron_configuration", "raw": "1s2 2s2 2p6", "spoken": "1 s 2, 2 s 2, 2 p 6", "block": "paragraph"}
{"id": "chemistry_40", "class": "electron_configuration", "raw": "an sp3 carbon and a π* orbital", "spoken": "an s p 3 carbon and a pi star orbital", "block": "paragraph"}
{"id": "chemistry_41", "class": "rate_law", "raw": "rate = k[A]2[B]", "spoken": "rate equals k times the concentration of a, squared, times the concentration of b", "block": "equation"}
{"id": "chemistry_42", "class": "rate_law", "raw": "Ksp = [Ag+][Cl−]", "spoken": "k s p equals the concentration of a g plus times the concentration of c l minus", "block": "equation"}
{"id": "chemistry_43", "class": "rate_law", "raw": "pH = pKa + log([A−]/[HA])", "spoken": "p h equals p k a plus log the concentration of a minus over the concentration of h a", "block": "equation"}
{"id": "chemistry_44", "class": "bond", "raw": "the C=O stretch", "spoken": "the c double bond o stretch", "block": "paragraph"}
```

Notes on the pairs: a sentence's first word is lower-cased as §3c requires of `spoken`; brackets in `raw`
NMR data are kept as prosody in `spoken` (EVAL-10 strips punctuation); chemistry_37 renders `[M+H]+` inside
parentheses only as a pause marker. `10−10` reads §3c "10 to the minus 10" (a flattened power; today's
normalizer says "10 minus 10", probe line 09).

## 6. Where it hooks in HearNarro (proposal)

| Class | Hook |
| --- | --- |
| 2.1 formulas | MATH-3 symbol table (formula letters and counts) plus a new formula detector in the prose normalizer (ING-6), gated by ING-11 |
| 2.2 charges | ING-6 normalizer, with a polyatomic-ion data table next to `math_symbols.py` |
| 2.3 oxidation states | ING-6 normalizer (Roman numeral after element name or symbol) |
| 2.4 isotopes | ING-6 normalizer plus an element-name table (118 rows, new data file) |
| 2.5 reactions | MATH-3 table (arrow verbs, state words) applied by mathspeak (MATH-1/2) in equation blocks and inline spans |
| 2.6 thermo constants | MATH-3 table (`°` "naught" in a quantity), ING-6 for `pH` `pKa` `Ksp` tokens |
| 2.7 units | MATH-3 unit table (molar prefixes, per-unit negative exponents) |
| 2.8 nomenclature | ING-6 normalizer (hyphen and locant rule) plus TERM-1 for tert, sec, ene |
| 2.9 abbreviations | new chemistry abbreviation table beside SYN-4 (group expansions); SYN-4 for all-caps acronyms; TERM-1 for DIBAL, Boc |
| 2.10 spectroscopy | ING-6 normalizer, a δ-data-group rule, gated by ING-11 |
| 2.11 configurations | MATH-3 / mathspeak rule for orbital terms, gated by ING-11 |
| 2.12 rate laws | mathspeak (MATH-1/2): bracket-as-concentration under a chemistry profile |
| 2.13 element symbols, bonds | MATH-3 table (bond words); ING-6 for standing symbols |
| profile | new ING-11 class `chemistry` (or a per-document "chemistry notation" setting) |

## 7. Sources

- https://raw.githubusercontent.com/NSoiffer/MathCAT/main/Rules/Languages/en/SharedRules/general.yaml —
  MathCAT's chemistry speech: "reacts to form" (terse "forms"), "is in equilibrium with", states "solid,
  liquid, gas, aqueous", "single/double/triple bond", a pause after a charge, "super"/"sub" for scripts (the
  last is banned by §3c, not adopted).
- https://lists.w3.org/Archives/Public/public-mathml4/2020Oct/0007.html — a chemistry professor's reading of
  CH4 + 2 O2 → CO2 + 2 H2O letter by letter with "reacts to form"; teachers use element names in discussion
  and letters in the equation; Supalo: units read as units.
- https://lists.w3.org/Archives/Public/public-chem-web-pub/2022Aug/0005.html — Soiffer and Moore: water is
  "always H 2 O", not "cap H subscript 2".
- https://lists.w3.org/Archives/Public/public-chem-web-pub/2022Oct/0000.html — MathCAT infers chemistry
  (H2O triggers, O2 does not); element symbols spoken as bare letters; nuclide naming discussion (search
  snippet only, page not opened).
- https://lists.w3.org/Archives/Public/public-chem-web-pub/2023Apr/att-0001/chemistry-page.html — W3C
  chemistry notation catalogue (classes covered: formulas, ions, isotopes, oxidation states, radicals,
  nuclides, reactions, precipitation, equilibrium, resonance); the speech column was not in the fetched page.
- https://docs.wiris.com/en_US/mathplayer-settings-dialog/speech-tab — MathPlayer offers three formula
  readings (spell out, compound names, as maths) (search snippet).
- https://goldbook.iupac.org/terms/view/A00295 — IUPAC Gold Book "amount concentration": unit mol dm−3 or
  mol L−1, `M` as a shorthand; "molarity" discouraged (search snippet).
- https://en.wikipedia.org/wiki/IUPAC_nomenclature_of_inorganic_chemistry — Stock notation for oxidation
  states (written form only) (search snippet).
- https://www.organicchemistrydata.org/hansreich/resources/acronyms/acronyms_data/acronyms.pdf and
  https://www.epfl.ch/labs/lcso/wp-content/uploads/2018/06/ACS-abbreviations.pdf — standard abbreviations
  (t-Bu, s-Bu, DMSO, THF) and their meanings; no spoken forms (search snippet).
- https://science.widener.edu/svb/nmr/citronellal/proton_int.html — NMR integration and multiplicity
  meaning (search snippet; spoken forms not given).

No source found prescribes spoken forms for charges, oxidation states, units like M or cm−1, nomenclature
locants, NMR data or electron configurations; those readings are marked proposed.

## 8. Open questions for the supervisor

1. Hydrate dot: keep §3c "dot" or use a pause only ("c u s o 4, 5 h 2 o")? Teachers also say the name
   ("copper sulfate pentahydrate"), which needs a name table.
2. K subscripts: "k s p" (classroom) or §3c "k sub s p" when the subscript survives extraction? One wording
   is required; this note proposes "k s p" for both.
3. Electron configurations: "1 s 2" (classroom, count) versus §3c "1 s squared" (power). Proposed "1 s 2".
4. Isotope order: "carbon 14" (proposed) or mass-first "14 c" (the W3C "forty potassium" proposal)?
5. Δ: §3c "capital delta h" versus classroom "delta h". This note keeps §3c.
6. Element symbols as letters versus names for formulas a teacher names ("water", "methanol"): only MeOH and
   EtOH are expanded here; a common-name table is possible but is a reading choice (MathPlayer exposes it as
   a setting).
7. Does chemistry get its own ING-11 class, or a per-document toggle like PLAY-8?
8. The decimal `180.0634` is read digit by digit today (851); is that an ING-6 rule for long decimals that
   chemistry needs to override, or a bug?
