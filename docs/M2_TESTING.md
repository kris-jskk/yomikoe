# Testing M2 (synthesis + stream) by hand

About 20 minutes. You start the API with the fake backend and then with Kokoro, fetch a voice
list and one segment's audio with `curl` at 1.0x and 2.5x, listen to it, check the cache with
`HEAD`, run the smoke script's audio pass over all 15 text fixtures, run the benchmark and the
model tests. M2 has no UI yet; what you are checking is that a stored segment becomes playable
audio with word timestamps that line up with the segment text (SYN-1 to SYN-6, gate in
`docs/PRD.md`).

All commands run from `api/`. Use two terminals: one for the server, one for the rest. Every
command below was run on 2026-10-16 (transcript `_agent/results/337_m2_testing_transcript.txt`);
the numbers in section 9 come from those runs.

## 1. Prerequisites

Everything from `docs/M1_TESTING.md` section 1, plus:

- The `tts` extra for real speech (PyTorch CPU, misaki without extras, spaCy and its small
  English model, inflect). Without it only the fake backend runs.
- Optional: the `opus` extra (`opuscodec`, Apache-2.0) for Ogg Opus audio instead of WAV.
- No ffmpeg, no espeak, no GPU.

```bash
cd api
uv pip install --python .venv/bin/python -e ".[dev,tts]"        # add ,opus for Ogg Opus
.venv/bin/python scripts/check_licences.py | tail -1            # TOTAL ... VIOLATIONS 0 []
```

**The model.** Kokoro-82M downloads from the Hugging Face Hub on the first Kokoro start, at the
revision pinned in config (`f3ff3571791e39611d31c381e3a41a3af07b4987`, D15). It lands in
`$HF_HOME/hub/models--hexgrad--Kokoro-82M/` (default `~/.cache/huggingface`): the weights file
`kokoro-v1_0.pth` is 327 MB, `config.json` 2 KB, and each voice pack (`voices/<id>.pt`) about
0.5 MB, fetched the first time that voice is used. Set `HF_HOME` to a persistent directory
before the first run; every later start loads from disk in about 2 s.

## 2. Start the server (terminal 1)

Fake backend (silent audio with exact timing, 80 ms per word at 1.0x; no model needed):

```bash
cd api
export HN_DATA=$HOME/hearnarro-m2        # any empty directory
HEARNARRO_TTS_BACKEND=fake .venv/bin/python -m hearnarro serve --data-dir "$HN_DATA" --port 8765
```

Kokoro (real speech; stop the fake server first, or use another port and data dir):

```bash
HEARNARRO_TTS_BACKEND=kokoro .venv/bin/python -m hearnarro serve --data-dir "$HN_DATA" --port 8765
```

The revision defaults to the D15 pin; set `HEARNARRO_KOKORO_REVISION=<hash>` only to test a
different one. The model loads before the server accepts requests (about 2 s once cached).
Other settings: `HEARNARRO_LOOKAHEAD` (segments synthesized ahead, default 5, SYN-5) and
`HEARNARRO_AUDIO_FORMAT` (`wav` default, `opus` needs the `opus` extra, D16).
`HEARNARRO_TRIM_LEAD_MS` (default 60) and `HEARNARRO_TRIM_TAIL_MS` (default 150) set the
silence kept before and after each clip's sound (SYN-1); together they are the pause between two
sentences. Cached clips keep the trim they were made with: use a fresh data dir after changing them.

## 3. Voices, one segment, two speeds (terminal 2)

```bash
cd api
export HN_DATA=$HOME/hearnarro-m2
B=http://127.0.0.1:8765
V=af_heart                               # fake_f1 with the fake backend
curl -s $B/voices | python3 -c 'import json,sys; v=json.load(sys.stdin); print(len(v), "voices:", [(x["id"], x["gender"]) for x in v])'
curl -s -o /dev/null -w '%{http_code}\n' -F file=@tests/fixtures/pdfs/report_01_zero_trust.pdf $B/documents
curl -s $B/documents/1 | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["status"], d["page_count"])'
curl -s "$B/documents/1/segments?from=0&limit=2" | python3 -c 'import json,sys; [print(s["id"], s["type"], repr(s["text"]), repr(s["normalized_text"])) for s in json.load(sys.stdin)["segments"]]'
```

