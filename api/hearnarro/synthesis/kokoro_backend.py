"""KokoroBackend: the only module that names a TTS model (SYN-2, SYN-4; D15).

``hexgrad/Kokoro-82M`` (Apache-2.0) on PyTorch CPU, every file fetched with
``hf_hub_download(revision=...)`` at a pinned revision. GPL-free by construction (D15):

- the model code is vendored (``hearnarro.synthesis.kokoro_model``, Apache-2.0); the PyPI
  ``kokoro`` package and its ``KPipeline`` (which imports ``misaki.espeak`` -> phonemizer) are
  never installed or imported;
- ``misaki`` is installed without extras; its top-level ``from num2words import num2words``
  (LGPL) is served by ``hearnarro.synthesis.compat.num2words`` registered before import;
- out-of-vocabulary words, which misaki would drop silently, go through ``_OOVFallback``:
  the CMU Pronouncing Dictionary for the whole word (vendored BSD data,
  ``hearnarro.synthesis.cmudict``; ARPAbet -> Kokoro IPA by ``arpabet_to_kokoro``), else per
  camel-case piece misaki's lexicon, then cmudict, then the vendored g2p_en predictor, else
  letter spelling; one warning per OOV word per document naming the tier(s) used.

Pronunciation tiers, in order: ``lexicon_overrides`` -> misaki gold/silver lexicon -> cmudict ->
g2p_en neural fallback -> letters.

Custom pronunciations (SYN-4): ``hearnarro.synthesis.lexicon_overrides`` entries are written
into misaki's gold lexicon when a G2P is built, and after G2P every token they match (case-
insensitive, possessive/plural suffixes) gets the override's phonemes, before the all-caps step;
each entry used is logged once per document at INFO.

All-caps context (SYN-4): before G2P the segment goes through
``hearnarro.synthesis.acronyms.fold_caps``; in a heading or emphasized run ("ERIC'S NOTE") the
caps words are case-folded ("Eric's Note") so misaki reads them as words instead of spelling
them, the tokens get their original text back, and the folded ones skip the per-token step.

All-caps tokens (SYN-4, ING-6): after misaki's G2P, every other token of 2+ capital letters is
re-read by ``hearnarro.synthesis.acronyms.decide`` (overrides, collocation with the next word,
the document's definitions from ``SynthContext``, misaki's lexicon, a pronounceability
heuristic). Spoken: the lexicon entry of its ``RESPELL`` word if it has one, else misaki's own
word phonemes if it had them, else the lexicon entry, else the
g2p_en predictor on the lowercase form. Spelled: the token is replaced by one token per letter
(no spaces between them, so the phoneme string equals misaki's letter spelling), each with its
own duration; the letters fold back into one WordTimestamp spanning the original token. A
possessive/plural ("CEO's", "PDFs") is decided on its letters and the voiced suffix joins the
last letter token ("O's", "Fs"). Each
(document, token) decision is logged once at INFO.

Word timestamps (contract for ``SynthResult.timestamps``):
- one ``WordTimestamp`` per whitespace-delimited word of the input text, in order; the word
  text and ``(char_start, char_end)`` are that slice of the input;
- times come from Kokoro's predicted durations (``pred_dur``, 600 samples = 25 ms per frame):
  a misaki token spans the frames of its own phoneme characters (not the following space);
  a word starts at its first timed token's start and ends at its last timed token's end;
- a word whose tokens all have empty phonemes (e.g. a lone symbol) gets a zero-length interval
  at the previous word's end (0 for the first word);
- times are clamped so that starts and ends never decrease, start <= end, end <= duration.

Speed and the leading BOS token (SYN-3, D6): the model renders its first ~250-330 ms as
near-silence whatever is scheduled there, and Kokoro's own forward divides every predicted
duration by ``speed``, BOS included. At 2.0 the BOS shrinks from ~325 to ~175 ms and the
first word falls into that dead start (onset 73-112 ms after the word's start, first word
25-46 dB quieter; results 343). ``_infer`` therefore runs the model with the BOS duration
never shorter than its speed-1.0 value; every other token is divided by ``speed`` as before.
Speeds <= 1.0 are unchanged.
"""

