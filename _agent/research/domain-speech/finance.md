# Domain speech: finance, accounting and economics

Task domain-speech-finance, 2026-10-19. Shape follows spec `_agent/specs/m5-academic-reading.md` §3c:
lower case, one wording per pattern, numbers stay digits (the backend's `num2words` shim speaks them),
punctuation is prosody only. Where finance reuses a maths symbol the §3c wording is reused, never a
second one. Evidence for today's behaviour: `_agent/results/865_finance_probe_today.txt` (normalizer,
15 strings, and SYN-4 decisions on 34 tokens) and `_agent/results/866_finance_misaki_g2p.txt` (what
Kokoro's G2P does with the tokens the normalizer leaves alone). Pair check:
`_agent/results/867_finance_pairs_check.txt`.

## 1. What a teacher does

A finance or economics lecturer reads a figure as an amount with its unit and its currency at the end:
"$4.2bn" is "4.2 billion dollars", never "dollar 4.2 b n". Shorthand that exists only to save column
width is expanded the first time and every time when the class cannot see the page: "bp" becomes "basis
points", "pp" "percentage points", "y/y" "year on year", "22x" "22 times", "(1,234)" "minus 1,234".
Acronyms that the profession says as words (EBITDA, GAAP, CAGR, WACC, REIT, the Footsie) are said as
words, the rest are spelled. A regression table is read row by row as variable, coefficient,
significance and standard error, so the student hears the estimate and how sure it is. Formulas follow
the maths convention; the only finance-specific part is that multi-letter variable names (PV, CF, NPV)
are read letter by letter inside a formula, as §3c does for `D_{KL}`. What the student must hear: the
sign, the unit (percent versus percentage points versus basis points), the magnitude word, the currency
and the period.

## 2. Notation classes

### 2.1 Currency amounts and magnitudes (`currency`)

**Detection.** A currency symbol (`$ € £ ¥ ₹ ₩ ₽ ₺ ₿`), an ISO 4217 code (`USD EUR GBP JPY CHF CNY INR
...`, three capitals before or after a number) or a symbol-prefixed code (`US$`, `A$`, `C$`, `HK$`,
`R$`) adjacent to a number, optionally followed by a magnitude suffix glued or spaced: `k`, `K`, `m`,
`mn`, `mm`, `MM`, `M`, `bn`, `b`, `B`, `tn`, `trn`, `T`, `crore`, `lakh`. Extraction artefacts: the
symbol separated from the number by a space (`$ 4.2`), thousands separators split across a line break,
a hyphen or en dash in place of the minus sign (`-$1.2m`, `–$1.2m`), `US$` extracted as `US $`.
Negatives in parentheses: `(1,234)`, `$(0.12)`, `($0.12)`, `(1.2)` in a column of amounts.

**Rule.** Number first, then the magnitude word, then the currency word, plural unless the amount is
exactly 1. `k` thousand, `m`/`mn`/`mm`/`MM` million, `bn`/`b` billion, `tn`/`trn` trillion; a capital
`M`, `B`, `T` after a currency symbol is the magnitude (after a plain number with no currency it is not
rewritten). Dollars and cents: `$4.20` "4 dollars and 20 cents"; an amount under 1 with no magnitude is
cents (`$0.12` "12 cents"). An amount in parentheses in a financial statement, a table cell, or after a
currency symbol is negative and is read "minus" (§3c unary minus; never "negative"). The ISO code is
read as the currency's name, not spelled. Thousands separators stay; the backend reads `1,234` as a
number (866 shows "one thousand two hundred thirty four").

**Wording table**

| Pattern | Spoken |
| --- | --- |
| `$4.2bn`, `$4.2 billion`, `US$4.2bn` | 4.2 billion dollars (`US$` "4.2 billion u s dollars") |
| `USD 4.2 billion`, `4.2bn USD` | 4.2 billion u s dollars |
| `€3.5m`, `EUR 3.5m` | 3.5 million euros |
| `£12k` | 12 thousand pounds |
| `¥500mn`, `JPY 500mn` | 500 million yen |
| `₹2.5 crore`, `₹40 lakh` | 2.5 crore rupees, 40 lakh rupees |
| `CHF 3m` | 3 million swiss francs |
| `$5mm`, `$5MM`, `$5M` | 5 million dollars |
| `$1` / `$1.5m` | 1 dollar / 1.5 million dollars |
| `$4.20` / `$0.12` | 4 dollars and 20 cents / 12 cents |
| `(1,234)` in a statement or table | minus 1,234 |
| `$(0.12)`, `($0.12)` | minus 12 cents |
| `−$1.2m`, `-$1.2m` | minus 1.2 million dollars |
| `in $ millions` (header) | in millions of dollars |

**Source.** SSML say-as `currency` reads "$42.01" as "forty two dollars and one cent" (Google Cloud TTS
SSML); parentheses mean a negative amount in financial statements (AccountingCoach, AccountingTools);
`bn`/`m` after the figure with the symbol before it (UPC inter-university style guide; AP spells out
million/billion). **Confidence:** sourced for the order, cents and parentheses; proposed for "minus"
(reuses §3c) and for `mm`/`MM`.

### 2.2 Percentages, points, multiples and ratios (`percent_points`)

**Detection.** `%`, `pct`, `per cent`; `pp`, `ppt`, `pts`, `percentage points`; `bp`, `bps`, `bpts`,
`basis points` (glued `25bp` or spaced); a number glued to `x` or `×` before a noun or at a cell end
(`22x`, `3.5x EBITDA`, `1.2×`); ratio names with a slash between capitals (`P/E`, `D/E`, `P/B`,
`EV/EBITDA`); digit-colon-digit (`3:1`). Artefacts: `%` split onto the next line; `×` extracted as `x`.

**Rule.** `%` stays "percent" (ING-6 today, 865 line 6). `pp` "percentage points" and `bp`
"basis points", singular for exactly 1: the student must hear the absolute unit (AP: "percentage point"
for a difference between percentages). The trading-floor "bips" is not used; basis points is unambiguous.
A multiple is "times" (§3c `×`). A ratio name with a slash between capital letters is the letters
("p e", "e v to ebitda" for a name whose parts are themselves words), not "over": it names a ratio, it
is not a fraction in a formula. Digit-colon-digit is "to".

| Pattern | Spoken |
| --- | --- |
| `12%` | 12 percent |
| `1.5pp`, `1.5 ppt`, `1.5 pts` (after a % context) | 1.5 percentage points |
| `25bp`, `25 bps` / `1bp` | 25 basis points / 1 basis point |
| `22x`, `22×` | 22 times |
| `3.5x EBITDA` | 3.5 times ebitda |
| `P/E`, `D/E`, `P/B` | p e, d e, p b |
| `EV/EBITDA` | e v to ebitda |
| `3:1` | 3 to 1 |
| `T+2` | t plus 2 |

**Source.** Basis point = one hundredth of a percentage point, abbreviated bp/bps (Seeking Alpha,
Remitly, Rask); AP percent versus percentage point (Journalist's Resource). **Confidence:** sourced for
units; proposed for the ratio-name letters and "e v to ebitda".

### 2.3 Fiscal periods and time (`period`)

**Detection.** `Q1`–`Q4`, `1Q24`, `Q3'24`, `H1`, `H2`, `1H25`, `2H`, `FY2024`, `FY24`, `FY'24`, `CY2024`;
`YoY`, `y/y`, `y-o-y`, `QoQ`, `q/q`, `MoM`, `m/m`, `TTM`, `LTM`, `YTD`, `MTD`; tenors `3M`, `6M`, `1Y`,
`10Y`, `10-year`, `2s10s`; `T+1`, `T+2`. Artefacts: `FY 2024` split, `Q3` with a thin space.

**Rule.** Quarter and half labels stay letter and digit (`Q3` "q 3", `H1` "h 1"); a leading-digit form
is reordered (`1Q24` "q 1 24"). `FY` before a year is "fiscal". Change-period abbreviations are expanded
(the student cannot see that "Y O Y" means year on year). A tenor `nM`/`nY` directly before a rate or
index name, or a currency code, is "n-month"/"n-year"; elsewhere `3M` is left for the currency rule
(`$3M`) or the company. `2s10s` is "2s 10s" (twos tens).

| Pattern | Spoken |
| --- | --- |
| `Q3 FY2024` / `FY24` | q 3 fiscal 2024 / fiscal 24 |
| `1Q24`, `Q1'24` | q 1 24 |
| `1H25` / `H2 2024` | h 1 25 / h 2 2024 |
| `YoY`, `y/y`, `y-o-y` | year on year |
| `QoQ`, `q/q` / `MoM`, `m/m` | quarter on quarter / month on month |
| `TTM` / `LTM` | trailing 12 months / last 12 months |
| `YTD` / `MTD` | year to date / month to date |
| `3M USD LIBOR` / `10Y` yield | 3-month u s dollar libor / 10-year yield |
| `T+2` | t plus 2 |

**Source.** Common usage; no prescribing style guide found within the search budget. **Confidence:**
proposed.

### 2.4 Finance and accounting abbreviations, tickers (`abbrev`)

**Detection.** All-caps tokens and `&` compounds: EBITDA, EBIT, GAAP, IFRS, CAGR, ROI, ROE, ROA, ROIC,
IRR, NPV, WACC, CAPM, DCF, EPS, FCF, COGS, SG&A, M&A, P&L, IPO, ETF, REIT, NASDAQ, S&P 500, FTSE, Nikkei,
LIBOR, SOFR, FASB, IASB, SEC, OLS. Tickers: 1–5 capitals, often with an exchange or class suffix
(`AAPL`, `BRK.B`, `NYSE: IBM`, `VOD.L`). Artefacts: small caps extracted as lower case, `&` as `&amp;`.

**Rule.** Hand the token to SYN-4 with fixed overrides: the professional reading wins over the heuristic.
Read as words: EBITDA, EBIT, GAAP, CAGR, WACC, CAPM, COGS, REIT, NASDAQ, LIBOR, SOFR, FASB, IASB, FTSE
("footsie"), Nikkei. Spelled: IFRS, ROI, ROE, ROA, ROIC, IRR, NPV, DCF, EPS, FCF, IPO, ETF, GDP, CPI, PPI,
PPP, SEC, OLS, AAPL and every ticker. `&` between capitals is "and" (`S&P` "s and p", `SG&A`
"s g and a", `M&A` "m and a", `P&L` "p and l"). A ticker's class dot is "dot" (ING-6 domain rule).
865 shows today's mismatches: FTSE spelled, SEC and AAPL spoken, QOQ spoken, CAPM/FASB/REIT spoken with
no respelling.

| Pattern | Spoken |
| --- | --- |
| `EBITDA`, `EBIT`, `GAAP`, `CAGR`, `WACC` | ebitda, ebit, gaap, cagr, wacc (word; respelling in §4) |
| `IFRS`, `ROE`, `IRR`, `NPV`, `EPS` | i f r s, r o e, i r r, n p v, e p s |
| `SEC` (regulator) | s e c |
| `S&P 500` / `SG&A` / `M&A` | s and p 500 / s g and a / m and a |
| `FTSE 100` | footsie 100 |
| `AAPL` / `BRK.B` | a a p l / b r k dot b |

**Source.** FTSE "footsie" (Morningstar, Wiktionary, Oxford Learner's); REIT "reet" (Wikipedia,
Wiktionary); EBITDA as a spoken word (pronounce.tv, three syllables). **Confidence:** sourced for
FTSE, REIT, EBITDA; proposed for the rest of the list (common usage).

### 2.5 Economics notation and Greek (`econ`)

**Detection.** GDP, GNP, CPI, PPI, PPP, `s.a.`, `n.s.a.`, `SAAR`, `annualised`/`annualized`, `real`,
`nominal`, index bases `2015 = 100`, `(2015=100)`; growth `Δy`, `Δln Y`, `d ln Y`, `g_Y`; elasticity
`ε`, `η`; Greek used as finance quantities `β`, `α`, `σ`, `ρ`, `μ`, `θ`. Artefacts: `Δ` extracted as
`∆` (U+2206) or as `D`; Greek in a symbol font extracted as Latin (`b` for β).

**Rule.** Greek by §3c name (`β` "beta", `σ` "sigma", `Δ`/`∆` "capital delta"); a teacher often says
"change in" for `Δ`, but §3c's one wording wins (open question 3). `s.a.` "seasonally adjusted",
`n.s.a.` "not seasonally adjusted", `SAAR` "seasonally adjusted annual rate". `2015 = 100` keeps
"equals" (today's output, 865 line 11). `y/y` per 2.3.

| Pattern | Spoken |
| --- | --- |
| `β = 1.2` | beta equals 1.2 |
| `ΔY`, `∆Y` | capital delta y |
| `Δln Y_t` | capital delta natural log y sub t |
| `s.a.` / `n.s.a.` / `SAAR` | seasonally adjusted / not seasonally adjusted / seasonally adjusted annual rate |
| `(2015=100)` | 2015 equals 100 |
| `ε_{d}` | epsilon sub d |

**Source.** §3c (Greek, `ln`); expansions are common usage. **Confidence:** sourced (via §3c) for
symbols; proposed for the expansions.

### 2.6 Regression and results tables (`regression`)

**Detection.** A table whose cells hold a coefficient with 1–3 trailing `*` (`0.042***`), a parenthesized
number on the next row or after it (`(0.011)`), sometimes brackets (`[2.31]` for t-statistics); footer
rows `R²`, `R2`, `Adj. R²`, `Adjusted R-squared`, `N`, `Observations`, `Firm FE`, `Year FE`, `Controls`
with `Yes`/`No`/`✓`; a note "Robust standard errors in parentheses. *** p<0.01, ** p<0.05, * p<0.1".
Artefacts: `R²` extracted as `R2` or `R 2`; stars split into a separate cell; parentheses on a new line.

**Rule.** Read a row as: variable name, coefficient, stars as "n stars", then "standard error x". The
table note decides what the parentheses hold: "standard errors" (default), "t statistics" or "p
values"; brackets follow the note likewise. Stars are read as a count, not as a significance level,
because the legend varies by table (Stata example: *** p<0.01). `R²` "r squared" (§3c), `Adj. R²`
"adjusted r squared", `N` "n", `FE` "fixed effects", `SE` "standard errors", `t-stat` "t statistic",
`✓` "yes".

| Pattern | Spoken |
| --- | --- |
| `0.042***` | 0.042, 3 stars |
| `(0.011)` under a coefficient, note says SE | standard error 0.011 |
| `[2.31]` under a coefficient, note says t | t statistic 2.31 |
| `R²` / `Adj. R²` | r squared / adjusted r squared |
| `Firm FE  Yes` | firm fixed effects, yes |
| `Robust SE` | robust standard errors |
| `p < 0.01` | p is less than 0.01 |

**Source.** Stars and SE layout (Stata tables example 5; Statology; Sociological Science table
guidelines: stars to the right of the coefficient). **Confidence:** sourced for meaning; proposed for
the spoken order.

### 2.7 Finance formulas (`formula`)

**Detection.** Display or inline maths with PV, FV, CF, NPV, IRR, `r`, `t`, `T`, `S`, `K`, `σ`, `N(·)`,
`d₁`, `e^{−rT}`. Artefacts per §3c: subscripts flattened (`CFt`, `d1`), superscripts split (`(1+r)` then
`t` on the next line), minus as hyphen.

**Rule.** §3c throughout. Finance-specific: a multi-letter capital variable name in a formula (PV, FV, CF,
NPV) is read letter by letter like `D_{KL}`; `N(d₁)` "n of d sub 1" (function application); `σ√T`
"sigma the square root of t" (juxtaposition silent).

| Pattern | Spoken |
| --- | --- |
| `PV = CF/(1+r)^t` | p v equals c f over 1 plus r, to the t |
| `NPV = Σ_t CF_t/(1+r)^t` | n p v equals the sum over t of c f sub t over 1 plus r, to the t |
| `σ√T` | sigma the square root of t |
| `e^{−rT}` | e to the minus r t |
| `N(d₁)` | n of d sub 1 |

**Source.** §3c. **Confidence:** sourced (via §3c); the PV-as-letters rule is proposed.

### 2.8 Table and footnote conventions (`table`)

**Detection.** `▲`/`▼`/`△`/`▽`, `↑`/`↓` before or after a figure; `n/m`, `nm`, `NM`, `n/a`, `N/A`, `n.a.`;
a lone `—`, `–` or `-` in a numeric cell; `(a)`, `(1)`, `*`, `†` footnote markers after a label;
headers "in $ millions, except per share", "($000)", "% chg".

**Rule.** Arrows are "up"/"down" (865 shows `▲` is silent today, 866). `n/m` "not meaningful", `n/a`
"not available" in a data cell. A lone dash in a numeric cell is "nil". Footnote markers after a label
are dropped (like numeric citations, ING-6). Headers are expanded: `($000)` "in thousands of dollars",
`% chg` "percent change".

| Pattern | Spoken |
| --- | --- |
| `▲ 4%` / `▼ 2%` | up 4 percent / down 2 percent |
| `n/m` / `n/a` | not meaningful / not available |
| `—` in a numeric cell | nil |
| `Revenue (a)` | revenue |
| `($000)` / `% chg` | in thousands of dollars / percent change |
| `in $ millions, except per share` | in millions of dollars, except per share |

**Source.** None prescriptive found. **Confidence:** proposed.

### 2.9 Dates and ranges (`date`)

**Detection.** Year ranges with an en dash, hyphen or `to` (`2019–24`, `2019-2024`); `as of 31 Dec
2024`, `Dec. 31, 2024`, `31/12/2024`; `FY ending March`; month abbreviations. Artefact: en dash as hyphen.

**Rule.** A four-digit year followed by a two-digit end year expands the end year in the same century
when it is larger (`2019–24` "2019 to 2024"; today says "2019 to 24", 865 line 8). Month abbreviations
are expanded. Numeric dates are left to ING-6.

| Pattern | Spoken |
| --- | --- |
| `2019–24`, `2019-24` | 2019 to 2024 |
| `CAGR 2019–24` | cagr 2019 to 2024 |
| `31 Dec 2024`, `Dec. 31, 2024` | 31 december 2024, december 31, 2024 |
| `FY ending March` | fiscal year ending march |

**Source.** Common usage. **Confidence:** proposed.

## 3. Context rules and ambiguities

- **`m`/`mm`/`M` after a number.** Million only with a currency marker or in a table header in money;
  otherwise metres/millimetres (MATH-3 units). `5 mm` is millimetres; `$5mm` is million dollars.
- **`k`.** Thousand after a currency symbol or in a money column; kilo- only as a unit prefix (`5 kg`).
- **`x` after a number.** "times" before a noun, at a cell end or before a metric; the letter in algebra
  (`2x + 1`). Decided by the following token: an operator or `=` means maths.
- **Parentheses around a number.** Negative in a financial statement, an amounts column, or after a
  currency symbol; a standard error under a regression coefficient; otherwise a parenthetical. ING-11
  could carry a `finance` flag (share of currency tokens and parenthesized numbers in tables) so the
  negative reading applies document-wide; the table note decides standard errors versus t statistics.
- **`3M`, `6M`, `10Y`.** Tenor before a rate, index or currency code; million after a currency symbol;
  the company name standing alone. Needs the following token.
- **`Δ`.** "capital delta" by §3c; teachers say "change in". Supervisor decision (open question 3).
- **`E`, `E_t[·]`.** §3c reads "e"; in finance it is the expectation operator. §3c wins.
- **`SEC`, `AAPL`, `CAP`.** All-caps words that the SYN-4 heuristic reads as words; overrides needed.
- **`β`.** A stock's beta versus a regression coefficient: same wording, no conflict.
- **`P/E` versus `a/b`.** Letters-only slash between capitals with no operator nearby is a ratio name.
- **Spelling.** British and American (`annualised`/`annualized`) need no rewrite.
- **Stars.** `*` after a coefficient in a table is significance, `*` after a label is a footnote.

## 4. Pronunciation lexicon needs (TERM-1)

Respellings are proposed unless a source in §7 backs them (FTSE, REIT).

| Term | Respelling | Note |
| --- | --- | --- |
| EBITDA | ee-BIT-dah | spoken word; heuristic says spoken, G2P unknown |
| EBIT | EE-bit | |
| GAAP | gap | |
| CAGR | KAG-er | |
| WACC | wak | |
| CAPM | KAP-em | heuristic spoken, no vowel after P |
| COGS | kogz | |
| REIT | reet | sourced |
| NASDAQ | NAZ-dak | |
| LIBOR / SOFR / Euribor | LY-bor / SOH-fer / YOOR-ih-bor | |
| FASB / IASB | FAZ-bee / eye-AZ-bee | |
| FTSE | FOOT-see | sourced; today spelled (865) |
| Nikkei | NEE-kay | |
| renminbi / yuan | REN-min-bee / yoo-AHN | |
| crore / lakh | kror / lahk | Indian magnitudes |
| ceteris paribus | KAY-ter-is PAR-ih-bus | Latin |
| ex ante / ex post | eks AN-tee / eks POHST | Latin |
| pro rata / per annum | proh RAH-tuh / per AN-um | Latin |
| laissez-faire | less-ay-FAIR | French |
| tâtonnement | tah-tun-MAHN | Walras |
| Keynes / Keynesian | kaynz / KAYN-zee-an | surname |
| Walras / Pareto | val-RAHSS / pa-RAY-toh | surnames |
| Schumpeter / Hayek | SHOOM-pay-ter / HY-ek | surnames |
| Modigliani / Debreu | moh-dee-LYAH-nee / deh-BRUH | surnames |
| Scholes / Gini | shohlz / JEE-nee | Black–Scholes, Gini coefficient |
| Herfindahl / Theil | HER-fin-dahl / tile | indices |
| Veblen / Okun | VEB-len / OH-kun | Veblen good, Okun's law |

## 5. Example pairs

```jsonl
{"id": "finance_01", "class": "currency", "raw": "Revenue rose to $4.2bn.", "spoken": "revenue rose to 4.2 billion dollars.", "block": "paragraph"}
{"id": "finance_02", "class": "currency", "raw": "The firm raised USD 4.2 billion.", "spoken": "the firm raised 4.2 billion u s dollars.", "block": "paragraph"}
{"id": "finance_03", "class": "currency", "raw": "A grant of €3.5m was approved.", "spoken": "a grant of 3.5 million euros was approved.", "block": "paragraph"}
{"id": "finance_04", "class": "currency", "raw": "Salaries start at £12k.", "spoken": "salaries start at 12 thousand pounds.", "block": "paragraph"}
{"id": "finance_05", "class": "currency", "raw": "Costs were ¥500mn and ₹2.5 crore.", "spoken": "costs were 500 million yen and 2.5 crore rupees.", "block": "paragraph"}
{"id": "finance_06", "class": "currency", "raw": "The deal is worth $5mm.", "spoken": "the deal is worth 5 million dollars.", "block": "paragraph"}
{"id": "finance_07", "class": "currency", "raw": "Net loss was (1,234).", "spoken": "net loss was minus 1,234.", "block": "paragraph"}
{"id": "finance_08", "class": "currency", "raw": "EPS was $(0.12) per share.", "spoken": "e p s was minus 12 cents per share.", "block": "paragraph"}
{"id": "finance_09", "class": "currency", "raw": "The stock closed at $4.20.", "spoken": "the stock closed at 4 dollars and 20 cents.", "block": "paragraph"}
{"id": "finance_10", "class": "currency", "raw": "A fee of CHF 3m applies.", "spoken": "a fee of 3 million swiss francs applies.", "block": "paragraph"}
{"id": "finance_11", "class": "percent_points", "raw": "Margins fell 1.5pp to 22.3%.", "spoken": "margins fell 1.5 percentage points to 22.3 percent.", "block": "paragraph"}
{"id": "finance_12", "class": "percent_points", "raw": "The Fed cut rates by 25bp.", "spoken": "the fed cut rates by 25 basis points.", "block": "paragraph"}
{"id": "finance_13", "class": "percent_points", "raw": "The spread widened 1bp.", "spoken": "the spread widened 1 basis point.", "block": "paragraph"}
{"id": "finance_14", "class": "percent_points", "raw": "It trades at 22x earnings.", "spoken": "it trades at 22 times earnings.", "block": "paragraph"}
{"id": "finance_15", "class": "percent_points", "raw": "Leverage is 3.5x EBITDA.", "spoken": "leverage is 3.5 times ebitda.", "block": "paragraph"}
{"id": "finance_16", "class": "percent_points", "raw": "A P/E of 18 and a D/E of 3:1.", "spoken": "a p e of 18 and a d e of 3 to 1.", "block": "paragraph"}
{"id": "finance_17", "class": "period", "raw": "Revenue in Q3 FY2024 was up 12% YoY.", "spoken": "revenue in q 3 fiscal 2024 was up 12 percent year on year.", "block": "paragraph"}
{"id": "finance_18", "class": "period", "raw": "1H25 sales rose 4% QoQ.", "spoken": "h 1 25 sales rose 4 percent quarter on quarter.", "block": "paragraph"}
{"id": "finance_19", "class": "period", "raw": "TTM EPS and YTD returns.", "spoken": "trailing 12 months e p s and year to date returns.", "block": "paragraph"}
{"id": "finance_20", "class": "period", "raw": "Settlement is T+2 against 3M USD LIBOR.", "spoken": "settlement is t plus 2 against 3-month u s dollar libor.", "block": "paragraph"}
{"id": "finance_21", "class": "abbrev", "raw": "The S&P 500 and the FTSE 100 gained.", "spoken": "the s and p 500 and the footsie 100 gained.", "block": "paragraph"}
{"id": "finance_22", "class": "abbrev", "raw": "Shares of AAPL and BRK.B rose.", "spoken": "shares of a a p l and b r k dot b rose.", "block": "paragraph"}
{"id": "finance_23", "class": "abbrev", "raw": "SG&A and M&A costs under GAAP and IFRS.", "spoken": "s g and a and m and a costs under gaap and i f r s.", "block": "paragraph"}
{"id": "finance_24", "class": "abbrev", "raw": "The SEC requires the NPV and IRR.", "spoken": "the s e c requires the n p v and i r r.", "block": "paragraph"}
{"id": "finance_25", "class": "econ", "raw": "Real GDP grew 2.1% y/y (s.a.).", "spoken": "real g d p grew 2.1 percent year on year, seasonally adjusted.", "block": "paragraph"}
{"id": "finance_26", "class": "econ", "raw": "CPI index (2015=100).", "spoken": "c p i index, 2015 equals 100.", "block": "paragraph"}
{"id": "finance_27", "class": "econ", "raw": "β = 1.2 and σ = 18% imply α of 0.5%.", "spoken": "beta equals 1.2 and sigma equals 18 percent imply alpha of 0.5 percent.", "block": "paragraph"}
{"id": "finance_28", "class": "econ", "raw": "ΔY_t = Y_t − Y_{t−1}", "spoken": "capital delta y sub t equals y sub t minus y sub t minus 1", "block": "equation"}
{"id": "finance_29", "class": "regression", "raw": "Education 0.042*** (0.011)", "spoken": "education 0.042, 3 stars, standard error 0.011", "block": "table"}
{"id": "finance_30", "class": "regression", "raw": "R² = 0.37, Adj. R² = 0.35, N = 1,204.", "spoken": "r squared equals 0.37, adjusted r squared equals 0.35, n equals 1,204.", "block": "paragraph"}
{"id": "finance_31", "class": "regression", "raw": "Firm FE Yes; Robust SE in parentheses; *** p < 0.01.", "spoken": "firm fixed effects, yes; robust standard errors in parentheses; 3 stars, p is less than 0.01.", "block": "table"}
{"id": "finance_32", "class": "formula", "raw": "PV = CF/(1+r)^t", "spoken": "p v equals c f over 1 plus r, to the t", "block": "equation"}
{"id": "finance_33", "class": "formula", "raw": "NPV = Σ_t CF_t/(1+r)^t", "spoken": "n p v equals the sum over t of c f sub t over 1 plus r, to the t", "block": "equation"}
{"id": "finance_34", "class": "formula", "raw": "C = S N(d₁) − K e^{−rT} N(d₂)", "spoken": "c equals s n of d sub 1 minus k e to the minus r t n of d sub 2", "block": "equation"}
{"id": "finance_35", "class": "formula", "raw": "the volatility term σ√T", "spoken": "the volatility term sigma the square root of t", "block": "paragraph"}
{"id": "finance_36", "class": "table", "raw": "Sales ▲ 4%; margin ▼ 2%; growth n/m.", "spoken": "sales up 4 percent; margin down 2 percent; growth not meaningful.", "block": "table"}
{"id": "finance_37", "class": "table", "raw": "(in $ millions, except per share)", "spoken": "in millions of dollars, except per share", "block": "table"}
{"id": "finance_38", "class": "date", "raw": "EBITDA grew at a CAGR of 8% over 2019–24.", "spoken": "ebitda grew at a cagr of 8 percent over 2019 to 2024.", "block": "paragraph"}
{"id": "finance_39", "class": "date", "raw": "Cash as of 31 Dec 2024.", "spoken": "cash as of 31 december 2024.", "block": "paragraph"}
{"id": "finance_40", "class": "date", "raw": "For the FY ending March 2025.", "spoken": "for the fiscal year ending march 2025.", "block": "paragraph"}
```

## 6. Where it hooks in YomiKoe (proposal)

- `currency`: prose normalizer ING-6 (new money rule before the backend; misaki already reads `$5` and
  `$4.20`, 866, so only magnitude suffixes, ISO codes, non-dollar symbols and parentheses are new).
- `percent_points`: ING-6 (`pp`, `bp`, `22x`, `3:1`); ratio names via a small SYN-4 slash table.
- `period`: ING-6 expansion table (configurable like TERM-4); tenor rule in ING-6.
- `abbrev`: SYN-4 `SPOKEN`/`SPELLED` overrides (FTSE, SEC, QOQ, tickers) plus TERM-1 respellings.
- `econ`: MATH-3 symbol table (Greek, Δ) already covers symbols; `s.a.`, `SAAR` to the TERM-4 table.
- `regression`: a new table-reading rule in the reader for ING-3 table blocks, reading the table note;
  `R²` "r squared" via MATH-3 superscripts.
- `formula`: MATH-1/MATH-2 mathspeak, no new rule beyond multi-letter capital names.
- `table`: ING-6 (arrows, `n/m`, `n/a`, dash cells, headers); footnote drop with TERM-3.
- `date`: ING-6 year-range expansion and month abbreviations.
- A per-document setting: an ING-11 profile flag `finance` (currency and parenthesized-number density)
  that turns on the parentheses-as-negative and `m`-as-million readings.

## 7. Sources

- https://seekingalpha.com/article/4456348-basis-points-what-they-are-and-how-they-are-used — bp is a
  hundredth of a percentage point; bps spoken "bips" on the floor.
- https://www.remitly.com/blog/finance/what-is-a-basis-point/ — "bp" singular, "bps" plural.
- https://education.rask.com.au/what-are-basis-points-bips-and-bps — "bips" as the spoken variant.
- https://journalistsresource.org/?p=72733 — AP: % symbol, "percentage point" spelled out for differences.
- https://www.upc.edu/slt/ca/redaccio-i-comunicacio/writing-resources/university-management/interuniversity-style-guide/numbers-billions
  — symbol before the figure, `m`/`bn` after it.
- https://prezi.com/tjerkldyay0i/ap-style-money-rules — AP: figures plus million/billion spelled out.
- https://docs.cloud.google.com/text-to-speech/docs/ssml — SSML say-as currency: "$42.01" read as
  "forty two dollars and one cent".
- https://www.w3.org/TR/ssml-sayas — W3C note on say-as values (currency value; not read in full).
- https://www.accountingcoach.com/blog/use-of-parentheses — parentheses mean a negative amount.
- https://accountingtools.com/articles/when-to-put-parentheses-around-a-number — $(1,000) is negative 1,000.
- https://www.stata.com/manuals/tablesexample5.pdf — stars legend *** p<0.01, ** p<0.05, * p<0.1.
- https://www.statology.org/read-interpret-regression-table/ — SE beside or below the coefficient.
- https://sociologicalscience.com/guidelines-for-table-preparation/ — stars to the right of the coefficient.
- https://www.morningstar.co.uk/uk/glossary/98115/ftse.aspx — FTSE pronounced "Footsie".
- https://www.wiktionary.com/wiki/Footsie — /ˈfʊt.si/.
- https://www.oxfordlearnersdictionaries.com/definition/english/the-footsietm — "the Footsie".
- https://en.wikipedia.com/wiki/REIT — REIT pronounced "reet".
- https://www.wiktionary.com/wiki/REIT — /riːt/.
- https://pronounce.tv/video/ebitda — EBITDA said as a three-syllable word.
- Spec `_agent/specs/m5-academic-reading.md` §3c — every reused maths wording.

Not consulted within budget (named in the brief): ClearSpeak/MathSpeak finance coverage, NVDA/JAWS,
DAISY/NISO, Bloomberg/FT/Economist style guides, CFA Institute, AEA/JEL, FASB/IFRS, SEC conventions.

## 8. Open questions for the supervisor

1. Basis points: "basis points" (chosen) or "bips" as practitioners say?
2. Negatives in parentheses: "minus 1,234" (§3c) or "negative 1,234" / "a loss of 1,234" as an
   accountant says? §3c bans "negative" in maths only; does the ban extend to prose amounts?
3. `Δ` in economics: keep §3c "capital delta" or add "change in" for a growth-rate context? The
   one-wording rule says keep.
4. Tickers: spell (chosen) or map to the company name (needs a table that ages)?
5. Expand `Q3` to "the third quarter" and `FY24` to "fiscal 2024" (assumes the century), or keep
   "q 3" and "fiscal 24" (chosen)?
6. Regression stars: "3 stars" (chosen) or the significance level from the table note ("significant at
   1 percent")? The note is not always on the same page.
7. Is a `finance` flag in the ING-11 profile wanted, or should currency/parentheses rules apply
   everywhere with the local context rules in §3 only?
8. Block values: the brief asks for "paragraph", but `math_speech.jsonl` uses only "equation" and "body"
   (`_agent/results/867_finance_pairs_check.txt`). Map "paragraph" to "body" and "table" (4 rows here) to which value?
