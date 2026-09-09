from __future__ import annotations

import pytest

from mga.grounding.segearth_ov3 import SegEarthOV3Grounder


def test_missing_vendor_checkout_fails_before_heavy_imports(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="SegEarth-OV3 checkout"):
        SegEarthOV3Grounder(vendor_root=str(tmp_path / "missing"))


def test_scalar_accepts_tensor_like_value() -> None:
    class TensorLike:
        def detach(self):
            return self

        def float(self):
            return self

        def max(self):
            return self

        def cpu(self):
            return self

        def item(self):
            return 0.75

    assert SegEarthOV3Grounder._scalar(TensorLike(), default=0.0) == pytest.approx(0.75)