from __future__ import annotations

import copy
import logging
import re
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import numpy as np

from hearnarro.synthesis import cmudict, lexicon_overrides
from hearnarro.synthesis.acronyms import (
    RESPELL,
    Decision,
    caps_fold_spans,
    decide,
    fold_caps,
    is_acronym,
    spell_phonemes,
    split_suffix,
    suffix_phonemes,
)
from hearnarro.synthesis.backend import SynthContext, SynthResult, Voice, WordTimestamp

log = logging.getLogger(__name__)

MODEL_REPO = "hexgrad/Kokoro-82M"
# D15: pinned revision (settings.DEFAULT_KOKORO_REVISION mirrors this).
PINNED_REVISION = "f3ff3571791e39611d31c381e3a41a3af07b4987"
MODEL_FILE = "kokoro-v1_0.pth"
SAMPLE_RATE = 24_000
FRAME_MS = 25  # one pred_dur frame = 600 samples at 24 kHz
MAX_PHONEMES = 510  # context 512 minus BOS/EOS

# (id, display name). Prefix: a/b = American/British English, f/m = female/male.
_VOICES: tuple[tuple[str, str], ...] = (
    ("af_heart", "Heart"),
    ("af_bella", "Bella"),
    ("af_nicole", "Nicole"),
    ("am_michael", "Michael"),
    ("am_fenrir", "Fenrir"),
    ("am_puck", "Puck"),
    ("bf_emma", "Emma"),
    ("bf_isabella", "Isabella"),
    ("bm_george", "George"),
    ("bm_fable", "Fable"),
)
_LANG = {"a": "en-US", "b": "en-GB"}
_GENDER = {"f": "female", "m": "male"}

# CMU ARPAbet (stress digits stripped) -> misaki/Kokoro phonemes. Vowels by stress below.
_ARPA_CONS = {
    "B": "b", "CH": "ʧ", "D": "d", "DH": "ð", "F": "f", "G": "ɡ", "HH": "h", "JH": "ʤ",
    "K": "k", "L": "l", "M": "m", "N": "n", "NG": "ŋ", "P": "p", "R": "ɹ", "S": "s",
    "SH": "ʃ", "T": "t", "TH": "θ", "V": "v", "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ",
}  # fmt: skip
_ARPA_VOWEL = {
    "AA": "ɑ", "AE": "æ", "AO": "ɔ", "AW": "W", "AY": "I", "EH": "ɛ", "EY": "A",
    "IH": "ɪ", "IY": "i", "OW": "O", "OY": "Y", "UH": "ʊ", "UW": "u",
}  # fmt: skip


def voice_from_id(voice_id: str) -> Voice:
    name = dict(_VOICES)[voice_id]
    lang = _LANG[voice_id[0]]
    return Voice(
        id=voice_id,
        name=f"{name} ({lang[-2:]})",
        backend="kokoro",
        language=lang,
        gender=_GENDER[voice_id[1]],
    )


def arpabet_to_kokoro(arpa: list[str], british: bool = False) -> str:
    """``["Z", "IH0", "G", "AA1", ...]`` -> ``"zɪɡˈɑ..."``: stress mark before the vowel."""
    out = []
    for p in arpa:
        base, stress = p.rstrip("012"), p[len(p.rstrip("012")) :]
        mark = {"1": "ˈ", "2": "ˌ"}.get(stress, "")
        if base in _ARPA_CONS:
            out.append(_ARPA_CONS[base])
        elif base == "AH":
            out.append(mark + ("ʌ" if mark else "ə"))
        elif base == "ER":
            out.append(mark + (("ɜː" if british else "ɜɹ") if mark else ("ə" if british else "əɹ")))
        elif base in _ARPA_VOWEL:
            v = _ARPA_VOWEL[base]
            out.append(mark + ("Q" if british and v == "O" else v))
    return "".join(out)


