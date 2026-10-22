# Cross-domain findings from the six domain-speech notes

Sources: probe files 850, 855, 860, 865, 870, 875 (and 851, 866, 871), the OBSERVATIONS of the six
reports in `_agent/reports/domain-speech-<domain>.md`, and the wording tables in the six notes
(`_agent/research/domain-speech/*.md`). Combined dataset: `domain_speech.jsonl` (278 pairs; check in
`_agent/results/885_domain_speech_jsonl_check.txt`). Wording grep: `_agent/results/886_wording_conflicts_grep.txt`.
Line cites are probe-file line numbers (verdict lines unless stated). "§3c" is the reading convention in
`api/scripts/math_convention.json`. All outputs are "today's normalize(s)[0]" at commit 0628324 (normalizer stage only).

## 1. Probe tally (15 strings each)

Counted from each file's verdict lines. "Wrong" includes the "wrong + symbol leaked" verdicts of physics; "leaked" is leaked only.

| Domain | Correct | Wrong | Symbol leaked | Source |
|---|---|---|---|---|
| chemistry | 0 | 6 | 9 | 850:51 (file's own tally) |
| physics | 1 | 7 | 7 | 855:53 (file's own tally; 7 are "wrong + symbol leaked") |
| biology | 0 | 9 | 6 | no tally line; 15 verdict lines counted (grep, 860) |
| finance | 1 | 7 | 7 | no tally line; 15 verdict lines counted (grep, 865) |
| history | 0 | 5 | 10 | no tally line; 15 verdict lines counted (870 lines 36-50) |
| cs_stats | 1 | 4 | 10 | 875:53 (file's own tally) |
| total | 3 | 38 | 49 | of 90 strings |

The finance report says "9 symbol leaked or wrong"; the file's verdict lines give 14 (7 + 7). The report figure is not used.

## 2. Defects of today's normalizer shown by two or more probes or reports

| # | Defect | Domains affected | Evidence (file:line) | §3c rule broken |
|---|---|---|---|---|
| D1 | `→` read "goes to" (reactions, nuclear decay, 5'→3') | chemistry, physics, biology | 850:42; 855:47, 855:48; 860:9 | banned `goes to` (arrows: approaches / to) |
| D2 | `∇` read "nabla" | physics, cs_stats | 855:44; 875:45 | banned `nabla` (use "del") |
| D3 | Capital Greek read as the lower-case name: Σ "sigma", Θ "theta", Δ "delta" | finance, cs_stats, chemistry, biology | 865:45; 875:38, 875:39; 850:43 (ΔH° "delta H°"); 860:15 (ΔF508 "delta F508") | `capital` prefix for capital Greek (biology note itself keeps "delta f 508", see conflict C5) |
| D4 | Ω as ohm read "omega" (`kΩ` becomes "k omega") | physics | 855:39, 855:49; physics report OBSERVATIONS | units: Ω = ohms |
| D5 | `p < 0.05` read "p less than 0.05", no "is" | biology, history, cs_stats | 860:42; 871:13; 875:48 (and ".05" leading dot, 875:48) | relations: `<` = "is less than" |
| D6 | `51°30′N` read "51 degrees30′N" (no space, prime leaks) | physics, history | 855:51; 871:11 | none (° is ING-6; ′ prime only) |
| D7 | Long decimal read digit by digit: `180.0634` becomes "1 8 0, 0 6 3 4" | chemistry (verified); history, cs_stats flag decimal risk (unverified) | 850:49; 851 (rows 1-2); 870:42 (7.228, unprobed); 875:43 (3.11, unprobed) | none (ING-6 decimal rule) |
| D8 | `[year]` dropped as a numeric citation; bracketed intervals at risk | history (verified); cs_stats flags `CI [1.2, 3.4]` (unverified) | 870:46; 875:49; history report OBSERVATIONS | none (ING-6 citation rule) |
| D9 | SYN-4 acronym choices disagree with usage: FTSE, SEC, AAPL, QOQ, TP53/WT/SD, NP, HMS/BC | finance (verified: 865 tail), biology (860:3), history (870:37, unverified), cs_stats (875:40, unverified), chemistry (850:46 acceptable) | 865 last two lines; 860:3; 870:37; 875:40 | none (SYN-4) |
| D10 | Superscript digit detached from or fused to its base: "SO42 minus", "chi ²(1)", "omega ²x", raw `p²`, `R²` "r two" | chemistry, physics, biology, finance, cs_stats | 850:39; 855:43; 860:45; 865:42; 875:50, 875:51 | scripts: `x^2` = "x squared" |
| D11 | `^` and `_` reach the voice raw (`10^6`, `10^8`, `N_A`, `^t`, `CF_t`, `argmax_k`) | physics, biology, finance, cs_stats | 855:41; 860:30; 865:45; 875:45 | scripts: "to the n", "sub" |
| D12 | Unicode sub/superscripts and combining accents unhandled (`R₁`, `₀`, `x̂`, `ŷ`, `σ̂²` "sigmâ²") | physics, cs_stats | 855:43, 855:44, 855:49; 875:45, 875:51 | scripts: hat, bar, sub |
| D13 | Units untouched in prose (`m/s²`, `GHz`, `mM`, `µg/mL`, `KiB`, `pp`) | chemistry, physics, biology, finance, cs_stats | 850:45; 855:37-41; 860:27; 865:21; 875:42 | units / units_rule (MATH-3) |
| D14 | `/` left raw outside a maths span (`120/80`, `D/E`, `y/y`, `cells/mL`, `A51/B75`) | biology, finance, history, cs_stats | 860:39; 865:24; 865:36; 870:50; 875:39 | fractions: `a/b` = "a over b" |
| D15 | En-dash year range drops the century (`2019-24` "2019 to 24", `1914-18` "1914 to 18") | finance, history | 865:27; 870:39 | none (ING-6 range rule) |
| D16 | Middle dot read "dot" inside hydrates and unit products | chemistry, physics | 850:38; 855:38 | operators: `·` = dot (applies to dot product only; context rule missing) |
| D17 | Negative exponent unit read "minus 1" (`cm−1` "cm minus 1", `dm−3`, `10−10`) | chemistry | 850:45, 850:49, chemistry report OBSERVATIONS | none (units rule: "per") |
| D18 | Arrows and pictographs outside the table leak or vanish: `⇌`, `←`, `↑`, `▲`, `~` | chemistry, cs_stats, finance | 850:43; 875:44, 875:52; 865:48; 875:51 (tilde) | arrows / relations: `~` = "distributed as" |
| D19 | Letter-digit tokens pass through unchanged (`H2O`, `Ca(OH)2`, `c.524G>A`, `17p13.1`, `0x1F`, `v2.3.1`) | chemistry, biology, cs_stats, finance | 850:36-37; 860:12, 860:18; 875:41, 875:43; 865:6 | chemistry_rule: letter by letter, counts as digits (chemistry only) |

Defects counted: 19. D7, D8 and D9 are verified in one domain and flagged (unverified) in a second; all other rows have two or more verified domains, except D4 and D17, which are single-domain verified (kept because the brief names Ω and the notes repeat them).

## 3. Symbols and patterns with different wordings across notes

| # | Symbol / pattern | Wordings (note proposing it) | §3c already fixes it? |
|---|---|---|---|
| C1 | `→` | "reacts to form" (chemistry 132, "yields" absent); "yields" (physics 251-253); "to" (biology 106 `5'→3'`; chemistry 294 `n→π*`); "approaches / to / yields" (physics 377) | Partly: approaches (limit), "to" (between sets). No reaction wording. |
| C2 | `⇌` | "is in equilibrium with" (chemistry 133); no other note | No |
| C3 | `/` | "per" in units (chemistry 181-185, physics 56-62, biology 191-192, 231-233); "over" (chemistry 269 m/z, 315-317; biology 232 `120/80`, 302; finance 222; cs_stats 54); "to" for `:` ratios (biology 201, finance 94); separator (history 359) | Partly: "over" fixed for fractions; "per" for units and "to" for ratios not in the JSON |
| C4 | `~` | "distributed as / about" (physics 373); "distributed as / about / home" (cs_stats 433) | Partly: "distributed as" yes; "about" before a number no |
| C5 | `Δ` | "capital delta" (chemistry 157-159, finance 171-172); "delta" with no "capital" (biology 133 `ΔF508`) | Yes: `capital` prefix; biology row departs from it (mutation name; decision needed) |
| C6 | `Ω` / `Θ` | "ohms/kilohms" (physics 64); "big omega / big theta" (cs_stats 49, 48); "capital theta/omega" or "big" offered as alternatives (cs_stats 420) | Yes for the letter ("capital omega"); "big" is not §3c; the ohm unit is in `units` |
| C7 | `×` | "times" (finance 90, biology 194-195, physics 128, chemistry 314); "cross" (physics 189-190); "by" (cs_stats 238 shapes, 342 `2 × 2`) | Partly: "times" only; "cross" and "by" are proposals (cs probe 875:45 says "B times T times D" matches §3c) |
| C8 | E-notation | "6.022 times 10 to the 23" (physics 130); "3 e minus 4" (cs_stats 76, 237) | No |
| C9 | `·` | "dot" (chemistry 51 hydrate; physics 188 dot product); silent in unit products, "newton meters" (physics 58-60) | Partly: `·` = "dot" only |
| C10 | Unit plurals and case | plural "300 kelvins", "9.8 meters" (physics 108, 109); singular after per ("joules per mole kelvin", physics 60); "1715 per centimeter" (chemistry 185); "degrees Celsius" capital C (physics 158, 311) vs "degrees celsius" (chemistry 273, biology 197) | Partly: plural unless 1, US spelling, K = kelvins; denominator form, "per" and case of Celsius not stated |
| C11 | Sentence case | physics `spoken` keeps capitals (15 pairs, see 885); the other five notes lower-case | Yes: spoken text is lower case (checker) |
| C12 | `′` | "prime" (biology 105-106, chemistry 215); "minutes" (physics 355-356, history 263) | Partly: `′` = "prime"; arc-minute context not stated |
| C13 | `°` | "degrees" (physics, biology, chemistry); "naught" in thermo (chemistry 158-159, 163) | Partly: degrees Celsius stays ING-6; "naught" not in the JSON |
| C14 | Sub/superscripts | "sub", "sup" for tensor indices (physics 192-193); "squared / cubed / to the n" for powers (physics 57, biology 301); "squared" read from a flattened digit after a bracket (chemistry 314) | Yes (scripts table); flattened superscripts need ING-3 font-size runs |
| C15 | `Σ` / `∑` | "capital sigma" (cs_stats 194 alphabet); "the sum over t of" (finance 222) | Yes: Σ capital sigma, ∑ "the sum" |
| C16 | `±` | "plus or minus" in all notes; chemistry 218 `(±)-ibuprofen` "racemic" | Yes for the operator; racemic is a context rule |

Conflicts counted: 16 rows (C1-C16). A grep for "change in" as a Δ wording returned no match in any note (886, last block), so the brief's "capital delta vs change in" conflict does not occur in the notes.

## 4. Convention-check result for the combined file

15 pairs, all in the physics note, fail the checker's "upper-case letters" rule only (ids in 885): physics_01, 03, 06, 07, 10, 18, 21, 22, 24, 31, 39, 44, 49, 53, 54. No banned wording or raw symbol is flagged in the other 263 pairs. See conflict C11.
