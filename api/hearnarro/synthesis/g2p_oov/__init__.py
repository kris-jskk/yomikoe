"""Neural grapheme-to-phoneme predictor for out-of-vocabulary words (D15).

Adapted from ``g2p_en`` 2.1.0 (Apache-2.0, Kyubyong Park & Jongseok Kim; see NOTICE): only the
numpy GRU encoder-decoder and its weights (``checkpoint20.npz``, unchanged). It predicts
CMU ARPAbet phonemes for one lower-case word, e.g. ``predict("zygalski")``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

_GRAPHEMES = ["<pad>", "<unk>", "</s>", *"abcdefghijklmnopqrstuvwxyz"]
_PHONEMES = ["<pad>", "<unk>", "<s>", "</s>"] + [
    "AA0",
    "AA1",
    "AA2",
    "AE0",
    "AE1",
    "AE2",
    "AH0",
    "AH1",
    "AH2",
    "AO0",
    "AO1",
    "AO2",
    "AW0",
    "AW1",
    "AW2",
    "AY0",
    "AY1",
    "AY2",
    "B",
    "CH",
    "D",
    "DH",
    "EH0",
    "EH1",
    "EH2",
    "ER0",
    "ER1",
    "ER2",
    "EY0",
    "EY1",
    "EY2",
    "F",
    "G",
    "HH",
    "IH0",
    "IH1",
    "IH2",
    "IY0",
    "IY1",
    "IY2",
    "JH",
    "K",
    "L",
    "M",
    "N",
    "NG",
    "OW0",
    "OW1",
    "OW2",
    "OY0",
    "OY1",
    "OY2",
    "P",
    "R",
    "S",
    "SH",
    "T",
    "TH",
    "UH0",
    "UH1",
    "UH2",
    "UW",
    "UW0",
    "UW1",
    "UW2",
    "V",
    "W",
    "Y",
    "Z",
    "ZH",
]
_G2IDX = {g: i for i, g in enumerate(_GRAPHEMES)}
CHECKPOINT = Path(__file__).with_name("checkpoint20.npz")
MAX_PHONEMES = 20


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-x))


class NeuralG2P:
    """ARPAbet predictor: ``predict(word) -> ["Z", "AY0", "G", ...]``."""

    def __init__(self, checkpoint: Path = CHECKPOINT) -> None:
        v = np.load(checkpoint)
        self.enc_emb, self.dec_emb = v["enc_emb"], v["dec_emb"]
        self.enc = (v["enc_w_ih"], v["enc_w_hh"], v["enc_b_ih"], v["enc_b_hh"])
        self.dec = (v["dec_w_ih"], v["dec_w_hh"], v["dec_b_ih"], v["dec_b_hh"])
        self.fc_w, self.fc_b = v["fc_w"], v["fc_b"]

    @staticmethod
    def _cell(x: np.ndarray, h: np.ndarray, w_ih, w_hh, b_ih, b_hh) -> np.ndarray:
        rzn_ih = x @ w_ih.T + b_ih
        rzn_hh = h @ w_hh.T + b_hh
        k = rzn_ih.shape[-1] * 2 // 3
        r, z = np.split(_sigmoid(rzn_ih[:, :k] + rzn_hh[:, :k]), 2, -1)
        n = np.tanh(rzn_ih[:, k:] + r * rzn_hh[:, k:])
        return (1 - z) * n + z * h

    def predict(self, word: str) -> list[str]:
        chars = [c for c in word.lower() if c in _G2IDX] + ["</s>"]
        x = np.take(self.enc_emb, [_G2IDX[c] for c in chars], axis=0)  # (T, emb)
        h = np.zeros((1, self.enc[1].shape[-1]), np.float32)
        for t in range(x.shape[0]):
            h = self._cell(x[t : t + 1], h, *self.enc)
        dec = np.take(self.dec_emb, [2], axis=0)  # <s>
        out: list[str] = []
        for _ in range(MAX_PHONEMES):
            h = self._cell(dec, h, *self.dec)
            pred = int((h @ self.fc_w.T + self.fc_b).argmax())
            if pred == 3:  # </s>
                break
            out.append(_PHONEMES[pred])
            dec = np.take(self.dec_emb, [pred], axis=0)
        return [p for p in out if not p.startswith("<")]