class _OOVFallback:
    """misaki ``G2P.fallback`` hook: ``(token) -> (phonemes | None, rating)``."""

    def __init__(
        self,
        lexicon: Any,
        predictor: Any,
        vocab: set[str],
        british: bool,
        cmu: dict[str, list[str]] | None = None,
    ) -> None:
        self.lexicon, self.predictor, self.vocab, self.british = lexicon, predictor, vocab, british
        self.cmu = cmu or {}
        self.used: list[tuple[str, str, str]] = []  # (word, phonemes, methods) for diagnostics
        self.document_id: int | None = None  # set by the backend for each synthesis
        self._logged: set[tuple[int | None, str]] = set()

    def _cmu(self, w: str) -> str | None:
        arpa = self.cmu.get(w.lower())
        return arpabet_to_kokoro(arpa, self.british) if arpa else None

    def _look(self, w: str) -> str | None:
        for k in (w, w.lower(), w.capitalize(), w.upper()):
            for d in (self.lexicon.golds, self.lexicon.silvers):
                v = d.get(k)
                if isinstance(v, dict):
                    v = v.get("DEFAULT") or next(iter(v.values()), None)
                if v:
                    return str(v)
        return None

    def _spell(self, w: str) -> str:
        return "".join(self._look(c.upper()) or "" for c in w if c.isalnum())

    def __call__(self, tk: Any) -> tuple[str | None, int]:
        word, tail = tk.text, ""
        if word.endswith(("'s", "’s")):
            word, tail = word[:-2], "z"  # voiced below, after the word's last sound
        whole = self._cmu(word) if word.isalpha() else None
        parts = [word] if whole else re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", word)
        pieces, methods = [], []
        for part in parts:
            ps, how = (whole, "cmudict") if whole else (self._look(part), "lexicon")
            if not ps and part.isalpha():
                ps, how = self._cmu(part), "cmudict"
            if not ps and part.isalpha() and not part.isupper():
                ps, how = arpabet_to_kokoro(self.predictor.predict(part), self.british), "g2p_en"
            if not ps:
                ps, how = self._spell(part), "spelled"
            pieces.append(ps)
            methods.append(how)
        if tail:
            tail = suffix_phonemes("".join(pieces))
        phonemes = "".join(c for c in "".join(pieces) + tail if c in self.vocab) or None
        self.used.append((tk.text, phonemes or "", "+".join(methods)))
        if (self.document_id, tk.text) not in self._logged:
            self._logged.add((self.document_id, tk.text))
            log.warning(
                "kokoro OOV word %r -> %r via %s (document=%s)",
                tk.text, phonemes, "+".join(methods) or "none", self.document_id,
            )  # fmt: skip
        return phonemes, 1


@dataclass
class _Timed:
    text: str
    start_ms: int | None
    end_ms: int | None


def _chunks(tokens: list[Any]) -> Iterator[list[Any]]:
    """Split misaki tokens so each chunk's phoneme string stays within MAX_PHONEMES,
    preferring to cut after sentence punctuation, then clause punctuation."""
    cur: list[Any] = []
    count = 0
    for t in tokens:
        n = len(t.phonemes) + (1 if t.whitespace else 0)
        if cur and count + n > MAX_PHONEMES:
            cut = len(cur)
            for marks in ("!.?…", ":;", ",—"):
                z = next((i for i in range(len(cur) - 1, -1, -1) if cur[i].phonemes in marks), None)
                if z is not None and z > 0:
                    cut = z + 1
                    break
            yield cur[:cut]
            cur = cur[cut:]
            count = sum(len(x.phonemes) + (1 if x.whitespace else 0) for x in cur)
        cur.append(t)
        count += n
    if cur:
        yield cur


