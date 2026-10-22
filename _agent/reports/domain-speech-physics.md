TASK        domain-speech-physics
STATUS      done
ASSUMED     Where §3c and a physics classroom habit differ, the note keeps §3c's wording ("epsilon sub 0", "10 to the 8", plural unless 1) and lists the classroom form as an open question. Particles default to letter reading ("e minus"); names only under a proposed per-document setting. Prose words in pairs keep their case, as math_speech.jsonl prose pairs do.

RESULT      1. Probe of today's normalize() on 15 physics strings, each with a verdict — done — _agent/results/855_physics_probe_today.txt (1 correct, 7 symbol leaked, 7 wrong + symbol leaked)
            2. Note covers every SCOPE class with Detection, Rule, Wording table, Source, Confidence; unsourced rules marked proposed — done — _agent/research/domain-speech/physics.md §2.1–2.11; _agent/results/857_physics_note_sections.txt
            3. ≥30 raw→spoken pairs, jsonl shape, consistent with note and §3c — done (57 pairs, 0 banned wordings, 0 non-ASCII or symbol leaks) — _agent/results/856_physics_pairs_check.txt
            4. Context ambiguities and TERM-1 lexicon needs listed — done — physics.md §3 (16 ambiguities) and §4 (58 terms)

OBSERVATIONS
- Today's normalizer emits "goes to" for → and "nabla" for ∇, both banned by §3c (probe lines 08, 11, 12); it reads Ω as "omega" (03, 13) and glues "51 degrees30′N" (15).
- Flattened superscripts ("3.0 × 108") cannot be told from real numbers without ING-3 font-size runs; the note flags this as a dependency.
- No source found prescribes spoken forms for units: per the NIST pages surfaced in search 1, SP 811, SP 330 and the SI Brochure deliberately leave verbal pronunciation out. Written-name rules (per, squared, square/cubic) are used as the proxy.
- The reaction arrow wording ("yields") must be shared with the chemistry note; the element-symbol table too.
- AIP, IEEE, APS, DAISY/NISO and NVDA/JAWS were not retrieved within the 8-search cap; rules that would rest on them are marked proposed.
- Counts: 11 notation classes (10 SCOPE classes, astronomy and geoscience split, plus unit-vs-variable as its own class); 57 pairs; 8 WebSearch calls + 1 WebFetch.

EVIDENCE    _agent/results/855_physics_probe_today.txt — 15 strings, today's spoken output, verdict per line, tally
            _agent/results/856_physics_pairs_check.txt — jsonl parse: 57 pairs, unique ids, keys, classes, 0 violations against math_convention.json banned list
            _agent/results/857_physics_note_sections.txt — section headings 1–8 and 2.1–2.11 present, 11 Confidence lines

FILES WRITTEN     _agent/research/domain-speech/physics.md
                  _agent/results/855_physics_probe_today.txt
                  _agent/results/856_physics_pairs_check.txt
                  _agent/results/857_physics_note_sections.txt
                  _agent/reports/domain-speech-physics.md
                  (scratch, outside the repo: <scratchpad>/scratchpad/probe.py)
FILES READ BEYOND THE BRIEF     none (check_math_convention.py grepped for its CLI only)

UNVERIFIED  NIST SP 811 "kilohm"/"megohm" prefix-vowel elision (prior knowledge, not fetched)
            "times ten to the" and "ket psi"/"bra phi"/"h bar" as classroom readings (no source stating the spoken form was found)
            IEEE component-subscript style and IAU M☉ style (not retrieved)
            SI Brochure wording (search summaries only; the PDF was not fetched)
NOT DONE    none
DRAFTS      none

OUTPUT
856: pairs: 57 | unique ids: True | keys ok: True | violations: 0
     classes: units 13, unit_vs_variable 3, scientific_notation 4, uncertainty 5, equations_in_words 1, vectors 7, quantum 7, nuclear 2, particle 2, constants 3, circuits 4, temperature 1, astronomy 4, geoscience 1
855 tally: correct 1 (14); symbol leaked 7 (01,03,04,06,09,10,13); wrong + symbol leaked 7 (02,05,07,08,11,12,15)
