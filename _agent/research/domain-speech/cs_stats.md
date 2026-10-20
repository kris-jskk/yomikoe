# Domain speech: computer science, machine learning and statistics (cs_stats)

Task `domain-speech-cs_stats`, 2026-10-19. Follows the shape of spec §3c
(`_agent/specs/m5-academic-reading.md`, lines 305-475) and reuses its wordings wherever a symbol is shared:
lower case, one wording per symbol, numbers stay digits (the backend's `num2words` speaks them), punctuation
is prosody only and never spoken as "comma". Today's behaviour is in `_agent/results/875_cs_stats_probe_today.txt`
(15 strings: 1 correct, 4 wrong, 10 symbol leaked). The example pairs in section 5 were checked against
`math_convention.json` with the project's own checker, `_agent/results/877_cs_stats_pairs_convention_check_final.txt` (the first run, 876, flagged "baseline" in a prose pair as the banned MathSpeak word; the pair was reworded).

Confidence: **sourced** means a cited source prescribes or documents the reading; **proposed** means the
reading is this note's choice (common lecture usage, consistent with §3c) with no prescribing source found
in the eight searches allowed.

## 1. What a teacher does

A lecturer reading a complexity bound, a hyperparameter or a test result never reads the glyphs; they read
the role: "big o of n log n", "learning rate 3 e minus 4", "t with 23 degrees of freedom equals 2.14, p less
than point 0 5". Silent reading leans on typography (italic letters, subscripts, bold best results, daggers,
arrows in column headers, monospace code), and all of that disappears in audio, so the teacher puts it back as
words: "sub", "transpose", "hat", "higher is better", "the best result". Statistics abbreviations are expanded
(M, SD, CI become "mean", "standard deviation", "confidence interval") because a listener cannot see that
"M" is a mean and not a matrix. Code and identifiers are read as the words a programmer would say ("x plus
equals 1", "control c", "dash dash verbose"), not character names. The student must hear (a) which quantity,
(b) its qualifiers (sub, hat, bar, degrees of freedom) and (c) the comparison (is less than, plus or minus),
in the order written, with a pause where the page has a comma.

## 2. Notation classes

Sixteen classes. Shared maths symbols (relations, Greek, scripts, accents, `argmax`, norms, `E`, `Var`,
`∼`, `|`) keep §3c's wording; only what is beyond §3c is new here.

### 2.1 Asymptotic notation, complexity classes, recurrences

- **Detection**: a capital `O`, `Θ`, `Ω` or lower-case `o`, `ω` immediately followed by `(`; in extracted text
  often `O(n log n)`, `O(n2)` (superscript flattened), `O(n^2)`, `Θ(n lg n)`. Complexity classes: tokens
  `P`, `NP`, `coNP`, `PSPACE`, `EXPTIME`, `BPP`, `#P`, with `-hard`/`-complete` suffixes. Recurrences:
  `T(n) = aT(n/b) + f(n)`.
- **Rule**: `O(` → "big o of", `Θ(` → "big theta of", `Ω(` → "big omega of", `o(` → "little o of",
  `ω(` → "little omega of"; parentheses silent. This overrides §3c's "capital theta/omega" only when the
  Greek capital is followed by `(` in an asymptotic position (argument holds n, m, k, log, a power).
  `lg` → "log". Complexity classes are spelled letter by letter except the word parts ("space", "time",
  "co"). `-hard` / `-complete` → "hard", "complete". A recurrence follows §3c function notation.
- **Wording**

| Pattern | Spoken |
| --- | --- |
| `O(n log n)` | big o of n log n |
| `Θ(n²)`, `Θ(n2)` flattened | big theta of n squared |
| `Ω(n)` | big omega of n |
| `o(1)` / `ω(n)` | little o of 1 / little omega of n |
| `f(n) = O(g(n))` | f of n equals big o of g of n |
| `NP-hard`, `NP-complete` | n p hard, n p complete |
| `PSPACE`, `coNP`, `BPP`, `#P` | p space, co n p, b p p, sharp p |
| `T(n) = 2T(n/2) + O(n)` | t of n equals 2 t of n over 2 plus big o of n |

- **Source**: NIST DADS "big-O notation" gives the spoken form "f of n is big oh of g of n"; HMC CS60
  slides ("O is letter Oh, for order"); Kelling's survey of spoken variants (no single standard).
- **Confidence**: sourced for "big o of"; proposed for "big theta/omega" (common lecture usage), the class
  spellings and "sharp p".

### 2.2 Numeric literals (hex, binary, scientific, powers of two, magnitude suffixes)

- **Detection**: `0x[0-9A-Fa-f]+`, `0b[01]+`, `\d(\.\d+)?e[-+]?\d+` (also `1E-5`, and `1e−5` with a
  Unicode minus), `2^32`, `2³²`, flattened `232` after "2" in a power-of-two context (undetectable: see §3),
  suffixed counts `10k`, `1.5M`, `175B`, `7B` model sizes.
- **Rule**: hex → "hex" then the digits and letters one by one; binary → "binary" then the digits one by one;
  scientific notation → mantissa "e" ("minus") exponent, the ML lecture reading (a teacher reads `lr = 3e-4`
  as "3 e minus 4", not "3 times 10 to the minus 4"); `2^32` follows §3c ("2 to the 32"); `k`/`K` after a
  digit → "thousand", `M` → "million", `B` (parameter or token counts) → "billion"; `64-bit` → "64 bit".
- **Wording**

| Pattern | Spoken |
| --- | --- |
| `0x1F` | hex 1 f |
| `0b1010` | binary 1 0 1 0 |
| `3e-4`, `1E-5` | 3 e minus 4, 1 e minus 5 |
| `2^32`, `2³²` | 2 to the 32 |
| `10k`, `1.5M`, `175B` | 10 thousand, 1.5 million, 175 billion |
| `64-bit` | 64 bit |

- **Source**: none prescribing; §3c for powers.
- **Confidence**: proposed.

### 2.3 Data units, rates and timings

- **Detection**: a number then `B`, `KB`, `kB`, `KiB`, `MB`, `MiB`, `GB`, `GiB`, `TB`, `b`, `kb`, `Mb`,
  `Gb`, `bps`, `kbps`, `Mbps`, `Gbps`, `MB/s`, `GB/s`, `IOPS`, `FLOPS`, `FLOPs`, `TFLOPS`, `ms`, `µs`
  (U+00B5) or `μs` (U+03BC), `ns`, `ps`, `Hz`, `GHz`; latency percentiles `p50`, `p95`, `p99`, `p99.9`.
- **Rule**: MATH-3 prefix + unit, plural unless 1. Bytes `B` → "bytes", bits `b` → "bits" (case decides,
  the only place case matters). Binary prefixes: Ki kibi, Mi mebi, Gi gibi, Ti tebi. `/s` and `ps` suffix
  → "per second". FLOPS → "flops" (lexicon). `pNN` before "latency" or in a latency table → "p NN".
- **Wording**

| Pattern | Spoken |
| --- | --- |
| `4 KiB` / `4 KB` | 4 kibibytes / 4 kilobytes |
| `16 GB` / `16 Gb` | 16 gigabytes / 16 gigabits |
| `10 Gbps`, `100 Mb/s` | 10 gigabits per second, 100 megabits per second |
| `500 MB/s` | 500 megabytes per second |
| `12 ms`, `3 µs`, `40 ns` | 12 milliseconds, 3 microseconds, 40 nanoseconds |
| `312 TFLOPS` | 312 teraflops |
| `p99 latency` | p 99 latency |

- **Source**: NIST binary prefixes page (kibi = 2^10; first syllable as the SI prefix, second "bee");
  MATH-3 / §3c units paragraph.
- **Confidence**: sourced for prefixes and units; proposed for "p 99".

### 2.4 Versions, standards, addresses, paths, flags, codes

- **Detection**: `v\d+(\.\d+)+`, a product name then `\d+\.\d+` (Python 3.11), `RFC \d+`, `ISO \d+`,
  IPv4 `\d{1,3}(\.\d{1,3}){3}`, `:port` after a host, CIDR `/\d{1,2}` after an address, POSIX paths
  (`/usr/bin/x`, `~/.bashrc`), Windows paths, CLI flags (`--flag`, `-v`), `HTTP \d{3}`, `SHA-256`, `MD5`,
  `UTF-8`, `x86-64`, `ARMv8`. Extraction artefacts: a path or URL split over a line break with a hyphen.
- **Rule**: a version is read component by component with "point" (not as a decimal, since `3.11` is not
  "three point one one"): "version" for a leading `v`. IPv4 dots → "dot"; `:` before a port → "port";
  `/24` → "slash 24". Paths: `/` → "slash", `.` → "dot", `~` → "home"; flags: `--` → "dash dash", `-` →
  "dash". Codes and standards: letters by SYN-4 (spelled), number as digits.
- **Wording**

| Pattern | Spoken |
| --- | --- |
| `v2.3.1` | version 2 point 3 point 1 |
| `Python 3.11` | python 3 point 11 |
| `RFC 2616`, `HTTP 404` | r f c 2616, h t t p 404 |
| `192.168.0.1:8080` | 192 dot 168 dot 0 dot 1 port 8080 |
| `10.0.0.0/24` | 10 dot 0 dot 0 dot 0 slash 24 |
| `/usr/bin/python` | slash usr slash bin slash python |
| `--verbose`, `-v` | dash dash verbose, dash v |
| `SHA-256`, `UTF-8`, `x86-64` | sha 256, u t f 8, x 86 64 |

- **Source**: none prescribing (ING-6 already speaks URL dots as "dot").
- **Confidence**: proposed.

### 2.5 Pseudocode and algorithm text

- **Detection**: `←` (often extracted as `<-` or a private-use glyph), `:=` inside an algorithm block or a
  line starting with a keyword (`for`, `while`, `if`, `return`, `repeat`, `until`), `end for`, `end if`,
  line numbers at line start, array access `A[i]`, `A[1..n]`, `⌊x⌋`, `⌈x⌉`, `mod`, `div`, `nil`, `NIL`.
- **Rule**: assignment `←` / `:=` (in an algorithm block) → "gets"; `for i ← a to b` → "for i from a to b"
  (the teacher's reading of the loop header); `downto` → "down to"; block-end keywords are words and are read
  ("end for"); line numbers are dropped; `A[i]` → "a of i" (as §3c `E[X]`); `A[1..n]` → "a of 1 to n";
  `⌊x⌋` → "the floor of x", `⌈x⌉` → "the ceiling of x"; `mod` → "mod"; `NIL` → "nil".
- **Wording**

| Pattern | Spoken |
| --- | --- |
| `x ← x + A[i]` | x gets x plus a of i |
| `for i ← 1 to n do` | for i from 1 to n do |
| `for j ← n downto 2` | for j from n down to 2 |
| `A[1..n]` | a of 1 to n |
| `⌊n/2⌋`, `⌈log n⌉` | the floor of n over 2, the ceiling of log n |
| `return NIL` | return nil |

- **Source**: LaTeX `pseudocode` package docs (left arrow = assignment); Northeastern CS3000 CLRS-style
  pseudocode guide ("read as gets").
- **Confidence**: sourced for "gets"; proposed for the loop header, floor/ceiling and line-number drop.

### 2.6 Logic, type theory, lambda calculus, semantics

- **Detection**: `⊢`, `⊨`, `⊬`, `λx.`, `λx →`, `f : A → B`, `x :: Int`, `A × B` between type names, `⟨a, b⟩`
  holding more than two elements or named as a tuple, `⟦e⟧`, `Γ ⊢ e : τ`, `→` between types.
- **Rule**: `⊢` → "proves" (in typing judgements "Γ ⊢ e : τ" → "capital gamma proves e has type tau");
  `⊨` → "models"; `λx. M` → "lambda x dot m"; `:` in a typing judgement and `::` → "has type"; `f : A → B`
  follows §3c ("f from a to b"); `∘` composed with, `↦` maps to (§3c); `⟨a, b, c⟩` → "the tuple a, b, c"
  outside linear algebra (§3c keeps "the inner product of" for two arguments in maths); `⟦e⟧` → "the
  meaning of e".
- **Wording**

| Pattern | Spoken |
| --- | --- |
| `Γ ⊢ e : τ` | capital gamma proves e has type tau |
| `M ⊨ φ` | m models phi |
| `λx. x + 1` | lambda x dot x plus 1 |
| `map :: (a -> b) -> [a] -> [b]` | map has type a to b, to list of a, to list of b |
| `⟨q, Σ, δ, q₀, F⟩` | the tuple q, capital sigma, delta, q sub 0, f |
| `⟦e₁ + e₂⟧` | the meaning of e sub 1 plus e sub 2 |

- **Source**: §3c for `∘`, `↦`, `f : X → Y`; none prescribing for the rest.
- **Confidence**: proposed.

### 2.7 Grammars and automata

- **Detection**: `::=`, `→` in a production (`S → aSb | ε`), `|` between alternatives, `ε` / `λ` as the
  empty string, angle-bracket nonterminals `<expr>`, `δ(q, a) = p`, `δ*`, `Σ*`, `L(M)`.
- **Rule**: `::=` and production `→` → "is" (teacher: "s is a s b or epsilon"); `|` → "or"; `ε` → "epsilon";
  `<expr>` → "expr"; `δ(q, a)` follows §3c function notation; Kleene star `*` after a symbol → "star".
- **Wording**

| Pattern | Spoken |
| --- | --- |
| `<expr> ::= <term> \| <expr> + <term>` | expr is term or expr plus term |
| `S → aSb \| ε` | s is a s b or epsilon |
| `δ(q₀, a) = q₁` | delta of q sub 0, a equals q sub 1 |
| `Σ*` | capital sigma star |

- **Source**: §3c (`x^*` "x star"); none prescribing for "is"/"or".
- **Confidence**: proposed.

### 2.8 Machine-learning notation (optimisation, norms, gradients, accents, operators)

- **Detection**: `argmax`, `argmin` (often `arg max` with a space, or `argmax_θ` flattened to `argmaxθ`),
  `∥w∥₂`, `||w||_2` (ASCII bars), `∇θL` (subscript flattened), `𝔼[·]`, `E_{x∼p}`, `ŷ` (also `yˆ` with a
  spacing circumflex after the letter), `x̄`, `x̃`, `θ*` or `θ∗`, `W⊤x`, `WTx` (flattened transpose), `⊙`, `⊕`,
  `∥` between vectors in brackets, `σ(·)`, `softmax`, `ReLU`, `KL(p‖q)`.
- **Rule**: everything in §3c applies (`argmax_θ` "the arg max over theta of", paired norm "the norm of",
  `∇` "del", `E` "e", accents "hat/bar/tilde/star", `⊤` "transpose"). New: `⊙` → "elementwise times";
  `⊕` → "o plus" (maths, ML), "x or" in bit context; `∥` between two vectors inside `[ ]` → "concatenated
  with" (single `∥` in an argument list stays §3c "parallel"); `softmax`, `relu`, `sigmoid` are words.
- **Wording**

| Pattern | Spoken |
| --- | --- |
| `θ* = argmin_θ L(θ)` | theta star equals the arg min over theta of l of theta |
| `∥w∥₂²` | the norm of w sub 2, squared |
| `∇_θ L` | del sub theta l |
| `𝔼_{x∼p}[f(x)]` | e sub x distributed as p of f of x |
| `ŷ = softmax(W⊤x + b)` | y hat equals softmax of w transpose x plus b |
| `h ⊙ m` | h elementwise times m |
| `[h₁ ∥ h₂]` | h sub 1 concatenated with h sub 2 |
| `D_KL(p ∥ q)` | d sub k l of p parallel q (§3c) |

- **Source**: §3c for all shared symbols; none prescribing for `⊙`, `⊕`, concatenation.
- **Confidence**: sourced (§3c) for shared; proposed for the three new operators.

### 2.9 Hyperparameters, shapes and counts

- **Detection**: `lr = 3e-4`, `β₁ = 0.9`, `dropout p = 0.5`, `batch size 32`, `top-k`, `top-1`, `k-NN`,
  `n-gram`, shapes `B × T × D`, `[B, T, D]`, `ℝ^{d×k}`, `R^{dxk}` (flattened, `x` for `×`), `d_model`.
- **Rule**: `×` between dimension symbols or numbers after "shape", "size", "matrix", "tensor", "design",
  "grid", or inside `ℝ^{…}` → "by" (the teacher's "a 2 by 2 matrix"); elsewhere §3c "times". `lr` →
  "learning rate" (TERM-4 table); `top-k` → "top k"; `k-NN` → "k nearest neighbors"; `n-gram` → "n gram";
  `ℝ^{d×k}` → "r to the d by k" (blackboard `ℝ` read as the letter, §3c); identifiers per TERM-5.
- **Wording**

| Pattern | Spoken |
| --- | --- |
| `lr = 3e-4` | learning rate equals 3 e minus 4 |
| `shape B × T × D` | shape b by t by d |
| `W ∈ ℝ^{d×k}` | w in r to the d by k |
| `top-k`, `top-1 accuracy` | top k, top 1 accuracy |
| `k-NN`, `n-gram` | k nearest neighbors, n gram |
| `β₁ = 0.9` | beta sub 1 equals 0.9 |

- **Source**: none prescribing for "by" (§3c "times" kept outside dimension context).
- **Confidence**: proposed.

### 2.10 Model, dataset and benchmark names

- **Detection**: a camel or capitalised name with a hyphen-number or hyphen-word suffix: `GPT-2`,
  `BERT-base`, `ResNet-50`, `ViT-B/16`, `ImageNet-1k`, `CIFAR-10`, `MNIST`, `GLUE`, `SQuAD`, `LLaMA-2-7B`.
- **Rule**: name through SYN-4 and TERM-1 (spoken vs spelled is a lexicon fact, not derivable); the hyphen
  is silent; a size suffix uses 2.2 (`7B` "7 billion"; inside a model name "7 b" is what practitioners say —
  open question 3); `/16` in ViT → "slash 16".
- **Wording**

| Pattern | Spoken |
| --- | --- |
| `GPT-2`, `BERT-base` | g p t 2, bert base |
| `ResNet-50`, `ViT-B/16` | res net 50, vit b slash 16 |
| `ImageNet-1k`, `CIFAR-10` | image net 1 k, cifar 10 |
| `MNIST`, `SQuAD` | m nist, squad |

- **Source**: none prescribing.
- **Confidence**: proposed; each name is a TERM-1 entry (section 4).

### 2.11 Code in prose and keyboard

- **Detection**: monospace font runs (when the extractor keeps font names), backtick spans, operators
  `==`, `!=`, `<=`, `>=`, `&&`, `||`, `->`, `=>`, `++`, `--`, `+=`, `<<`, `>>`, `&`, `|`, `^`, `~` between
  identifiers, `foo()`, `null`, `NULL`, `None`, keyboard chords `Ctrl+C`, `Cmd+Shift+P`, `Alt+F4`.
- **Rule**: read as programmers say it in class: `==` "equals equals", `!=` "not equals", `<=` / `>=` as
  §3c relations, `&&` "and", `||` "or", `!x` "not x", `->` and `=>` "arrow", `++` "plus plus", `+=` "plus
  equals", `<<` "shift left", `>>` "shift right", `&` "bitwise and", `|` "bitwise or", `^` "x or", `~`
  "bitwise not"; `foo()` → "foo" (empty parentheses silent); keyboard `+` → silent join ("control c").
  Identifiers per TERM-5.
- **Wording**

| Pattern | Spoken |
| --- | --- |
| `Ctrl+C`, `Cmd+Shift+P` | control c, command shift p |
| `if x != 0 && y == 1` | if x not equals 0 and y equals equals 1 |
| `i++`, `x += 1` | i plus plus, x plus equals 1 |
| `a << 2`, `a ^ b`, `~a` | a shift left 2, a x or b, bitwise not a |
| `returns null`, `foo()` | returns null, foo |

- **Source**: Hermans et al. "Code phonology" (ICPC 2018) and Begel's "Spoken Java" document that
  programmers verbalise operators inconsistently and propose a shared standard; neither fixes these words.
- **Confidence**: proposed.

### 2.12 Statistical test reporting (APA)

- **Detection**: `t(df) =`, `F(df1, df2) =`, `χ²(df) =` (often `χ2(1)` or `chi ²(1)` after extraction),
  `z =`, `p < .05`, `p = .003`, `p < 0.001`, `n.s.`, `ns`, `α = .05`, `1 − β`, "two-tailed".
- **Rule**: the parenthesised group after a test statistic is its degrees of freedom: `t(23)` "t with 23
  degrees of freedom", `F(2, 45)` "f with 2 and 45 degrees of freedom", `χ²(1)` "chi squared with 1
  degree of freedom" (singular at 1). Relations as §3c ("is less than"). A leading-dot decimal (APA drops
  the zero for p, r, α) is read "point" then digits one by one ("point 0 5"); a decimal with a zero is left
  to `num2words`. `n.s.` → "not significant". Significance stars are silent (2.16).
- **Wording**

| Pattern | Spoken |
| --- | --- |
| `t(23) = 2.14, p < .05` | t with 23 degrees of freedom equals 2.14, p is less than point 0 5 |
| `F(2, 45) = 3.9, p = .003` | f with 2 and 45 degrees of freedom equals 3.9, p equals point 0 0 3 |
| `χ²(1) = 4.2` | chi squared with 1 degree of freedom equals 4.2 |
| `p < 0.001` | p is less than 0.001 |
| `z = 1.96`, `α = .05` | z equals 1.96, alpha equals point 0 5 |
| `power = 1 − β` | power equals 1 minus beta |
| `n.s.` | not significant |

- **Source**: APA 7 reporting format `t(df) = value, p = value`, leading zero dropped for statistics bounded
  by 1 (Scribbr, socscistatistics, Columbus State "reporting quantitative results APA"); JCU "Common
  statistical symbols in APA 7th". The degrees-of-freedom reading is proposed (no source states it).
- **Confidence**: sourced for the written shapes; proposed for the spoken "with N degrees of freedom" and
  "point 0 5".

### 2.13 Descriptive statistics, effect sizes, intervals

- **Detection**: an APA abbreviation followed by `=` and a number inside a parenthesised report or a table:
  `M`, `SD`, `SE`, `SEM`, `Mdn`, `IQR`, `df`, `n`, `N`, `r`, `r²`, `R²`, `adj. R²`, `β`, `b`, `B`, `η²`,
  `ηp²` / `η²p` / `η_p²`, `ω²`, `d`, `g`, `OR`, `HR`, `RR`, `CI`, `95% CI [a, b]`, `M ± SD`.
- **Rule**: in a statistics position (abbreviation then `=` then a number, or a column header), expand APA
  abbreviations: M "mean", SD "standard deviation", SE "standard error", SEM "standard error of the mean",
  Mdn "median", IQR "interquartile range", df "degrees of freedom", CI "confidence interval", OR "odds
  ratio", HR "hazard ratio", RR "relative risk", adj. "adjusted". `ηp²` → "partial eta squared"; `d`
  after "Cohen's" stays "d". `95% CI [1.2, 3.4]` → "95 percent confidence interval from 1.2 to 3.4" (the
  §3c interval wording, and the bracket is not a citation under any profile). `±` stays "plus or minus".
  `R²` and `r²` are both "r squared" (lower-case rule).
- **Wording**

| Pattern | Spoken |
| --- | --- |
| `M = 3.2, SD = 1.1` | mean equals 3.2, standard deviation equals 1.1 |
| `Mdn = 4, IQR = 2` | median equals 4, interquartile range equals 2 |
| `r = .45, R² = .32` | r equals point 4 5, r squared equals point 3 2 |
| `adj. R² = .29` | adjusted r squared equals point 2 9 |
| `ηp² = .15`, `η² = .08` | partial eta squared equals point 1 5, eta squared equals point 0 8 |
| `Cohen's d = 0.8` | cohen's d equals 0.8 |
| `95% CI [1.2, 3.4]` | 95 percent confidence interval from 1.2 to 3.4 |
| `OR = 1.8, 95% CI [1.1, 2.9]` | odds ratio equals 1.8, 95 percent confidence interval from 1.1 to 2.9 |
| `3.2 ± 1.1` | 3.2 plus or minus 1.1 |
| `2 × 2 design` | 2 by 2 design |

- **Source**: APA 7 symbol list (JCU guide) for meanings of M, SD, Mdn, IQR, ηp²; NIST/§3c for intervals.
- **Confidence**: sourced for meanings; proposed for reading expanded rather than letters.

### 2.14 Distributions and estimators

- **Detection**: `X ~ N(μ, σ²)` (tilde often ASCII `~`), `Bin(n, p)`, `Pois(λ)`, `Unif(0, 1)`, `Ber(p)`,
  `Beta(a, b)`, `Dir(α)`, `x̄`, `s²`, `σ̂` (also `σˆ` or the probe's `sigmâ`), `β̂`, `θ̃`, `E[X]`, `Var(X)`,
  `Cov(X, Y)`, `Corr(X, Y)`, `i.i.d.`, `iid`, `MLE`, `MAP`, `ℒ(θ)`, `ℓ(θ)`.
- **Rule**: §3c for `∼` ("distributed as"), `E`, `Var`, `Cov`, accents. New: `Corr` → "the correlation of";
  after `∼`, a multi-letter distribution name is read as its full name (Bin "binomial", Pois "poisson",
  Unif "uniform", Ber "bernoulli", Dir "dirichlet", Cat "categorical", Exp "exponential"); single-letter `N`
  stays "n" per §3c's example (open question 1). `i.i.d.` → "i i d" (TERM-4); `MLE` → "m l e"; `MAP` → "m a
  p" (SPELLED override, not the word "map"); `ℒ` → "script l"; `ℓ` → "l".
- **Wording**

| Pattern | Spoken |
| --- | --- |
| `X ∼ N(μ, σ²)` | x distributed as n of mu, sigma squared |
| `X ∼ Bin(n, p)` | x distributed as binomial of n, p |
| `x̄`, `s²`, `σ̂²` | x bar, s squared, sigma hat squared |
| `β̂`, `θ̃` | beta hat, theta tilde |
| `E[X] = μ`, `Var(X)` | e of x equals mu, the variance of x |
| `Corr(X, Y)` | the correlation of x, y |
| `i.i.d.`, `MLE`, `MAP` | i i d, m l e, m a p |
| `ℓ(θ) = log ℒ(θ)` | l of theta equals log script l of theta |

- **Source**: §3c (shared rows); LibreTexts "Greek letter pronunciations" (eta, chi); r-help thread on
  "chi-square" vs "chi-squared" (both in use).
- **Confidence**: sourced for shared; proposed for distribution-name expansion, `Corr`, "script l".

### 2.15 Matrices and linear algebra (shared with ML)

- **Detection**: `Aᵀ`, `A^T`, `A⊤`, `AT` flattened (ambiguous with a product: §3), `A⁻¹`, `A−1` flattened,
  `A†`, `A⁺`, `I_n`, `In` flattened, `tr(A)`, `det(A)`, `‖A‖_F`, `rank(A)`, `diag(·)`, `⊗`, `⊙`.
- **Rule**: §3c throughout (transpose, "x to the minus 1", "the trace of", "the determinant of", norm,
  "tensor"). New: `A†` → "a dagger", `A⁺` → "a plus" (pseudo-inverse), `rank(A)` → "the rank of a",
  `diag(v)` → "diag of v", `‖A‖_F` keeps §3c "the norm of a sub f".
- **Wording**

| Pattern | Spoken |
| --- | --- |
| `AᵀA`, `(XᵀX)⁻¹Xᵀy` | a transpose a, x transpose x, to the minus 1, x transpose y |
| `A†` | a dagger |
| `I_n`, `tr(A)`, `det(A)` | i sub n, the trace of a, the determinant of a |
| `‖A‖_F` | the norm of a sub f |
| `rank(A) = r`, `diag(v)` | the rank of a equals r, diag of v |

- **Source**: §3c.
- **Confidence**: sourced (§3c) for shared rows; proposed for dagger, rank, diag.

### 2.16 Tables of results

- **Detection**: ING-3 table blocks; cells `76.1 ± 0.2`, `76.1±0.2`, `76.1 (0.2)`; header arrows `↑` `↓`;
  footnote marks `†`, `‡`, `*`, `**`, `***` glued to a number or name; `—`, `–`, `-`, `n/a`, `N/A` alone in a
  cell; bold best (needs font runs; the probe and this note cannot see bold in plain text).
- **Rule**: a teacher reads one row as "row label: column header value, column header value", not a grid.
  `↑` in a header → "higher is better", `↓` → "lower is better"; footnote marks and significance stars are
  silent; a dash or n/a cell → "not reported"; `76.1 (0.2)` in a ± column → "76.1 plus or minus 0.2"; bold
  best → "best" after the value when font runs show bold in a numeric column (proposed; needs ING-3).
- **Wording**

| Pattern | Spoken |
| --- | --- |
| header `Acc. ↑` | accuracy, higher is better |
| row `ResNet-50 | 76.1 ± 0.2 | —` | res net 50, accuracy 76.1 plus or minus 0.2, f 1 not reported |
| `82.3†` | 82.3 |
| `0.031**` | 0.031 |

- **Source**: none prescribing.
- **Confidence**: proposed.

## 3. Context rules and ambiguities

| Ambiguity | What decides it | Who can decide |
| --- | --- | --- |
| `:=` is "is defined as" (§3c) or "gets" (assignment) | inside an algorithm block (ING-10 code listing, a line starting with a pseudocode keyword) → "gets" | block type; per span |
| `Θ`/`Ω` "capital theta/omega" (§3c) or "big theta/omega" | followed by `(` with an n/log/power argument | per span |
| `×` "times" (§3c) or "by" | preceding noun shape/size/matrix/design, or inside `ℝ^{…}` | sentence |
| `⟨a, b⟩` inner product (§3c) or tuple | two arguments in a maths span → inner product; 3+ or CS context → tuple | ING-11 class plus arity |
| `∥` parallel (§3c), norm (paired), concatenation | single inside `D(p ∥ q)` → parallel; between vectors inside `[ ]` → concatenated with | per span |
| `⊕` direct sum / x or / concatenation | bit context (surrounding `&`, `|`, hex) → "x or"; else "o plus" | sentence |
| `M`, `N`, `d`, `r`, `B` as stats abbreviation or matrix/variable | abbreviation then `=` number in a parenthetical report or table header → expand | sentence; ING-11 cannot (a `mixed` stats paper has both) |
| `[1.2, 3.4]` interval vs citation | preceded by `CI`; first number decimal | already a rule (ING-6, 5b09a5f); add "CI" trigger |
| `.05` leading-dot decimal | always "point 0 5" | normalizer |
| `3.11` version vs decimal | preceded by a product name or `v`, or has 2+ dots | sentence |
| `AT`, `A−1`, `In`, `n2` flattened scripts | superscript lost in extraction; only font/bbox data can tell `AT` (transpose) from `A T` | ING-3 span geometry; otherwise left as letters |
| `1e-5` vs `1e−5` vs `10^-5` | all scientific; the minus glyph varies | normalizer |
| `k` thousand vs variable k vs `1k` in model names | digit-glued `k` before a noun → thousand; in a model/dataset name → "k" | lexicon for names |
| `MAP` spelled vs "map"; `SAT` problem vs "sat" | ML/stats profile → spelled; lexicon override | SYN-4 SPELLED + TERM-1 |
| `~` distributed as vs "approximately" vs home dir | between a variable and a distribution → distributed as; before a number → "about"; at path start → "home" | sentence |
| `|` given / such that / abs / or / bitwise or | §3c roles, plus grammar alternation ("or") and code ("bitwise or") | block type |
| `*` star / times / footnote / Kleene | after a variable in maths "star"; between numbers in code "times"; glued to a table number silent | block type |

ING-11 can decide: the default for `⊕`, `⟨ ⟩` and `×` in dimension context (a `math` profile leans maths
wordings; a code-share above threshold leans CS wordings). It cannot decide the stats abbreviations, versions or
flattened scripts: those need the sentence or span geometry.

## 4. Pronunciation lexicon needs (TERM-1)

| Term | Respelling | Note |
| --- | --- | --- |
| chi (χ, chi-squared) | KAI | not "chee" or "kee" |
| eta (η) | AY-tuh | |
| big O | big OH | "o" must be the letter, not "zero" |
| Dijkstra | DIKE-struh | |
| Euler, Eulerian | OY-ler, oy-LAIR-ee-un | |
| Knuth | kuh-NOOTH | |
| Bayes, Bayesian | BAYZ, BAY-zee-un | |
| Gauss, Gaussian | GOWSS, GOW-see-un | |
| Markov | MAR-koff | |
| Poisson | pwah-SOHN | |
| Dirichlet | dee-ree-KLAY | |
| Bernoulli | ber-NOO-lee | |
| Kolmogorov–Smirnov | kol-muh-GOR-off SMEER-noff | |
| Chebyshev | CHEB-ih-shoff | |
| Cholesky | kuh-LESS-kee | |
| Hadamard | AH-duh-mar | |
| Frobenius | fro-BEE-nee-us | |
| Cauchy | koh-SHEE | |
| Kullback–Leibler | KULL-back LYBE-ler | |
| Jacobian, Hessian | juh-KOH-bee-un, HESH-un | |
| Levenshtein | LEV-en-shtyne | |
| Erdős | AIR-dush | |
| Voronoi | vor-oh-NOY | |
| Nyström | NEE-strum | |
| Bonferroni | bon-fer-OH-nee | |
| Tukey | TOO-kee | |
| Cronbach | KRON-bahk | |
| Likert | LICK-ert | |
| Kaplan–Meier | KAP-lun MY-er | |
| heteroscedasticity | het-er-oh-skeh-das-TISS-ih-tee | |
| stochastic | stoh-KAS-tik | |
| ANOVA, MANOVA | uh-NOH-vuh, muh-NOH-vuh | spoken, not spelled |
| kibibyte, mebibyte, gibibyte | KIB-ee-bite, MEB-ee-bite, GIB-ee-bite | NIST: second syllable "bee" |
| FLOPS, teraflops | FLOPS, TAIR-uh-flops | spoken |
| SQL | ESS-kyoo-ELL (or SEE-kwul) | open question 5 |
| SHA | SHAH | |
| JSON, YAML | JAY-sun, YAM-ul | spoken |
| CUDA | KOO-duh | |
| LaTeX | LAH-tek | |
| NumPy, PyTorch, SciPy | NUM-pie, PIE-torch, SIGH-pie | |
| GNU | guh-NOO | |
| sudo | SOO-doo | |
| tuple | TOO-pul | |
| ReLU, GELU | RAY-loo, JEH-loo | |
| BERT, ResNet, ViT | BURT, REZ-net, VIT | ViT spoken, not spelled |
| GPT, LSTM, CNN, RNN | spelled | SYN-4 SPELLED |
| MNIST, CIFAR, SQuAD | EM-nist, SEE-far, SKWOD | |
| ad hoc, post hoc, a priori | ad HOCK, post HOCK, ah pree-OR-ee | Latin |
| ceteris paribus | KET-er-is PAR-ih-bus | Latin |

Abbreviations TERM-4 should expand (expansion table, not lexicon): lr "learning rate", i.i.d. "i i d" (kept
spelled), w.p. "with probability", w.h.p. "with high probability", a.s. "almost surely", s.t. "such that",
n.s. "not significant", adj. "adjusted", resp. "respectively".

## 5. Example pairs

```jsonl
{"id": "cs_stats_01", "class": "asymptotic", "raw": "Merge sort runs in O(n log n) time.", "spoken": "merge sort runs in big o of n log n time.", "block": "paragraph"}
{"id": "cs_stats_02", "class": "asymptotic", "raw": "The lower bound is Ω(n) and the tight bound is Θ(n²).", "spoken": "the lower bound is big omega of n and the tight bound is big theta of n squared.", "block": "paragraph"}
{"id": "cs_stats_03", "class": "asymptotic", "raw": "The error term is o(1).", "spoken": "the error term is little o of 1.", "block": "paragraph"}
{"id": "cs_stats_04", "class": "asymptotic", "raw": "T(n) = 2T(n/2) + O(n)", "spoken": "t of n equals 2 t of n over 2 plus big o of n", "block": "equation"}
{"id": "cs_stats_05", "class": "asymptotic", "raw": "SAT is NP-complete and TQBF is PSPACE-complete.", "spoken": "sat is n p complete and t q b f is p space complete.", "block": "paragraph"}
{"id": "cs_stats_06", "class": "numeric_literal", "raw": "The mask is 0x1F, i.e. 0b11111.", "spoken": "the mask is hex 1 f, that is binary 1 1 1 1 1.", "block": "paragraph"}
{"id": "cs_stats_07", "class": "numeric_literal", "raw": "We train with lr = 3e-4 and weight decay 1e-5.", "spoken": "we train with learning rate equals 3 e minus 4 and weight decay 1 e minus 5.", "block": "paragraph"}
{"id": "cs_stats_08", "class": "numeric_literal", "raw": "The address space has 2^32 entries on a 32-bit machine.", "spoken": "the address space has 2 to the 32 entries on a 32 bit machine.", "block": "paragraph"}
{"id": "cs_stats_09", "class": "numeric_literal", "raw": "The model has 175B parameters trained on 300B tokens.", "spoken": "the model has 175 billion parameters trained on 300 billion tokens.", "block": "paragraph"}
{"id": "cs_stats_10", "class": "data_units", "raw": "Pages are 4 KiB and the disk holds 2 TB.", "spoken": "pages are 4 kibibytes and the disk holds 2 terabytes.", "block": "paragraph"}
{"id": "cs_stats_11", "class": "data_units", "raw": "p99 latency is 12 ms at 10 Gbps.", "spoken": "p 99 latency is 12 milliseconds at 10 gigabits per second.", "block": "paragraph"}
{"id": "cs_stats_12", "class": "data_units", "raw": "Throughput reached 500 MB/s with 3 µs per request.", "spoken": "throughput reached 500 megabytes per second with 3 microseconds per request.", "block": "paragraph"}
{"id": "cs_stats_13", "class": "versions_addresses", "raw": "We used Python 3.11 and PyTorch v2.3.1.", "spoken": "we used python 3 point 11 and pytorch version 2 point 3 point 1.", "block": "paragraph"}
{"id": "cs_stats_14", "class": "versions_addresses", "raw": "The server listens on 192.168.0.1:8080.", "spoken": "the server listens on 192 dot 168 dot 0 dot 1 port 8080.", "block": "paragraph"}
{"id": "cs_stats_15", "class": "versions_addresses", "raw": "It returns HTTP 404 as defined in RFC 2616.", "spoken": "it returns h t t p 404 as defined in r f c 2616.", "block": "paragraph"}
{"id": "cs_stats_16", "class": "versions_addresses", "raw": "Run /usr/bin/python with --verbose.", "spoken": "run slash usr slash bin slash python with dash dash verbose.", "block": "paragraph"}
{"id": "cs_stats_17", "class": "pseudocode", "raw": "for i ← 1 to n do x ← x + A[i] end for", "spoken": "for i from 1 to n do x gets x plus a of i end for", "block": "code"}
{"id": "cs_stats_18", "class": "pseudocode", "raw": "m ← ⌊(lo + hi)/2⌋", "spoken": "m gets the floor of lo plus hi over 2", "block": "code"}
{"id": "cs_stats_19", "class": "logic_types", "raw": "Γ ⊢ e : τ", "spoken": "capital gamma proves e has type tau", "block": "equation"}
{"id": "cs_stats_20", "class": "logic_types", "raw": "The identity is λx. x and f : A → B.", "spoken": "the identity is lambda x dot x and f from a to b.", "block": "paragraph"}
{"id": "cs_stats_21", "class": "grammar_automata", "raw": "S → aSb | ε", "spoken": "s is a s b or epsilon", "block": "equation"}
{"id": "cs_stats_22", "class": "grammar_automata", "raw": "δ(q₀, a) = q₁", "spoken": "delta of q sub 0, a equals q sub 1", "block": "equation"}
{"id": "cs_stats_23", "class": "ml_notation", "raw": "θ* = argmin_θ L(θ) + λ∥θ∥₂²", "spoken": "theta star equals the arg min over theta of l of theta plus lambda the norm of theta sub 2, squared", "block": "equation"}
{"id": "cs_stats_24", "class": "ml_notation", "raw": "ŷ = softmax(W⊤x + b)", "spoken": "y hat equals softmax of w transpose x plus b", "block": "equation"}
{"id": "cs_stats_25", "class": "ml_notation", "raw": "We update θ with ∇_θ L and gate with h ⊙ m.", "spoken": "we update theta with del sub theta l and gate with h elementwise times m.", "block": "paragraph"}
{"id": "cs_stats_26", "class": "ml_notation", "raw": "The state is [h₁ ∥ h₂].", "spoken": "the state is h sub 1 concatenated with h sub 2.", "block": "paragraph"}
{"id": "cs_stats_27", "class": "hyperparams_shapes", "raw": "Inputs have shape B × T × D and W ∈ ℝ^{d×k}.", "spoken": "inputs have shape b by t by d and w in r to the d by k.", "block": "paragraph"}
{"id": "cs_stats_28", "class": "hyperparams_shapes", "raw": "We use top-k sampling and a k-NN classifier over n-gram features.", "spoken": "we use top k sampling and a k nearest neighbors classifier over n gram features.", "block": "paragraph"}
{"id": "cs_stats_29", "class": "model_names", "raw": "ResNet-50 and BERT-base were pretrained on ImageNet-1k and BooksCorpus.", "spoken": "res net 50 and bert base were pretrained on image net 1 k and books corpus.", "block": "paragraph"}
{"id": "cs_stats_30", "class": "code_in_prose", "raw": "Press Ctrl+C if x != 0 && y == 1.", "spoken": "press control c if x not equals 0 and y equals equals 1.", "block": "paragraph"}
{"id": "cs_stats_31", "class": "code_in_prose", "raw": "The loop does i++ and x += 1, then a << 2.", "spoken": "the loop does i plus plus and x plus equals 1, then a shift left 2.", "block": "paragraph"}
{"id": "cs_stats_32", "class": "test_reporting", "raw": "The effect was significant, t(23) = 2.14, p < .05.", "spoken": "the effect was significant, t with 23 degrees of freedom equals 2.14, p is less than point 0 5.", "block": "paragraph"}
{"id": "cs_stats_33", "class": "test_reporting", "raw": "F(2, 45) = 3.9, p = .003", "spoken": "f with 2 and 45 degrees of freedom equals 3.9, p equals point 0 0 3", "block": "paragraph"}
{"id": "cs_stats_34", "class": "test_reporting", "raw": "χ²(1) = 4.2, p < 0.001", "spoken": "chi squared with 1 degree of freedom equals 4.2, p is less than 0.001", "block": "paragraph"}
{"id": "cs_stats_35", "class": "test_reporting", "raw": "The interaction was n.s. at α = .05 with power 1 − β = .80.", "spoken": "the interaction was not significant at alpha equals point 0 5 with power 1 minus beta equals point 8 0.", "block": "paragraph"}
{"id": "cs_stats_36", "class": "descriptives_effects", "raw": "Scores were higher (M = 3.2, SD = 1.1).", "spoken": "scores were higher, mean equals 3.2, standard deviation equals 1.1.", "block": "paragraph"}
{"id": "cs_stats_37", "class": "descriptives_effects", "raw": "r = .45, R² = .32, adj. R² = .29", "spoken": "r equals point 4 5, r squared equals point 3 2, adjusted r squared equals point 2 9", "block": "paragraph"}
{"id": "cs_stats_38", "class": "descriptives_effects", "raw": "ηp² = .15, Cohen's d = 0.8, 95% CI [1.2, 3.4]", "spoken": "partial eta squared equals point 1 5, cohen's d equals 0.8, 95 percent confidence interval from 1.2 to 3.4", "block": "paragraph"}
{"id": "cs_stats_39", "class": "descriptives_effects", "raw": "We used a 2 × 2 design; OR = 1.8.", "spoken": "we used a 2 by 2 design; odds ratio equals 1.8.", "block": "paragraph"}
{"id": "cs_stats_40", "class": "distributions", "raw": "Let X ~ N(μ, σ²) be i.i.d. with MLE σ̂².", "spoken": "let x distributed as n of mu, sigma squared be i i d with m l e sigma hat squared.", "block": "paragraph"}
{"id": "cs_stats_41", "class": "distributions", "raw": "Y ∼ Bin(n, p) and E[Y] = np.", "spoken": "y distributed as binomial of n, p and e of y equals n p.", "block": "paragraph"}
{"id": "cs_stats_42", "class": "distributions", "raw": "x̄ estimates μ and s² estimates σ².", "spoken": "x bar estimates mu and s squared estimates sigma squared.", "block": "paragraph"}
{"id": "cs_stats_43", "class": "distributions", "raw": "ℓ(θ) = log ℒ(θ)", "spoken": "l of theta equals log script l of theta", "block": "equation"}
{"id": "cs_stats_44", "class": "linear_algebra", "raw": "β̂ = (XᵀX)⁻¹Xᵀy", "spoken": "beta hat equals x transpose x, to the minus 1, x transpose y", "block": "equation"}
{"id": "cs_stats_45", "class": "linear_algebra", "raw": "We bound ‖A‖_F by tr(AᵀA) and use A† for the pseudo-inverse.", "spoken": "we bound the norm of a sub f by the trace of a transpose a and use a dagger for the pseudo inverse.", "block": "paragraph"}
{"id": "cs_stats_46", "class": "results_table", "raw": "ResNet-50 | 76.1 ± 0.2† | —", "spoken": "res net 50, 76.1 plus or minus 0.2, not reported", "block": "table"}
{"id": "cs_stats_47", "class": "results_table", "raw": "Acc. ↑", "spoken": "accuracy, higher is better", "block": "table"}
```

Note on `cs_stats_44`: §3c gives "x to the minus 1"; a teacher usually says "x transpose x, inverse" for a
matrix (open question 2). Note on `cs_stats_45`: "pseudo inverse" without a hyphen because the checker
treats `-` as a raw minus.

## 6. Where it hooks in HearNarro (proposal)

| Class | Hook |
| --- | --- |
| 2.1 asymptotic, complexity classes | MATH-3 symbol table (Θ/Ω/O before `(`) plus SYN-4 SPELLED for NP, PSPACE, BPP |
| 2.2 numeric literals | ING-6 prose normalizer (hex, binary, scientific, k/M/B suffixes) |
| 2.3 data units and rates | MATH-3 units table extended with byte/bit/binary prefixes; ING-6 for `pNN` |
| 2.4 versions, addresses, paths, flags | ING-6 prose normalizer |
| 2.5 pseudocode | ING-10 code-listing reader plus MATH-3 (`←`, floor, ceiling) |
| 2.6 logic and types | MATH-3 symbol table (`⊢`, `⊨`, `λ`, `::`, `⟦⟧`) |
| 2.7 grammars and automata | MATH-3 (`::=`, `ε`) with a grammar-block rule in ING-10 |
| 2.8 ML notation | MATH-3 (`⊙`, `⊕`, concatenation `∥`); §3c already covers the rest |
| 2.9 hyperparameters and shapes | ING-6 (`top-k`, `k-NN`, `n-gram`), TERM-4 (`lr`), MATH-2 ("by" rule) |
| 2.10 model and dataset names | TERM-1 lexicon plus SYN-4 overrides |
| 2.11 code in prose and keyboard | TERM-5 identifiers plus a new code-operator table in ING-6 |
| 2.12 test reporting | ING-6 prose normalizer (a stats-report pass; leading-dot decimals) |
| 2.13 descriptives, effect sizes, CI | ING-6 stats-report pass plus TERM-4 expansion table (M, SD, CI ...) |
| 2.14 distributions and estimators | MATH-3 (distribution names after `∼`) plus TERM-4 (i.i.d., MLE) |
| 2.15 linear algebra | MATH-3 (dagger, rank, diag); §3c covers the rest |
| 2.16 results tables | new per-document setting "read tables row by row" with ING-3 table structure |

## 7. Sources

- https://xlinux.nist.gov/dads//HTML/bigOnotation.html — NIST DADS: "f of n is big oh of g of n" spoken form.
- https://www.cs.hmc.edu/courses/2003/spring/cs60/complexity_files/slide0025.htm — HMC lecture slide: O is the letter "oh", for "order".
- https://iankelling.org/blog/say-on2.html — counts ~92 spoken variants of O(n²); no single standard (why a fixed wording is needed).
- https://www.physics.nist.gov/cgi-bin/cuu/Info/Units/binary.html — NIST: IEC binary prefixes kibi..., not SI; pronunciation guidance.
- https://searchstorage.techtarget.com/definition/Kibi-mebi-gibi-tebi-pebi-and-all-that — "KIH-bee" respelling.
- https://course.ccs.neu.edu/cs3000/resources/latex_pseudocode.pdf — CLRS-style pseudocode: assignment read "gets"; arrays 1-indexed.
- https://dk-01.installer.hardenedbsd.org/ctan/macros/latex/contrib/pseudocode/pseudocode.tex — LaTeX pseudocode package: left arrow is assignment.
- https://socscistatistics.com/tutorials/ttest/default.aspx — APA t-test format t(df) = value, p = value.
- https://www.scribbr.com/?p=306043 — APA statistics reporting; leading zero dropped for statistics bounded by 1.
- https://www.columbusstate.edu/graduate-school/_docs/research-writing-bootcamp/fall-2023/reporting-quantitative-results-apa.pdf — APA quantitative reporting conventions.
- https://www.jcu.edu.sg/_media/documents/student-life/student-support-services/learning-support/7th-editions/Common-Statistical-Symbols-and-Greek-letters-in-APA-7th.pdf — APA 7 statistical symbols and abbreviations (M, SD, Mdn, ηp²).
- https://stats.libretexts.org/Bookshelves/Introductory_Statistics/Mostly_Harmless_Statistics_(Webb)/zz%3A_Back_Matter/22%3A_Greek_Letter_Pronunciations — Greek letter pronunciations in statistics (eta, chi).
- https://stat.ethz.ch/pipermail/r-help/2019-October/464434.html — "chi-square" vs "chi-squared" both in use.
- https://www.ets.org/research/policy_research_reports/publications/report/2016/jwog.html — ClearSpeak: classroom-like speech for algebra (the style §3c follows); no statistics-specific rules found.
- https://research.tudelft.nl/en/publications/code-phonology-an-exploration-into-the-vocalization-of-code — Hermans et al.: code vocalisation is inconsistent; proposes a shared standard.
- https://www.academia.edu/50960478/Spoken_Programs — Begel, Spoken Java: expert programmers' verbalisation of code, including punctuation.

## 8. Open questions for the supervisor

1. After `∼`, read single-letter `N` as "normal" ("x distributed as normal of 0, 1")? §3c's own example says
   "n of 0, 1"; this note keeps §3c and expands only multi-letter names (Bin, Pois). A teacher says
   "normal with mean mu and variance sigma squared".
2. Matrix inverse: keep §3c "a to the minus 1" or add "a inverse" when the base is a capital letter (matrix
   convention)? The same for `‖A‖_F` "the frobenius norm of a".
3. Model size suffix inside a name (`LLaMA-2-7B`): "7 b" (what practitioners say) or "7 billion"?
4. Scientific literals: "3 e minus 4" (ML practice, chosen) or "3 times 10 to the minus 4" (maths reading)?
5. SQL "sequel" or "s q l"; MAP spelled or "map"; ViT spoken or spelled. These are house choices.
6. Results tables: is reading a table row by row with headers in scope for M5, or is a table still announced
   and skipped (ING-3)? Bold-best needs font runs the extractor may not keep.
7. Stats abbreviation expansion (M → "mean") needs a reliable "statistics position" detector; is a sentence
   rule (abbreviation `=` number inside parentheses or a table header) acceptable, or should ING-11 gain a
   `stats` flag?
8. Leading-dot decimals "point 0 5": should this apply in every document (ING-6), or only in stats position?
   It is unambiguous, so this note proposes everywhere.
