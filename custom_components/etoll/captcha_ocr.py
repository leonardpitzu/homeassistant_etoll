"""Local captcha OCR for the portal.etoll.ro vignette lookup.

The portal's captcha is five case-sensitive characters (``A-Z a-z 2-9`` — the
ambiguous ``0 1 O I l o s`` etc. are not used) drawn in a distorted, hand-drawn
font. It is read on the Home Assistant host with no extra dependencies: Pillow
and numpy both ship with Home Assistant. A small gallery of labelled glyphs
lives beside this module (``captcha_templates.npz``); each captcha is split into
its five glyphs and each glyph is classified against the gallery by nearest
neighbour. No OCR service, no API key, nothing leaves the machine.

Per-character accuracy is ~87%, so a single read of a five-glyph captcha
succeeds ~57% of the time. The client retries with a fresh captcha each time, so
a correct read is all but certain within a handful of attempts.
"""

from __future__ import annotations

import io
import logging
import threading
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

_LOGGER = logging.getLogger(__name__)

_TEMPLATES = Path(__file__).parent / "captcha_templates.npz"
_INK_THRESHOLD = 120
_NORM_W = 24
_NORM_H = 36
_BLUR = 1.2
_GLYPHS = 5

_lock = threading.Lock()
_gallery: tuple[np.ndarray, np.ndarray, str] | None = None


def _binarize(im: Image.Image) -> np.ndarray:
    g = np.asarray(im.convert("L"), dtype=np.uint8)
    return (g < _INK_THRESHOLD).astype(np.uint8)


def _ink_bbox(b: np.ndarray):
    cols = np.where(b.sum(axis=0) > 0)[0]
    rows = np.where(b.sum(axis=1) > 0)[0]
    if len(cols) == 0 or len(rows) == 0:
        return None
    return int(cols[0]), int(cols[-1]), int(rows[0]), int(rows[-1])


def _five_cells(b: np.ndarray):
    """Split the ink into five character cells.

    The sketchy font makes neighbours touch, so instead of relying on gaps we
    place four cuts near the 1/5..4/5 positions and snap each to the lowest-ink
    column nearby. The captcha always has exactly five glyphs.
    """
    bb = _ink_bbox(b)
    if bb is None:
        return [], (0, b.shape[0] - 1)
    x0, x1, y0, y1 = bb
    prof = b[y0 : y1 + 1, :].sum(axis=0).astype(float)
    width = (x1 - x0) / _GLYPHS
    cuts = []
    for k in range(1, _GLYPHS):
        centre = int(round(x0 + k * width))
        win = max(4, int(width * 0.35))
        lo, hi = max(x0 + 4, centre - win), min(x1 - 4, centre + win)
        cuts.append(lo + int(np.argmin(prof[lo : hi + 1])) if hi > lo else centre)
    xs = [x0] + cuts + [x1 + 1]
    return [(xs[i], xs[i + 1]) for i in range(_GLYPHS)], (y0, y1)


def _glyph_images(im: Image.Image) -> list[np.ndarray]:
    """Return five normalized greyscale glyph matrices for a captcha image.

    Each glyph keeps the captcha's shared vertical band so ascenders,
    descenders and cap-height survive — the cues that separate an upper-case
    letter from its lower-case twin.
    """
    b = _binarize(im)
    cells, (y0, y1) = _five_cells(b)
    band = b[y0 : y1 + 1, :]
    out = []
    for s, e in cells:
        sub = band[:, s:e]
        cols = np.where(sub.sum(axis=0) > 0)[0]
        if len(cols) == 0:
            out.append(np.zeros((_NORM_H, _NORM_W), dtype=np.uint8))
            continue
        crop = sub[:, cols[0] : cols[-1] + 1]
        img = Image.fromarray((crop * 255).astype(np.uint8)).resize((_NORM_W, _NORM_H), Image.BILINEAR)
        out.append(np.asarray(img, dtype=np.uint8))
    return out


def _feature(glyph_u8: np.ndarray) -> np.ndarray:
    """Blur and L2-normalize a greyscale glyph into a match vector."""
    img = Image.fromarray(glyph_u8).filter(ImageFilter.GaussianBlur(_BLUR))
    a = np.asarray(img, dtype=np.float32) / 255.0
    norm = float(np.linalg.norm(a))
    return (a / norm if norm > 1e-6 else a).ravel()


def _load_gallery() -> tuple[np.ndarray, np.ndarray, str]:
    """Load the glyph gallery and turn it into normalized match vectors once."""
    global _gallery
    if _gallery is None:
        with _lock:
            if _gallery is None:
                with np.load(_TEMPLATES, allow_pickle=False) as data:
                    glyphs = data["glyphs"]  # (N, H, W) uint8
                    labels = data["labels"]  # (N,) class indices
                    classes = str(data["classes"])
                feats = np.stack([_feature(g) for g in glyphs]).astype(np.float32)
                chars = np.array([classes[i] for i in labels])
                _gallery = (feats, chars, classes)
    return _gallery


def solve_captcha(image_data: bytes) -> str:
    """Return the five characters read from a captcha image.

    Runs entirely on-device. Blocking, so call it from an executor. Raises
    ValueError if the image cannot be read, which the client treats as a
    retriable miss.
    """
    try:
        image = Image.open(io.BytesIO(image_data))
        feats, chars, _ = _load_gallery()
        glyphs = _glyph_images(image)
        if len(glyphs) != _GLYPHS:
            raise ValueError(f"expected {_GLYPHS} glyphs, found {len(glyphs)}")
        text = "".join(chars[int(np.argmax(feats @ _feature(g)))] for g in glyphs)
    except ValueError:
        raise
    except Exception as err:  # noqa: BLE001 - Pillow/numpy raise a variety of errors
        raise ValueError(f"captcha OCR failed: {err}") from err

    if len(text) != _GLYPHS:
        raise ValueError(f"captcha OCR returned unusable text: {text!r}")
    return text