| Step | What you should see |
| --- | --- |
| Voices | fake: `6 voices`, `fake_f1..f3` female and `fake_m1..m3` male; Kokoro: `10 voices`, `af_heart, af_bella, af_nicole, am_michael, am_fenrir, am_puck, bf_emma, bf_isabella, bm_george, bm_fable` |
| Upload | `202` |
| Poll | `ready 4` (repeat if it still says `parsing`) |
| First segments | `1 heading 'NIST Special Publication 800-207' 'N I S T Special Publication 800-207'` and `2 heading 'Zero Trust Architecture' ...` |

Now the audio for segment 1 (the segment `id` from the last command):

```bash
curl -s -o /dev/null -w '%{http_code}\n' -I "$B/audio/1?voice=$V&speed=1.0"      # 404: not cached yet
curl -s -D h1.txt -o seg1_x1.0.wav -w 'HTTP %{http_code}  %{size_download} bytes  %{time_total} s\n' "$B/audio/1?voice=$V&speed=1.0"
grep -i -E '^(content-type|x-duration-ms|x-timestamps)' h1.txt | cut -c1-220
curl -s -D h2.txt -o seg1_x2.5.wav -w 'HTTP %{http_code}  %{size_download} bytes  %{time_total} s\n' "$B/audio/1?voice=$V&speed=2.5"
grep -i -E '^(content-type|x-duration-ms)' h2.txt
curl -s -o /dev/null -w '%{http_code}\n' -I "$B/audio/1?voice=$V&speed=1.0"      # 200: cached
curl -s -o /dev/null -w 'second GET (cache hit): HTTP %{http_code} %{time_total} s\n' "$B/audio/1?voice=$V&speed=1.0"
afinfo seg1_x1.0.wav | grep -E 'File type|Data format|estimated duration'
curl -s -o seg1_x1.25.wav -w 'HTTP %{http_code}  %{size_download} bytes\n' "$B/audio/1?voice=$V&speed=1.25"   # 0.05 steps: 1.25x, 1.75x are valid
afplay seg1_x1.0.wav; afplay seg1_x2.5.wav                                        # listen
```

What Kokoro returned in the recorded run: `HTTP 200 195644 bytes 0.36 s` at 1.0x with
`content-type: audio/wav`, `x-duration-ms: 4075` and `x-timestamps` starting
`[{"word": "N", "start_ms": 375, "end_ms": 525, "char_start": 0, "char_end": 1}, ...`; at 2.5x
`82604 bytes`, `x-duration-ms: 1720` (2.5x is synthesized at 2.0x and time-stretched, D17).
`HEAD` then answers `200`, and the second GET is a cache hit in about 7 ms. `afinfo` reports
`WAVE`, `1 ch, 24000 Hz, Int16`. With the fake backend the same steps give 560 ms and 224 ms of
silence.

At 1.0x you should hear the heading spoken by `af_heart` (American English, female), with
"NIST" as separate letters; at 2.5x the same sentence, fast but at normal pitch. Listening was
not part of the recorded run (the transcript checks the files with `afinfo`).

Errors:

```bash
curl -s -w ' %{http_code}\n' "$B/audio/1?voice=af_nope&speed=1.0"   # unknown voice 'af_nope' 422
curl -s -w ' %{http_code}\n' "$B/audio/1?voice=$V&speed=0.45"       # speed must be 0.5..3.0 in 0.05 steps 422 (so are 3.05 and 1.23)
curl -s -w ' %{http_code}\n' "$B/audio/999999?voice=$V&speed=1.0"   # 404
```

## 4. Ogg Opus instead of WAV (optional, D16)

