from __future__ import annotations

import numpy as np
import pytest

from mga.semantic_palette import decode_rgb_label


def test_decode_rgb_label_supports_multiple_void_colors() -> None:
    value = np.asarray(
        [
            [[0, 0, 0], [255, 255, 255]],
            [[0, 255, 0], [0, 0, 255]],
        ],
        dtype=np.uint8,
    )
    palette = {
        0: ((0, 0, 0), (255, 255, 255)),
        1: ((0, 255, 0),),
        2: ((0, 0, 255),),
    }
    decoded = decode_rgb_label(value, palette)
    assert decoded.tolist() == [[0, 0], [1, 2]]


def test_decode_rgb_label_reports_unknown_colors() -> None:
    value = np.asarray([[[12, 34, 56]]], dtype=np.uint8)
    with pytest.raises(ValueError, match="unknown colors"):
        decode_rgb_label(value, {0: ((0, 0, 0),)})