def _phoneme_string(tokens: list[Any]) -> tuple[str, list[tuple[int, int] | None]]:
    """Kokoro input for a chunk and each token's [start, end) char range in it (None if empty)."""
    ps = ""
    spans: list[tuple[int, int] | None] = []
    for t in tokens:
        if t.phonemes:
            spans.append((len(ps), len(ps) + len(t.phonemes)))
            ps += t.phonemes
        else:
            spans.append(None)
        if t.whitespace and ps and not ps.endswith(" "):
            ps += " "
    return ps.rstrip(), spans


def word_timestamps(text: str, timed: list[_Timed], duration_ms: int) -> list[WordTimestamp]:
    """Fold token times into one WordTimestamp per whitespace word (rule in module docstring)."""
    words = [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]
    if not words:
        return []
    acc: list[list[int]] = [[] for _ in words]
    pos, wi = 0, 0
    for tk in timed:
        i = text.find(tk.text, pos) if tk.text else -1
        if i >= 0:
            pos = i + len(tk.text)
            while wi + 1 < len(words) and words[wi][1] <= i:
                wi += 1
        if tk.start_ms is not None and tk.end_ms is not None:
            acc[wi] += [tk.start_ms, tk.end_ms]
    out: list[WordTimestamp] = []
    prev = 0
    for (cs, ce), times in zip(words, acc, strict=True):
        start, end = (min(times), max(times)) if times else (prev, prev)
        start = min(max(start, prev), duration_ms)
        end = min(max(end, start), duration_ms)
        out.append(WordTimestamp(text[cs:ce], start, end, cs, ce))
        prev = end
    return out


