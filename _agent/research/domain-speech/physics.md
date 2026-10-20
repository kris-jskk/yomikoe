# Reading physics and engineering notation aloud (task domain-speech-physics, 2026-10-19)

Research note for the supervisor. It extends the maths reading convention (spec
`_agent/specs/m5-academic-reading.md` §3c, machine copy `api/scripts/math_convention.json`) to physics,
engineering, astronomy and geoscience notation. Same shape as §3c: one wording per symbol, lower case,
numbers stay digits (the backend's `num2words` shim speaks them), punctuation is prosody only. Where a
physics form reuses a maths symbol, §3c's wording is reused and marked "(§3c)". A wording is **sourced**
when a style guide or standard below prescribes it, **proposed** otherwise. Today's behaviour on 15 probe
strings is in `_agent/results/855_physics_probe_today.txt` (1 correct, 7 symbol leaked, 7 wrong and leaked).

## 1. What a teacher does

A physics teacher reads a quantity with its unit as one phrase ("nine point eight meters per second
squared"), never as letters ("m slash s two"); the unit is the part a listener most needs, because it
says what kind of quantity the number is. Symbols in an equation are read as letters ("f equals m a"),
and the teacher names the quantity ("force equals mass times acceleration") only when introducing a law
or when the symbol has just been defined; on the board the letters carry the meaning, but a listener
without the page needs the letters to match what the text uses next. Decorations that change meaning are
always said: hats ("x hat"), dots for time derivatives ("x dot"), arrows ("vector v"), daggers, bars on
antiparticles, kets ("ket psi"). Exponents of ten are said as powers ("three times ten to the eight"),
uncertainties as "plus or minus", and nuclides as element name plus mass number ("uranium 238"). Silent
reading tolerates symbol soup; listening does not, so every symbol must reach the voice as a word.

## 2. Notation classes

General rules carried from §3c: variables as lower-case letters; juxtaposition silent; `×` "times";
`·` "dot"; unary minus "minus"; `x_i` "x sub i"; `x²` "x squared", `xⁿ` "x to the n", `x^{−1}` "x to
the minus 1"; Greek by name; `x̂` "x hat"; `ẋ` "x dot"; `x⃗` "vector x"; `x^*` "x star"; `x^T` "x
transpose"; `∂` "partial"; `∇` "del" ("nabla" is banned); `a/b` "a over b"; `≈` "is approximately equal
to"; `∝` "is proportional to".

### 2.1 SI and derived units (prefixes, powers, quotients)

**Detection.** A number (digits, optional decimal, optional exponent) followed by a space or thin space
and a token from the unit table, optionally with a prefix, a power (`²`, `³`, `⁻¹`, `^2`, `-1`, `−2`),
a product (`·`, `⋅`, `.`, a space) or a quotient (`/`, `/( … )`). Also a unit token inside square
brackets in axis labels and table headers (`[m s⁻¹]`, `(kPa)`), and "in units of X". Extraction
artefacts: superscripts flattened to the baseline (`m/s2`, `m s-2`, `kg m-3`), minus as hyphen (`s-1`),
micro sign U+00B5 `µ` and Greek mu U+03BC `μ` both used, ohm sign U+2126 `Ω` and Greek capital omega
U+03A9 `Ω` both used, product dot as U+00B7, U+22C5 or a full stop, `deg` for `°`.

**Rule.** Prefix word plus unit word, written as one word (`kΩ` "kilohms"), US spelling, plural unless
the value is 1 (§3c units_rule). A product of units is the names separated by a space ("newton meters";
never "dot"); a quotient is "per" before each denominator unit; a positive power on a numerator unit of
length is "square"/"cubic" before it (`m²` "square meters"); a power after "per" or on any other unit
is "squared"/"cubed" after it (`m/s²` "meters per second squared"); a negative power is "per" plus the
unit (`s⁻¹` "per second", `K⁻⁴` "per kelvin to the 4"). The plural falls on the last unit word before
"per" ("newton meters", "kilogram meters per second", "joules per mole kelvin"), as in English. Unit symbols are never pluralised in the source, so `s` after a
number is always seconds. Mixed forms do not occur in speech: the whole unit expression is spoken as
names.

**Wording table.**

| Pattern | Spoken |
| --- | --- |
| `m/s`, `m s⁻¹`, `m s-1` | meters per second |
| `m/s²`, `m s⁻²`, `m/s2`, `m s-2` | meters per second squared |
| `kg·m/s`, `kg m s⁻¹` | kilogram meters per second |
| `N·m`, `N m` | newton meters |
| `J/(mol·K)`, `J mol⁻¹ K⁻¹` | joules per mole kelvin |
| `W m⁻² K⁻⁴` | watts per square meter per kelvin to the 4 |
| `kg/m³`, `kg m⁻³` | kilograms per cubic meter |
| `m²` / `m³` / `cm²` | square meters / cubic meters / square centimeters |
| `kΩ` / `MΩ` / `Ω` | kilohms / megohms / ohms |
| `µF`, `μF` / `nF` / `pF` | microfarads / nanofarads / picofarads |
| `mH` / `T` / `mT` / `Wb` | millihenries / teslas / milliteslas / webers |
| `S` (siemens) / `C` / `F` / `H` | siemens / coulombs / farads / henries |
| `GHz` / `kHz` / `Hz` | gigahertz / kilohertz / hertz |
| `eV` / `keV` / `MeV` / `GeV` / `TeV` | electronvolts / kilo electronvolts / mega electronvolts / giga electronvolts / tera electronvolts |
| `Å` | angstroms |
| `mbar` / `bar` / `atm` / `psi` / `Torr` | millibars / bars / atmospheres / p s i / torr |
| `rad` / `sr` | radians / steradians |
| `dB` | decibels |
| `cd` / `lm` / `lx` | candelas / lumens / lux |
| `Bq` / `Gy` / `Sv` | becquerels / grays / sieverts |
| `u`, `Da` | atomic mass units / daltons |

**Source.** NIST SP 811 and the NIST SI checklist (unit names follow English rules; "per" replaces the
solidus; "squared"/"cubed" after the unit name, "square"/"cubic" before it for area and volume; unit
names and symbols never mixed; symbols unaltered in the plural; `kilohm` and `megohm` drop the prefix
vowel); SI Brochure 9th ed. (unit names and symbols); Physics Today SI guide via search (space, not a
centred dot, between spelled unit names). §3c for the prefix-plus-unit pattern, US spelling, plural rule.

**Confidence.** sourced for "per", "squared/cubed", "square/cubic", the product as a space, plurals of
symbols; **proposed** for "kilo electronvolts" written as two words (G2P safety) and for `psi` as letters.
NIST pluralises only above 1 ("0.25 liter"); §3c says plural unless the value is 1 ("0.25 liters"); this
note follows §3c (open question 1).

### 2.2 Unit versus variable

**Detection.** A single Latin letter that is both a unit symbol and a common variable: `m` (meter / mass),
`s` (second / displacement), `g` (gram / gravitational acceleration), `V` (volt / volume or potential),
`A` (ampere / area), `T` (tesla / temperature or period), `K` (kelvin / a constant), `C` (coulomb /
capacitance), `F`, `H`, `W`, `J`, `N`, `L`, `h`. Extraction gives no font information unless the font
runs survive (ING-3 spans): an italic letter is a variable (ISO 80000-2 and the SI Brochure set
quantity symbols italic and unit symbols upright).

**Rule.** A letter is read as a unit only when (a) it immediately follows a number (or a number plus
`±` group, or a closing parenthesis of a `(value ± u)` group) and (b) it is upright when font runs are
present and (c) it is not followed by `=`, `(`, or an operator. Otherwise it is a variable and read as
the letter. A unit inside square brackets after a quantity symbol (`v [m/s]`) is a unit.

| Pattern | Spoken |
| --- | --- |
| `a mass m of 3 g` | a mass m of 3 grams |
| `10 A through the wire` | 10 amperes through the wire |
| `V = 5 V` | v equals 5 volts |
| `T = 300 K` | t equals 300 kelvins |
| `g = 9.81 m/s²` | g equals 9.81 meters per second squared |

**Source.** SI Brochure 9th ed. §5 (quantity symbols italic, unit symbols upright); NIST checklist #12
(it is clear to which unit symbol a value belongs). The number-before rule is **proposed**.
**Confidence.** proposed.

### 2.3 Scientific notation and orders of magnitude

**Detection.** `a × 10^n`, `a × 10ⁿ`, `a x 10^n` (letter x as times), `a·10^n`, E-notation `6.022e23`,
`6.022E-23`, `10^{-19}`. Artefacts: the superscript flattened so `3.0 × 10⁸` arrives as `3.0 × 108` and
`1.6 × 10⁻¹⁹` as `1.6 × 10-19` (needs the font-size run of the superscript to tell `× 108` from a real
108; a `×` followed by `10` and a hyphen-digit run is always a power); `~10^-19` and `O(10^3)`.

**Rule.** `× 10^n` is "times 10 to the n" (§3c power wording, digits stay digits); E-notation between
digits is rewritten to the same words; `~`, `∼` or `≈` with no left operand before a number is "about";
"of order" stays as written.

| Pattern | Spoken |
| --- | --- |
| `3.0 × 10^8`, `3.0 × 10⁸`, `3.0 x 10^8` | 3.0 times 10 to the 8 |
| `1.6 × 10⁻¹⁹`, `1.6 × 10-19` | 1.6 times 10 to the minus 19 |
| `6.022e23`, `6.022E23` | 6.022 times 10 to the 23 |
| `10⁶` alone | 10 to the 6 |
| `~10⁻¹⁹ J` | about 10 to the minus 19 joules |
| `O(10³)` | o of 10 to the 3 (§3c function rule) |

**Source.** §3c (power and function wording); "times ten to the" is the universal classroom reading
(unverified by a cited source in this note). **Confidence.** proposed ("about" for a prefix `~` is a
second wording for `~`, §3c gives "distributed as"; open question 2).

### 2.4 Measurement uncertainty, significant figures, ranges, ratios, percentages

**Detection.** `x ± u` with or without a unit after each part; `(x ± u) unit`; concise form `1.2345(6)`,
`6.674 30(15)` (digits, optional thin spaces, then a parenthesised digit group glued to the last
digit); "s.f.", "sig. figs", "d.p."; ranges with en dash `20–30 °C` or hyphen `20-30`; ratios `3:1`;
`%`, `ppm`, `‰`.

**Rule.** `±` "plus or minus" (§3c). The concise form is rewritten to the `±` form by placing the
parenthesised digits at the last decimal places of the value (`1.2345(6)` → `1.2345 ± 0.0006`,
`1234.56789(11)` → `± 0.00011`), then spoken; this is exactly NIST's definition of the notation, and
a listener cannot parse "one point two three four five, six". A unit written once after a parenthesised
`(x ± u)` applies to both. A numeric range is "x to y"; a ratio `a:b` between digits "a to b".

| Pattern | Spoken |
| --- | --- |
| `9.81 ± 0.02 m/s²` | 9.81 plus or minus 0.02 meters per second squared |
| `(123 ± 2) g` | 123 plus or minus 2 grams |
| `1.2345(6) kg` | 1.2345 plus or minus 0.0006 kilograms |
| `to 3 s.f.` / `2 d.p.` | to 3 significant figures / 2 decimal places |
| `20–30 °C` | 20 to 30 degrees Celsius |
| `3:1` | 3 to 1 |
| `5 %`, `5%` / `ppm` | 5 percent / parts per million |

**Source.** NIST Reference on Constants, Units and Uncertainty (concise notation: the number in
parentheses is the standard uncertainty in the last digits); NIST SI checklist #12 (`(123 ± 2) g`
form) and #8, #10. **Confidence.** sourced for the meaning; the spoken expansion is proposed.

### 2.5 Vectors, unit vectors, tensors and index notation; derivatives and vector calculus

**Detection.** Bold letters (font run bold, lost in plain extraction), arrows `v⃗` (U+20D7 combining,
often split off as a separate `⃗` or as `→` above in a separate line), hats `x̂ ŷ ẑ` (U+0302 combining or
precomposed), `î ĵ k̂`, dots `ẋ ẍ` (U+0307 / U+0308), `Fᵢⱼ`, `F_{ij}`, upper indices `x^μ`, `T^{μν}`,
`Aᵀ`, `a · b`, `a × b`, `∇f`, `∇·E`, `∇×B`, `∇²φ`, `∂_μ`, `□`. Artefacts: combining marks detached and
placed after the letter or before it; `∇` extracted as an image or `r`; dots above lost entirely.

**Rule.** Hats, dots and arrows by §3c ("x hat", "x dot", "vector v"); `ẍ` "x double dot" (proposed,
follows "x double prime"); bold single letter in maths with a font run "vector v" (proposed; without the
run, the letter). `×` between two vector operands (letters with arrows, hats or bold, `∇`, a closing
bracket of a vector) is "cross"; between numbers or a number and a letter it stays "times" (§3c).
`∇·` "del dot", `∇×` "del cross", `∇²` "del squared", `∇f` "del f". Lower indices "sub" (§3c); an
upper index on a tensor (a Greek letter or a single `i j k` superscript in a document with lower Greek
indices) is "sup" (§3c label superscript), never "to the". Einstein summation is read as written: no
"sum" is added.

| Pattern | Spoken |
| --- | --- |
| `x̂`, `î` | x hat, i hat |
| `v⃗` / bold `v` | vector v |
| `ẋ` / `ẍ` | x dot / x double dot |
| `a · b` | a dot b |
| `τ = r × F` (vectors) | tau equals r cross f |
| `∇·E` / `∇×B` / `∇²φ` / `∇f` | del dot e / del cross b / del squared phi / del f |
| `F_{ij}`, `Fᵢⱼ` | f sub i j |
| `∂_μ A^ν` | partial sub mu a sup nu |
| `g_{μν} x^μ x^ν` | g sub mu nu x sup mu x sup nu |
| `Aᵀ`, `A^T` | a transpose |

**Source.** §3c (hat, dot, vector, sub, sup, transpose, del); MathSpeak/ClearSpeak via Speech Rule Engine
docs (a physics domain exists; no wording retrieved). **Confidence.** §3c reuse sourced; "cross",
"double dot", bold-as-vector and upper-index "sup" proposed.

### 2.6 Quantum notation

**Detection.** `|ψ⟩` (also `|ψ>` with ASCII `>`, or `〉` U+3009), `⟨φ|`, `⟨φ|ψ⟩`, `⟨φ|Â|ψ⟩`, hatted
capitals `Ĥ`, `ħ` (U+210F, also `h̄` or `h-bar`), `[A, B]`, `{A, B}`, `A†` (also `A^\dagger`, `A+`),
`⟨x⟩`, `ψ*`, spin `½`, `|↑⟩ |↓⟩`, `|0⟩ |1⟩`. Artefacts: `⟩` extracted as `i` or `〉`, `ħ` as `h` plus
a stray macron.

**Rule.** `|a⟩` "ket a"; `⟨a|` "bra a"; `⟨a|b⟩` "bra a ket b"; `⟨a|M|b⟩` "bra a m ket b" (hat read);
`⟨f, g⟩` with a comma stays "the inner product of f and g" (§3c). `ħ` "h bar". `A†` "a dagger". `ψ*`
"psi star" (§3c). `[A, B]` with operator operands (hatted letters, capitals in a quantum context) is
"the commutator of a and b", `{A, B}` "the anticommutator of a and b"; otherwise §3c bracket rules.
`⟨x⟩` alone "the expectation value of x". Arrows inside a ket: `↑` "up", `↓` "down". `½` "1 half"
(§3c).

| Pattern | Spoken |
| --- | --- |
| `|ψ⟩` / `⟨φ|` | ket psi / bra phi |
| `⟨φ|ψ⟩` | bra phi ket psi |
| `⟨ψ|Ĥ|ψ⟩` | bra psi h hat ket psi |
| `ħ`, `h̄` | h bar |
| `[x̂, p̂] = iħ` | the commutator of x hat and p hat equals i h bar |
| `{A, B}` (operators) | the anticommutator of a and b |
| `A†` | a dagger |
| `⟨x⟩` | the expectation value of x |
| `|↑⟩` / `|0⟩` | ket up / ket 0 |
| `spin ½` | spin 1 half |

**Source.** Dirac notation texts (bra and ket names: Manchester PHYS30101 notes, Hamilton College
handout); spoken "ket psi", "bra phi", "h bar" are classroom convention not found stated in a source
(search 4). **Confidence.** proposed (sourced only for the names bra and ket).

### 2.7 Nuclear and particle notation

**Detection.** Pre-superscript mass number and optional pre-subscript atomic number on an element symbol:
`²³⁸U`, `²³⁸₉₂U`, `⁴He`, `^{235}U`; artefacts `238U`, `238 92U`, `92 238U` (scripts flattened before
the symbol, digits glued to a capital that is an element symbol); hyphen form `U-238`, `uranium-238`;
particles `e⁻ e⁺ μ⁻ π⁰ π⁺ ν ν̄ νₑ ν̄ₑ γ α β⁻ p n`; reactions with `→` and `+`; shells `1s² 2s² 2p⁶`;
quantum numbers `n, l, m_l, m_s`.

**Rule.** A nuclide is "element name, mass number" ("uranium 238"); the atomic number is not spoken
(it is implied by the element). The hyphen form reads the same. A particle symbol is read by its letters
and decorations (default): `e⁻` "e minus", `e⁺` "e plus", `π⁰` "pi 0", `ν̄ₑ` "nu bar sub e". With the
per-document "quantity names" setting on (§2.10) particles become names (electron, positron, neutral
pion, electron antineutrino). A reaction arrow `→` between particles or nuclides is "yields"
(proposed; §3c gives "approaches"/"to", neither fits a reaction; open question 3). Electron configuration
`2p⁶` is "2 p 6" (the superscript is an occupation count, not a power).

| Pattern | Spoken |
| --- | --- |
| `²³⁸U`, `238U`, `U-238` | uranium 238 |
| `⁴He`, `α` (as a particle) | helium 4, alpha |
| `²³⁸U → ²³⁴Th + ⁴He` | uranium 238 yields thorium 234 plus helium 4 |
| `n → p + e⁻ + ν̄ₑ` | n yields p plus e minus plus nu bar sub e |
| `π⁰ → γγ` | pi 0 yields gamma gamma |
| `1s² 2s² 2p⁶` | 1 s 2, 2 s 2, 2 p 6 |
| `β⁻ decay` | beta minus decay |

**Source.** IUPAC nuclide symbol (mass number as left superscript); Wikipedia "Isotope" (spoken form
"helium-four", "uranium two-thirty-five"; spoken usage element-name-then-mass-number). Particle letter
reading and "yields" proposed. **Confidence.** sourced for nuclides; proposed for particles and arrows.

### 2.8 Named constants, dimensionless numbers, Greek quantities

**Detection.** `c, G, h, ħ, k_B, k, ε₀, μ₀, N_A, e, R, σ, m_e, m_p, a₀, R_∞, α`; dimensionless groups
written as two-letter italic symbols `Re, Ma, Pr, Nu, St, Fr, Pe, Gr, Ra, Kn, We` before `=`, `≈`, `<`,
`>` or a number; Greek used as quantities (`ω λ ν ρ σ τ Φ`). Artefacts: `ε0`, `kB` (subscript flattened),
`Re` that is the real-part operator `Re(z)` or `ℜ`.

**Rule.** Constants are read as letters with §3c subscripts (`k_B` "k sub b", `ε₀` "epsilon sub 0").
A dimensionless-number symbol (a two-letter symbol from the table, followed by a relation or a number,
in a document whose profile or vocabulary is physics/engineering) is read by its name. `Re(…)`, `ℜ`
followed by a group is "the real part of"; `Im(…)` "the imaginary part of". Greek quantities by letter
name (§3c); the quantity name only under the §2.10 setting.

| Pattern | Spoken |
| --- | --- |
| `k_B T`, `kBT` | k sub b t |
| `ε₀`, `ε0` / `μ₀` | epsilon sub 0 / mu sub 0 |
| `N_A` | n sub a |
| `Re = 2000` | reynolds number equals 2000 |
| `Ma > 1` / `Pr` / `Nu` | mach number is greater than 1 / prandtl number / nusselt number |
| `Re(z)` | the real part of z |
| `E = hν` | e equals h nu |
| `ħω` | h bar omega |

**Source.** §3c (letters, subscripts, Greek); dimensionless-number names are standard names (no style
guide retrieved). **Confidence.** proposed (the `Re` real-part reading is an addition to §3c, open
question 4).

### 2.9 Circuits and engineering; logs and decibels; temperature

**Detection.** `Ω` (both code points), `kΩ`, `V`, `A`, `mA`, `R₁` `R1`, `C₂`, `V_{CC}`, `V_{out}`, `Hz`,
`∠θ` phasors, `j` as the imaginary unit (`3 + 4j`, `j\omega L`), `dB`, `dBm`, `dBi`, `dBV`, `log₁₀`,
`log10`, `K`, `°C`, `°F`. Artefacts: `R1` (subscript flattened), `Ω` lost to a font that maps it to `W`
(Symbol font), `∠` dropped.

**Rule.** Units by §2.1; component labels by §3c subscripts (`R₁` "r sub 1"; `V_{out}` "v sub out", a
word subscript read as a word); `∠` "angle"; `j` and `i` are letters (no "imaginary" word);
`dB` "decibels"; `dBm`, `dBi`, `dBV` letters ("d b m"); `log₁₀ x` "log base 10 of x" (§3c has no base
wording and its general subscript rule would give "log sub 10 of x"; open question 5). Temperature: `K` "kelvins" (never
"degrees kelvin"), `°C` and `°F` stay with ING-6 (already "degrees Celsius", "degrees Fahrenheit").

| Pattern | Spoken |
| --- | --- |
| `R₁ = 10 kΩ` | r sub 1 equals 10 kilohms |
| `5 V`, `20 mA` | 5 volts, 20 milliamperes |
| `V_{out}` | v sub out |
| `∠30°` | angle 30 degrees |
| `Z = 3 + 4j Ω` | z equals 3 plus 4 j ohms |
| `3 dB` / `−3 dBm` | 3 decibels / minus 3 d b m |
| `log₁₀ x` | log base 10 of x |
| `373.15 K` / `100 °C` | 373.15 kelvins / 100 degrees Celsius |

**Source.** SI Brochure / NIST SP 811 (kelvin, not "degree kelvin"; kelvins plural); IEEE Editorial
Style for component subscripts (not retrieved; unverified). **Confidence.** units sourced; the rest
proposed.

### 2.10 Equations in words (symbols versus quantity names)

**Detection.** Any maths span. The document's own glossary: "where F is the force, m the mass", "F
denotes", a nomenclature table (ING-3 table block headed "Nomenclature" / "List of symbols").

**Rule (proposed).** Default: symbols as letters ("f equals m a"); this is what the student sees on the
page and what the following algebra uses. A per-document setting "read quantity names" (off by default)
replaces a symbol by its name when, and only when, the document defines it (glossary captured at
ingestion like the SYN-4 acronym definitions): `F = ma` becomes "force equals mass times acceleration",
juxtaposition becomes "times" because names are multi-word. Particle symbols (§2.7) use a fixed name
table under the same setting. Never guess a name the document did not give.

| Pattern | Setting off | Setting on (with a glossary) |
| --- | --- | --- |
| `F = ma` | f equals m a | force equals mass times acceleration |
| `E = mc²` | e equals m c squared (§3c display_02) | energy equals mass times c squared |
| `p = mv` | p equals m v | momentum equals mass times velocity |

**Source.** none prescribes; §3c reads variables as letters. **Confidence.** proposed.

### 2.11 Angles, astronomy and geoscience units

**Detection.** `°`, `′` (U+2032) and `″` (U+2033) after digits (also ASCII `'` and `"`, and `º` U+00BA
ordinal indicator for degree), `arcsec`, `arcmin`, `mas`, `″` after a decimal, sexagesimal `51°30′N`,
`0°07′39″W`, `12ʰ 30ᵐ 15ˢ` (right ascension), `AU`, `au`, `pc`, `kpc`, `Mpc`, `ly`, `M☉` (U+2609 also
`M_⊙`, `M_sun`, `Msun`), `R☉`, `L☉`, `M⊕`, `mag`, `Gyr`, `Myr`, `Ma`, `Ga`, `ka`, `kyr`. Artefacts:
`☉` lost or turned into `/circledot`, `Msun`, `′` as an apostrophe, `°` glued to the next number.

**Rule.** `°` "degrees"; `′` and `″` after a number that follows a `°` value, or in a coordinate, are
"minutes" and "seconds"; standalone after a number in an astronomy document they are "arcminutes" and
"arcseconds" (ING-11 profile or the words "arcsec" nearby decide); after a letter they stay §3c
"prime"/"double prime". A hemisphere letter after a coordinate is "north/south/east/west". Astronomy
units by name with plural rule. Geological ages: `Ma` "million years ago", `Ga` "billion years ago",
`Myr` "million years", `Gyr` "billion years" (the age/duration split is the geoscience convention;
proposed here, open question 6).

| Pattern | Spoken |
| --- | --- |
| `51°30′N` | 51 degrees 30 minutes north |
| `0°07′39″W` | 0 degrees 7 minutes 39 seconds west |
| `0.75″` (astronomy) | 0.75 arcseconds |
| `12ʰ30ᵐ` | 12 hours 30 minutes |
| `1 AU` / `1.3 pc` / `4.2 ly` / `3 Mpc` | 1 astronomical unit / 1.3 parsecs / 4.2 light years / 3 megaparsecs |
| `2 M☉`, `2 M_sun` / `R☉` / `L☉` / `M⊕` | 2 solar masses / solar radii / solar luminosities / earth masses |
| `m = 5.2 mag` | m equals 5.2 magnitudes |
| `4.5 Gyr` / `66 Ma` | 4.5 billion years / 66 million years ago |

**Source.** SI Brochure Table 8 (degree, minute, second of arc; astronomical unit `au`); IAU style for
`M☉` (not retrieved; unverified). **Confidence.** sourced for angles and au; proposed for the rest.

## 3. Context rules and ambiguities

| Ambiguity | Readings | What decides | Who decides |
| --- | --- | --- | --- |
| `m s g V A T K C F H W J N L h` | unit / variable | number before, upright font run, no `=` after | sentence + font runs (ING-3) |
| `×` | times / cross | operands: numbers vs vector-marked letters, `∇` | expression |
| `~`, `∼` | distributed as (§3c) / about | left operand present or not; next token a number | expression |
| `[A, B]` | interval (§3c) / commutator | operands are operators (hats, capitals) and profile `math` + quantum vocabulary; `= iħ` nearby | expression + ING-11 |
| `x^μ`, `T^{μν}` | power / upper index | Greek or `i j k` superscript on a symbol that also carries lower Greek indices | expression |
| `′ ″` | prime / arcminute, arcsecond / minutes, seconds / feet, inches | after letter vs after digit; `°` before; document domain | expression + ING-11 vocabulary |
| `→` | approaches / to / yields | limit operator, colon before, or particles/nuclides on both sides | expression |
| `Re`, `Im`, `Ma`, `Pr` | dimensionless number / real part / megaannum | followed by `(`: operator; followed by `=`/number: dimensionless; after a number: unit | expression |
| `Ma` after a number | million years ago / mach number | number before → age | sentence |
| `e` | elementary charge / Euler's number / electron (`e⁻`) | charge sign superscript → particle; otherwise letter "e" (reading is the same) | none needed |
| `psi` (ASCII) vs `ψ` | pounds per square inch / Greek | ASCII letters after a number → unit | token |
| `238U`, `3H` | nuclide / number plus letter | digits glued to an element symbol at word start, reaction or isotope vocabulary near; `3 h` with a space is hours | sentence |
| `j` | imaginary unit / index | none: read as the letter either way | none |
| `½` after "spin" | 1 half | §3c numeric fraction | none |
| `1.2345(6)` | concise uncertainty / function call / citation | digits glued to `(` digits `)` with no space; never in a `prose` citation form | token |
| bold letter | vector / emphasis | font run bold inside a maths span | font runs |

ING-11 can decide document-wide: (a) whether `[A, B]` may be a commutator (profile `math` plus quantum
vocabulary), (b) whether bare `′ ″` are arcminutes/arcseconds (astronomy), (c) whether `Re/Ma/Pr` are
dimensionless numbers (engineering), (d) the default of the §2.10 "quantity names" setting. The sentence
around a token must decide unit vs variable and `Ma` as age.

## 4. Pronunciation lexicon needs (TERM-1)

Words the voice can mispronounce even when spelled right. Respellings are informal (capitals = stress).

| Term | Respelling | Term | Respelling |
| --- | --- | --- | --- |
| ħ (symbol name) | h bar | Schrödinger | SHROH-ding-er |
| Boltzmann | BOHLTS-mahn | Avogadro | av-oh-GAH-droh |
| coulomb | KOO-lom | angstrom, Ångström | ANG-strum |
| joule | JOOL | siemens | SEE-menz |
| becquerel | bek-REL | sievert | SEE-vert |
| Lagrangian | luh-GRAHN-jee-un | Hamiltonian | ham-il-TOH-nee-un |
| Euler | OY-ler | Fourier | FOOR-ee-ay |
| Laplacian | luh-PLAH-see-un | Hermitian | her-MISH-un |
| eigenvalue | EYE-gen-val-yoo | fermion | FUR-mee-on |
| boson | BOH-zon | Pauli | POW-lee |
| Heisenberg | HY-zen-berg | Dirac | dih-RAK |
| Feynman | FINE-mun | Fermi | FAIR-mee |
| Rayleigh | RAY-lee | Raman | RAH-mun |
| Navier | nav-YAY | Prandtl | PRAHN-tul |
| Mach | MAHK | Bernoulli | ber-NOO-lee |
| Lorentz | LOR-ents | Minkowski | min-KOFF-skee |
| Poisson | pwah-SOHN | Kirchhoff | KEERK-hoff |
| Thévenin | TAY-veh-nan | Gauss | GOWSS |
| weber (unit) | VAY-ber | Coriolis | kor-ee-OH-lis |
| Schwarzschild | SHVARTS-shilt | Chandrasekhar | chun-druh-SAY-kar |
| muon | MYOO-on | gluon | GLOO-on |
| quark | KWORK | qubit | KYOO-bit |
| psi (Greek ψ) | SIGH | xi (Greek ξ) | KSY |
| nu (Greek ν) | NOO | phi (Greek φ) | FY |
| psi (unit, ASCII) | P S I | dBm | D B M |
| enthalpy | EN-thal-pee | aphelion | uh-FEE-lee-un |
| ab initio | ab ih-NISH-ee-oh | Bremsstrahlung | BREMS-shtrah-lung |
| parsec | PAR-sek | Zeeman | ZAY-mahn |

Items that are text rewrites, not lexicon entries: unit symbols (§2.1), `ħ` → "h bar" (a symbol table
entry, MATH-3, listed above because the respelling must reach the voice as two words), nuclide names
(§2.7, needs an element-symbol table of 118 entries, shared with the chemistry note), `MeV` family.

## 5. Example pairs

```jsonl
{"id": "physics_01", "class": "units", "raw": "The car accelerates at 9.8 m/s² for 3 s.", "spoken": "The car accelerates at 9.8 meters per second squared for 3 seconds.", "block": "paragraph"}
{"id": "physics_02", "class": "units", "raw": "a torque of 12 N·m", "spoken": "a torque of 12 newton meters", "block": "paragraph"}
{"id": "physics_03", "class": "units", "raw": "The specific heat is 4.18 J/(mol·K).", "spoken": "The specific heat is 4.18 joules per mole kelvin.", "block": "paragraph"}
{"id": "physics_04", "class": "units", "raw": "σ = 5.67 × 10⁻⁸ W m⁻² K⁻⁴", "spoken": "sigma equals 5.67 times 10 to the minus 8 watts per square meter per kelvin to the 4", "block": "paragraph"}
{"id": "physics_05", "class": "units", "raw": "R = 10 kΩ and C = 4.7 µF", "spoken": "r equals 10 kilohms and c equals 4.7 microfarads", "block": "paragraph"}
{"id": "physics_06", "class": "units", "raw": "The carrier is at 2.4 GHz.", "spoken": "The carrier is at 2.4 gigahertz.", "block": "paragraph"}
{"id": "physics_07", "class": "units", "raw": "The photon carries 13.6 eV and the beam 7 MeV.", "spoken": "The photon carries 13.6 electronvolts and the beam 7 mega electronvolts.", "block": "paragraph"}
{"id": "physics_08", "class": "units", "raw": "g = 9.8 m s-2", "spoken": "g equals 9.8 meters per second squared", "block": "paragraph"}
{"id": "physics_09", "class": "units", "raw": "a density of 1000 kg/m³", "spoken": "a density of 1000 kilograms per cubic meter", "block": "paragraph"}
{"id": "physics_10", "class": "units", "raw": "The block has a mass of 1 kg.", "spoken": "The block has a mass of 1 kilogram.", "block": "paragraph"}
{"id": "physics_11", "class": "unit_vs_variable", "raw": "a mass m of 3 g", "spoken": "a mass m of 3 grams", "block": "paragraph"}
{"id": "physics_12", "class": "unit_vs_variable", "raw": "V = 5 V", "spoken": "v equals 5 volts", "block": "paragraph"}
{"id": "physics_13", "class": "unit_vs_variable", "raw": "10 A flows through the wire", "spoken": "10 amperes flows through the wire", "block": "paragraph"}
{"id": "physics_14", "class": "scientific_notation", "raw": "c = 3.0 × 10^8 m/s", "spoken": "c equals 3.0 times 10 to the 8 meters per second", "block": "paragraph"}
{"id": "physics_15", "class": "scientific_notation", "raw": "N_A = 6.022e23 mol⁻¹", "spoken": "n sub a equals 6.022 times 10 to the 23 per mole", "block": "paragraph"}
{"id": "physics_16", "class": "scientific_notation", "raw": "e = 1.6 × 10-19 C", "spoken": "e equals 1.6 times 10 to the minus 19 coulombs", "block": "paragraph"}
{"id": "physics_17", "class": "scientific_notation", "raw": "an energy of ~10⁻¹⁹ J", "spoken": "an energy of about 10 to the minus 19 joules", "block": "paragraph"}
{"id": "physics_18", "class": "uncertainty", "raw": "We measured g = 9.81 ± 0.02 m/s².", "spoken": "We measured g equals 9.81 plus or minus 0.02 meters per second squared.", "block": "paragraph"}
{"id": "physics_19", "class": "uncertainty", "raw": "m = (123 ± 2) g", "spoken": "m equals 123 plus or minus 2 grams", "block": "paragraph"}
{"id": "physics_20", "class": "uncertainty", "raw": "m = 1.2345(6) kg", "spoken": "m equals 1.2345 plus or minus 0.0006 kilograms", "block": "paragraph"}
{"id": "physics_21", "class": "uncertainty", "raw": "Give the answer to 3 s.f.", "spoken": "Give the answer to 3 significant figures.", "block": "paragraph"}
{"id": "physics_22", "class": "uncertainty", "raw": "a range of 20–30 °C", "spoken": "a range of 20 to 30 degrees Celsius", "block": "paragraph"}
{"id": "physics_23", "class": "equations_in_words", "raw": "F = ma", "spoken": "f equals m a", "block": "equation"}
{"id": "physics_24", "class": "vectors", "raw": "The force acts along x̂.", "spoken": "The force acts along x hat.", "block": "paragraph"}
{"id": "physics_25", "class": "vectors", "raw": "ẍ = −ω²x", "spoken": "x double dot equals minus omega squared x", "block": "equation"}
{"id": "physics_26", "class": "vectors", "raw": "τ = r × F", "spoken": "tau equals r cross f", "block": "equation"}
{"id": "physics_27", "class": "vectors", "raw": "∇·E = ρ/ε₀", "spoken": "del dot e equals rho over epsilon sub 0", "block": "equation"}
{"id": "physics_28", "class": "vectors", "raw": "∇×B = μ₀J", "spoken": "del cross b equals mu sub 0 j", "block": "equation"}
{"id": "physics_29", "class": "vectors", "raw": "F_{ij} = ∂_i A_j − ∂_j A_i", "spoken": "f sub i j equals partial sub i a sub j minus partial sub j a sub i", "block": "equation"}
{"id": "physics_30", "class": "vectors", "raw": "ds² = g_{μν} dx^μ dx^ν", "spoken": "d s squared equals g sub mu nu d x sup mu d x sup nu", "block": "equation"}
{"id": "physics_31", "class": "quantum", "raw": "The state |ψ⟩ is normalized.", "spoken": "The state ket psi is normalized.", "block": "paragraph"}
{"id": "physics_32", "class": "quantum", "raw": "⟨φ|ψ⟩ = 0", "spoken": "bra phi ket psi equals 0", "block": "equation"}
{"id": "physics_33", "class": "quantum", "raw": "E = ⟨ψ|Ĥ|ψ⟩", "spoken": "e equals bra psi h hat ket psi", "block": "equation"}
{"id": "physics_34", "class": "quantum", "raw": "[x̂, p̂] = iħ", "spoken": "the commutator of x hat and p hat equals i h bar", "block": "equation"}
{"id": "physics_35", "class": "quantum", "raw": "the operator A† is the adjoint of A", "spoken": "the operator a dagger is the adjoint of a", "block": "paragraph"}
{"id": "physics_36", "class": "quantum", "raw": "the mean position is ⟨x⟩", "spoken": "the mean position is the expectation value of x", "block": "paragraph"}
{"id": "physics_37", "class": "quantum", "raw": "an electron has spin ½ and state |↑⟩", "spoken": "an electron has spin 1 half and state ket up", "block": "paragraph"}
{"id": "physics_38", "class": "nuclear", "raw": "²³⁸U → ²³⁴Th + ⁴He", "spoken": "uranium 238 yields thorium 234 plus helium 4", "block": "equation"}
{"id": "physics_39", "class": "nuclear", "raw": "The isotope 235U is fissile.", "spoken": "The isotope uranium 235 is fissile.", "block": "paragraph"}
{"id": "physics_40", "class": "particle", "raw": "n → p + e⁻ + ν̄ₑ", "spoken": "n yields p plus e minus plus nu bar sub e", "block": "equation"}
{"id": "physics_41", "class": "particle", "raw": "π⁰ → γγ", "spoken": "pi 0 yields gamma gamma", "block": "equation"}
{"id": "physics_42", "class": "constants", "raw": "the thermal energy k_B T", "spoken": "the thermal energy k sub b t", "block": "paragraph"}
{"id": "physics_43", "class": "constants", "raw": "E = hν and ħ = h/2π", "spoken": "e equals h nu and h bar equals h over 2 pi", "block": "paragraph"}
{"id": "physics_44", "class": "constants", "raw": "The flow is laminar for Re = 2000.", "spoken": "The flow is laminar for reynolds number equals 2000.", "block": "paragraph"}
{"id": "physics_45", "class": "circuits", "raw": "R₁ = 10 kΩ at 50 Hz", "spoken": "r sub 1 equals 10 kilohms at 50 hertz", "block": "paragraph"}
{"id": "physics_46", "class": "circuits", "raw": "a phase of ∠30°", "spoken": "a phase of angle 30 degrees", "block": "paragraph"}
{"id": "physics_47", "class": "circuits", "raw": "Z = 3 + 4j Ω", "spoken": "z equals 3 plus 4 j ohms", "block": "paragraph"}
{"id": "physics_48", "class": "circuits", "raw": "a gain of 3 dB at −3 dBm", "spoken": "a gain of 3 decibels at minus 3 d b m", "block": "paragraph"}
{"id": "physics_49", "class": "temperature", "raw": "Water boils at 373.15 K.", "spoken": "Water boils at 373.15 kelvins.", "block": "paragraph"}
{"id": "physics_50", "class": "astronomy", "raw": "a star of 2 M☉ at 4.2 ly", "spoken": "a star of 2 solar masses at 4.2 light years", "block": "paragraph"}
{"id": "physics_51", "class": "astronomy", "raw": "at latitude 51°30′N", "spoken": "at latitude 51 degrees 30 minutes north", "block": "paragraph"}
{"id": "physics_52", "class": "astronomy", "raw": "a parallax of 0.75″ and a distance of 1.3 pc", "spoken": "a parallax of 0.75 arcseconds and a distance of 1.3 parsecs", "block": "paragraph"}
{"id": "physics_53", "class": "astronomy", "raw": "The Earth orbits at 1 AU.", "spoken": "The Earth orbits at 1 astronomical unit.", "block": "paragraph"}
{"id": "physics_54", "class": "geoscience", "raw": "The impact occurred 66 Ma; the Earth is 4.5 Gyr old.", "spoken": "The impact occurred 66 million years ago; the Earth is 4.5 billion years old.", "block": "paragraph"}
{"id": "physics_55", "class": "units", "raw": "a bond length of 1.5 Å", "spoken": "a bond length of 1.5 angstroms", "block": "paragraph"}
{"id": "physics_56", "class": "units", "raw": "1013 mbar or about 15 psi", "spoken": "1013 millibars or about 15 p s i", "block": "paragraph"}
{"id": "physics_57", "class": "units", "raw": "a full circle is 2π rad and a sphere 4π sr", "spoken": "a full circle is 2 pi radians and a sphere 4 pi steradians", "block": "paragraph"}
```

Notes on the pairs: prose words keep their case (§3c lower-cases maths, not prose; `math_speech.jsonl`
prose pairs do the same, "Earth", "Celsius"). An attributive unit before a noun ("a 10 kΩ resistor") is
singular in English ("a 10 kilohm resistor") but plural under §3c read literally; no pair uses that form
until open question 1 is settled.

## 6. Where it hooks in HearNarro (proposal)

| Class | Hook |
| --- | --- |
| 2.1 Units | MATH-3 unit and prefix tables (extend `math_convention.json` `units`, `si_prefixes`; add products, quotients, powers) applied by the ING-6 prose normalizer after a number |
| 2.2 Unit vs variable | ING-6 rule with font runs from ING-3; no new table |
| 2.3 Scientific notation | ING-6 (E-notation, `× 10^n`, flattened superscripts with font-size runs) |
| 2.4 Uncertainty | ING-6 (concise `(6)` expansion, `s.f.`, ranges, ratios); TERM-4 table for `s.f.`, `d.p.` |
| 2.5 Vectors | MATH-3 symbol table (cross, double dot, sup on tensor indices) inside MATH-1/MATH-2 |
| 2.6 Quantum | MATH-3 (bra, ket, dagger, h bar, commutator) inside MATH-1/MATH-2; ING-11 gates the commutator reading |
| 2.7 Nuclear and particle | MATH-3 (nuclide rule, reaction arrow) plus an element-symbol table shared with chemistry; particle names under the new per-document setting |
| 2.8 Constants and dimensionless numbers | MATH-3 (`Re`, `Ma` names, `Re(` real part); ING-11 engineering vocabulary |
| 2.9 Circuits, logs, temperature | MATH-3 units; SYN-4 acronym table for `dBm`, `dBi`; ING-6 keeps `°C`, `°F` |
| 2.10 Equations in words | new per-document setting "read quantity names" (off), glossary captured at ingestion like SYN-4 definitions |
| 2.11 Angles, astronomy, geoscience | ING-6 (sexagesimal angles, coordinates) and MATH-3 unit table; ING-11 decides arcminutes |
| §4 terms | TERM-1 lexicon (physics category, EVAL-4) |

## 7. Sources

- NIST SI checklist, https://physics.nist.gov/cuu/Units/checklist.html — unit names and symbols never mixed;
  "m/s or meter per second"; symbols unaltered in the plural; `(123 ± 2) g`; `%` is 0.01; ppm not used for values (fetched).
- NIST SP 811 guide pages, https://www.nist.gov/node/428731 — "per"
  replaces the solidus; "squared"/"cubed" after the unit name; plural only above 1; verbal pronunciation is
  not addressed by SP 811, SP 330 or the SI Brochure (search 1 summary; the kilohm/megohm elision is from
  prior knowledge of SP 811 and is unverified here).
- BIPM SI Brochure 9th ed., https://www.bipm.org/en/si-brochure-9 — unit names, symbols, italic quantity
  versus upright unit, non-SI units accepted (degree, minute, second of arc, au) (search 2; text not fetched).
- Physics Today SI guide (via search 2, https://www.ece.rutgers.edu/~orfanidi/ece580/metric.pdf) — spelled
  product "newton meter" with a space, never a centred dot; "meter per second", not "meter/second".
- NIST Constants, Units and Uncertainty, https://physics.nist.gov/cuu/Constants/definitions.html — concise
  notation: the parenthesised number is the standard uncertainty in the last digits.
- Speech Rule Engine releases, https://github.com/Speech-Rule-Engine/speech-rule-engine/releases/tag/v3.0.1 —
  ClearSpeak rules fire on units; a physics domain exists; no ket/ħ wording found.
- ETS ClearSpeak report RR-16-23, https://www.ets.org/research/policy_research_reports/publications/report/2016/jwog.html —
  ClearSpeak is algebra-focused; physics notation is outside its specification.
- Manchester PHYS30101 Dirac notes, https://www.theory.physics.manchester.ac.uk/~mikeb/lecture/phys30101/Dirac.pdf,
  and Hamilton College handout, https://academics.hamilton.edu/physics/smajor/Courses/320Info/braket.pdf — names
  "bra" and "ket" for ⟨φ| and |ψ⟩.
- Wikipedia "Isotope", https://en.wikipedia.org/wiki/Isotope — spoken nuclide names "helium-four",
  "uranium two-thirty-five" (US) / "two-three-five" (UK).
- IUPAC nomenclature P-8, https://iupac.qmul.ac.uk/BlueBook/PDF/P8.pdf — nuclide symbol: mass number as left superscript.
- Wikipedia "Giga", https://www.wikipedia.org/wiki/Giga — hard and soft g in "giga" both in use (lexicon).

Not retrieved (named in the brief; no wording obtained within the budget): AIP Style Manual, IEEE Editorial
Style, APS guidance, DAISY/NISO, NVDA/JAWS behaviour. Rules that would have rested on them are marked proposed.

## 8. Open questions for the supervisor

1. Plural: §3c "plural unless the value is 1" versus NIST "plural only above 1" ("0.5 meter"), and
   attributive units ("a 10 kilohm resistor"). Keep §3c, or add the attributive-singular rule?
2. `~` before a number "about": a second wording for `~` (§3c: "distributed as"). Accept as a
   role-dependent reading like the bar's three readings?
3. Reaction arrow: "yields" (proposed) versus "gives", "decays to", "goes to" (banned). Shared with the
   chemistry note; one wording should serve both.
4. `Re(z)` "the real part of z" and two-letter dimensionless numbers by name: additions to §3c's function table?
5. `log₁₀ x`: "log base 10 of x" (teacher) versus §3c's general "log sub 10 of x".
6. `Ma`/`Ga` as "million/billion years ago" versus "megaannum"; a geoscience profile flag?
7. Numbers in nuclide names: `num2words` says "two hundred thirty-eight" where a teacher says "two
   thirty-eight"; is a digit-grouping rule for mass numbers wanted?
8. `⟨x⟩` "the expectation value of x" does not hit the banned regex "expectation of", but runs against
   its spirit (E as a letter). Accept for angle-bracket averages only?
9. `ε₀` "epsilon sub 0" (convention-consistent) versus classroom "epsilon naught/nought".
10. Default of the "read quantity names" setting (§2.10): off for all profiles, or on for `prose` profile?