Install the `opus` extra, restart the server with `HEARNARRO_AUDIO_FORMAT=opus` on a fresh data
dir, and repeat section 3 with `.ogg` file names. In the recorded run (Kokoro): `content-type:
audio/ogg`, 23919 bytes at 1.0x (8x smaller than the WAV), the same `x-timestamps` and
`x-duration-ms: 4075`; `afinfo` reports `Oggf`, `1 ch, 48000 Hz, opus` (decoders play Opus at
48 kHz; the encoder takes the 24 kHz model output as is). `afplay` plays it. Whether every
browser decodes Ogg Opus is checked in M3.

## 5. Where audio lands

```
$HN_DATA/audio/<document_id>/<segment_id>/<voice>_<speed>.wav   (.ogg with Opus)
```

```bash
find "$HN_DATA/audio" -type f | sort | head
```

Speeds are written with two decimals. After the requests above you see
`audio/1/1/af_heart_1.00.wav`, `af_heart_1.25.wav`, `af_heart_2.00.wav` (the native-speed
intermediate of the stretched path) and `af_heart_2.50.wav`, plus `audio/1/2/af_heart_1.00.wav`
and further segments that the lookahead queue synthesized ahead.
Reset as in M1: stop the server and `rm -rf "$HN_DATA"`.

## 6. The smoke script's audio pass

With the server running:

```bash
.venv/bin/python scripts/m1_smoke.py --base-url $B --audio
```

It runs the M1 gate first (uploads the 15 text fixtures, prints `RESULT: PASS`), then the audio
pass: `GET /voices` (at least 6 voices, both genders), and for the first 3 segments with words
of every ready document, `GET /audio` at 1.0x, 1.25x and 2.5x with the first voice. Each row shows a
`HEAD` before the GET (`pre`: 404 = synthesized for this request, 200 = the lookahead queue had
it already), HTTP code, content type, `X-Duration-Ms`, word count, bytes, the time to the full
response (`ttfa_ms`) and a `HEAD` after (must be 200). It checks the timestamps are sorted,
non-overlapping, inside the duration, and that each char span lies inside the segment text.
The last line is the summary; any failure makes the exit code 1. The script does not care
which backend the server runs.

## 7. Benchmark

```bash
.venv/bin/python scripts/bench.py --backend kokoro --n 20      # writes ../bench/<date>.json
```

Prints cold start (imports and model load) and, per speed 0.5/1.0/2.0/3.0, TTFA mean/p50/max,
real-time factor and how many sentences reached first audio within 2 s. Sentences are the first
20 body sentences of 80 to 200 characters from the fixtures; there is no audio cache involved.
`--n 5` is a one-minute version.

## 8. The test suite and the model tests