class KokoroBackend:
    """Kokoro-82M, CPU. Construct once (loads model + spaCy, ~2 s); ``synthesize`` is
    serialised by a lock (one synthesis thread in the service)."""

    name = "kokoro"

    def __init__(self, revision: str = PINNED_REVISION, *, device: str = "cpu") -> None:
        if not revision:
            raise ValueError("KokoroBackend needs a pinned Hugging Face revision")
        from hearnarro.synthesis import compat

        compat.install()  # before misaki.en is imported (num2words shim)
        import torch
        from huggingface_hub import hf_hub_download
        from misaki import en

        from hearnarro.synthesis.g2p_oov import NeuralG2P
        from hearnarro.synthesis.kokoro_model import KModel

        self.revision = revision
        self._torch = torch
        self._en = en
        self._download = hf_hub_download
        config = self._fetch("config.json")
        weights = self._fetch(MODEL_FILE)
        self._model = KModel(repo_id=MODEL_REPO, config=config, model=weights).to(device).eval()
        self._vocab = set(self._model.vocab)
        self._predictor = NeuralG2P()
        self._g2p: dict[bool, Any] = {}
        self._packs: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._acronyms_logged: set[tuple[int | None, str, Decision]] = set()
        self._overrides_logged: set[tuple[int | None, str]] = set()
        self._g2p_for(british=False)  # load the US pipeline (spaCy) now, not on first request

    def _fetch(self, filename: str) -> str:
        return str(self._download(MODEL_REPO, filename, revision=self.revision))

    def _g2p_for(self, british: bool) -> Any:
        if british not in self._g2p:
            g2p = self._en.G2P(trf=False, british=british, fallback=None, unk="")
            g2p.lexicon.golds.update(lexicon_overrides.OVERRIDES)  # before misaki's own entries
            g2p.fallback = _OOVFallback(
                g2p.lexicon, self._predictor, self._vocab, british, cmu=cmudict.load()
            )
            self._g2p[british] = g2p
        return self._g2p[british]

    def _pack(self, voice_id: str) -> Any:
        if voice_id not in self._packs:
            path = self._fetch(f"voices/{voice_id}.pt")
            self._packs[voice_id] = self._torch.load(path, weights_only=True)
        return self._packs[voice_id]

    @property
    def oov_log(self) -> list[tuple[str, str, str]]:
        """(word, phonemes, method) for every OOV word seen, US then GB pipeline."""
        return [u for g in self._g2p.values() for u in g.fallback.used]

    def voices(self) -> list[Voice]:
        return [voice_from_id(v) for v, _ in _VOICES]

    def speed_range(self) -> tuple[float, float]:
        return (0.5, 2.0)

    def synthesize(
        self, text: str, voice_id: str, speed: float, context: SynthContext | None = None
    ) -> SynthResult:
        if voice_id not in dict(_VOICES):
            raise ValueError(f"unknown kokoro voice {voice_id!r}")
        lo, hi = self.speed_range()
        if not lo <= speed <= hi:
            raise ValueError(f"speed {speed} outside native range {lo}..{hi}")
        with self._lock:
            return self._synthesize(text, voice_id, speed, context)

    def _infer(self, ps: str, ref_s: Any, speed: float) -> tuple[np.ndarray, np.ndarray]:
        """``KModel.forward_with_tokens`` with one change: the BOS duration is floored at its
        speed-1.0 value (module docstring). Returns (float32 audio, pred_dur per input id)."""
        torch, m = self._torch, self._model
        ids = [m.vocab[p] for p in ps if p in m.vocab]
        if len(ids) + 2 > m.context_length:
            raise ValueError(f"phoneme chunk too long: {len(ids) + 2} > {m.context_length}")
        input_ids = torch.LongTensor([[0, *ids, 0]]).to(m.device)
        ref_s = ref_s.to(m.device)
        n = input_ids.shape[-1]
        lengths = torch.full((1,), n, device=m.device, dtype=torch.long)
        text_mask = torch.zeros((1, n), dtype=torch.bool, device=m.device)  # no padding
        with torch.inference_mode():
            bert_dur = m.bert(input_ids, attention_mask=(~text_mask).int())
            d_en = m.bert_encoder(bert_dur).transpose(-1, -2)
            s = ref_s[:, 128:]
            d = m.predictor.text_encoder(d_en, s, lengths, text_mask)
            x, _ = m.predictor.lstm(d)
            raw = torch.sigmoid(m.predictor.duration_proj(x)).sum(axis=-1).squeeze(0)
            duration = raw / speed
            duration[0] = torch.maximum(duration[0], raw[0])  # BOS: never shorter than at 1.0
            pred_dur = torch.round(duration).clamp(min=1).long()
            indices = torch.repeat_interleave(torch.arange(n, device=m.device), pred_dur)
            aln = torch.zeros((n, indices.shape[0]), device=m.device)
            aln[indices, torch.arange(indices.shape[0])] = 1
            aln = aln.unsqueeze(0)
            f0, noise = m.predictor.F0Ntrain(d.transpose(-1, -2) @ aln, s)
            asr = m.text_encoder(input_ids, lengths, text_mask) @ aln
            audio = m.decoder(asr, f0, noise, ref_s[:, :128]).squeeze()
        return audio.cpu().numpy().astype(np.float32), pred_dur.cpu().numpy()

    def _tokens(self, text: str, british: bool, context: SynthContext | None = None) -> list[Any]:
        """misaki tokens for ``text`` with all-caps tokens re-read (module docstring) and only
        phoneme symbols the model knows, so char i of the chunk string <-> pred_dur[i + 1]."""
        g2p = self._g2p_for(british)
        g2p.fallback.document_id = context.document_id if context else None
        definitions = context.acronyms if context else {}
        spans = caps_fold_spans(text, definitions)
        folded_text = fold_caps(text, definitions) if spans else text
        _, tokens = g2p(folded_text)
        folded: set[int] = set()
        pos = 0
        for t in tokens:  # original text back on every token (timestamps match on it)
            i = folded_text.find(t.text, pos) if t.text else -1
            if i < 0:
                continue
            pos = i + len(t.text)
            t.text = text[i:pos]
            if any(a < pos and i < b for a, b in spans):
                folded.add(id(t))
        doc = context.document_id if context else None
        for entry in lexicon_overrides.apply(tokens):
            if (doc, entry) not in self._overrides_logged:
                self._overrides_logged.add((doc, entry))
                log.info("pronunciation override document=%s entry=%r", doc, entry)
        tokens = self._pronounce_acronyms(tokens, g2p, british, context, folded)
        for t in tokens:
            t.phonemes = "".join(c for c in (t.phonemes or "") if c in self._vocab)
        return tokens

    def _pronounce_acronyms(
        self,
        tokens: list[Any],
        g2p: Any,
        british: bool,
        context: SynthContext | None,
        folded: set[int] | None = None,
    ) -> list[Any]:
        lex = g2p.lexicon
        look = g2p.fallback._look

        def in_lexicon(w: str) -> bool:
            return w.lower() in lex.golds or w.lower() in lex.silvers

        definitions = context.acronyms if context else {}
        out: list[Any] = []
        for i, t in enumerate(tokens):
            word, suffix = (t.text, "") if is_acronym(t.text) else split_suffix(t.text) or ("", "")
            if (
                not word
                or id(t) in (folded or ())
                or lexicon_overrides.lookup(t.text)
                or lexicon_overrides.lookup(word)
            ):
                out.append(t)
                continue
            nxt = tokens[i + 1].text if i + 1 < len(tokens) and t.whitespace else None
            d = decide(
                word,
                next_word=nxt if nxt and nxt.isalpha() else None,
                definitions=definitions,
                in_lexicon=in_lexicon,
            )
            key = (context.document_id if context else None, word, d)
            if key not in self._acronyms_logged:
                self._acronyms_logged.add(key)
                log.info(
                    "acronym document=%s token=%r decision=%s reason=%s",
                    key[0], t.text, "spoken" if d.spoken else "spelled", d.reason,
                )  # fmt: skip
            if d.spoken:
                spelled_by_misaki = lex.get_NNP(word)[0]
                ps = None
                if word in RESPELL:
                    ps = look(RESPELL[word])
                elif not t.phonemes or t.phonemes.startswith(spelled_by_misaki):
                    ps = look(word) or arpabet_to_kokoro(
                        self._predictor.predict(word.lower()), british
                    )
                if ps:
                    t.phonemes = ps + (suffix_phonemes(ps) if suffix else "")
                out.append(t)
                continue
            letters = {c: look(c) or "" for c in set(word)}
            pieces = spell_phonemes(word, letters)
            if suffix:
                pieces[-1] += suffix_phonemes(pieces[-1])
            for k, (c, ps) in enumerate(zip(word, pieces, strict=True)):
                lt = copy.copy(t)
                last = k == len(word) - 1
                lt.text, lt.phonemes = (c + suffix if last else c), ps
                lt.whitespace = t.whitespace if last else ""
                out.append(lt)
        return out

    def _synthesize(
        self, text: str, voice_id: str, speed: float, context: SynthContext | None = None
    ) -> SynthResult:
        pack = self._pack(voice_id)
        tokens = self._tokens(text, voice_id[0] == "b", context)
        audio_parts: list[np.ndarray] = []
        timed: list[_Timed] = []
        offset_ms = 0.0
        for chunk in _chunks(tokens):
            ps, spans = _phoneme_string(chunk)
            if not ps:
                timed += [_Timed(t.text, None, None) for t in chunk]
                continue
            audio, pred_dur = self._infer(ps, pack[len(ps) - 1], speed)
            frames = np.concatenate([[0], np.cumsum(pred_dur)])  # frames before id k
            for t, span in zip(chunk, spans, strict=True):
                if span is None:
                    timed.append(_Timed(t.text, None, None))
                    continue
                s, e = span  # ids are char index + 1 (BOS at 0)
                timed.append(
                    _Timed(
                        t.text,
                        round(offset_ms + frames[s + 1] * FRAME_MS),
                        round(offset_ms + frames[e + 1] * FRAME_MS),
                    )
                )
            audio_parts.append(audio)
            offset_ms += len(audio) * 1000 / SAMPLE_RATE
        samples = np.concatenate(audio_parts) if audio_parts else np.zeros(0, np.float32)
        pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()
        result = SynthResult(audio=pcm, sample_rate=SAMPLE_RATE)
        result.timestamps = word_timestamps(text, timed, result.duration_ms)
        return result
