"""Tests for the local captcha OCR.

The fixtures are real captcha images whose glyphs are in the bundled template
gallery, so a correct read is deterministic: it exercises the whole pipeline
(template load, segmentation, matching) without depending on OCR accuracy.
"""

from pathlib import Path

import pytest

from custom_components.etoll.captcha_ocr import solve_captcha

FIXTURES = Path(__file__).parent / "fixtures"
CLASSES = set("23456789ABDEFGHJKMNPQRTYabdefghjkmnpqrty")


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("captcha_en8JT.png", "en8JT"),
        ("captcha_F4qDe.png", "F4qDe"),
        ("captcha_d8TRG.png", "d8TRG"),
    ],
)
def test_known_captchas_are_read(filename: str, expected: str):
    text = solve_captcha((FIXTURES / filename).read_bytes())
    assert text == expected


def test_output_is_five_characters_in_the_charset():
    text = solve_captcha((FIXTURES / "captcha_en8JT.png").read_bytes())
    assert len(text) == 5
    assert set(text) <= CLASSES


def test_unreadable_data_raises_value_error():
    with pytest.raises(ValueError):
        solve_captcha(b"not an image")