```bash
.venv/bin/python -m pytest -q                                      # everything, FakeBackend only
HEARNARRO_TEST_MODEL=1 HEARNARRO_TTS_BACKEND=kokoro .venv/bin/python -m pytest -q tests/test_kokoro_backend.py tests/test_syn_gate.py
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

The first command needs no model; the tests marked `model` are skipped and the Opus tests skip
without the `opus` extra. The second loads Kokoro and runs the backend tests and the M2 gate:
time to first audio at most 2000 ms at 0.5/1.0/2.0/3.0x on the spec's 150-character sentence.
Set `HEARNARRO_TTS_BACKEND=kokoro`: without it the two Kokoro tests in `test_syn_gate.py` fail on
"HEARNARRO_KOKORO_REVISION must be set" because the settings fall back to the fake backend.

## 9. What good looks like

| Check | Expected (recorded 2026-10-16, Apple laptop CPU) |
| --- | --- |
| `/voices` | fake 6, Kokoro 10; both genders |
| Segment 1, Kokoro, 1.0x | `200 audio/wav`, 4075 ms of audio, first response in about 0.36 s |
| Segment 1, Kokoro, 2.5x | `200 audio/wav`, 1720 ms, about 0.38 s |
| `HEAD` before / after the first GET | `404` / `200`; the repeat GET is a cache hit in under 10 ms |
| Opus (optional) | `200 audio/ogg`, about 8x smaller than WAV, identical `X-Timestamps` |
| Smoke `--audio`, fake | `audio: 90 requests, 0 failures, TTFA mean 6 ms / max 16 ms` (`_agent/results/335_smoke_audio_fake.txt`) |
| Smoke `--audio`, Kokoro | `audio: 90 requests, 0 failures, TTFA mean 581 ms / max 2185 ms`, gate `RESULT: PASS` (`_agent/results/336_smoke_audio_kokoro.txt`) |
| Benchmark, `--n 20` | cold start 2.33 s; TTFA mean 1883 / 862 / 458 / 469 ms at 0.5 / 1.0 / 2.0 / 3.0x; RTF 0.08 to 0.12; 14 of 20 within 2 s at 0.5x, 20 of 20 at the other speeds (`_agent/results/314_bench.txt`) |
| Model tests | Kokoro gate TTFA 1842 / 997 / 472 / 483 ms at 0.5 / 1.0 / 2.0 / 3.0x (`_agent/results/311_model_tests.txt`); re-run for the M2 close: 12 passed (`_agent/results/342_model_tests_kokoro_env.txt`) |
| pytest | 0 failed |

The Kokoro smoke maximum (2185 ms) is one 6.05 s sentence at 1.0x (`tables_01_pfn_bayes`,
segment 731); its other cold requests took 0.15 to 1.5 s. Why that one was slow (lookahead work
for the previous document still queued, or the OOV fallback) was not measured. The smoke times
the full response, not the player's wait.

## 10. Known limits

- **Adding a pronunciation.** Add one line to `OVERRIDES` in
  `api/hearnarro/synthesis/lexicon_overrides.py` (lower-case word -> phonemes in misaki's alphabet,
  e.g. `"uber": "ˈubəɹ"`), then run `HEARNARRO_TEST_MODEL=1 pytest tests/test_kokoro_backend.py -k override`;
  re-ingest or clear the document's audio cache to hear it. Acronym readings: `SPOKEN`, `SPELLED`,
  `COLLOCATIONS`, `RESPELL` in `api/hearnarro/synthesis/acronyms.py`. All-caps headings
  ("ERIC'S NOTE", "BUILDING WEALTH", "FOREWORD") are read as words, not spelled; a lone acronym in
  a normal sentence keeps its decision ("the CEO said" spelled, "a TED talk" spoken), and so do
  `SPELLED` and document-defined acronyms inside a heading. Hear it:
  `~/hearnarro-m1/audio_samples/erics_note_1.0x.wav`. Cached audio of a heading synthesized before
  this change keeps the spelled reading until the document's audio cache is cleared.

- **0.5x tail (D19).** At half speed the model generates twice the audio before the first byte,
  so long sentences (6 of 20 benchmark sentences of up to 200 characters) exceed 2 s. The M2 gate
  is measured on the spec's 150-character sentence, which passes. M3 adds clause-level chunking
  of the first sentence at speeds below 1.0 and measures the wait in the player.
- **Out-of-vocabulary words.** misaki's lexicon does not know many names and coined words; the
  backend falls back to a vendored g2p_en predictor, then to spelling letters, and logs
  `kokoro OOV word ...` once per word. Unusual names can sound wrong; number ranges such as
  `20.00–42.86` are spelled piece by piece.
- **WAV by default.** About 48 KB per second of audio. Ogg Opus is about 6 to 8x smaller but is
  opt-in until M3 checks browser decoding (Safari before 18.4 reportedly fails on Ogg Opus).
- **2.1x to 3.0x** is the 2.0x synthesis time-stretched in process (WSOLA, D17); pitch is
  kept, and the stretched file is cached next to the 2.0x one.
- **No UI.** Playback, highlighting and the voice/speed pickers are M3.
