import pytest
from pydantic import ValidationError

from scenechat.models import Detection


def test_detection_uses_normalised_coordinates():
    result = Detection(label="laptop", confidence=0.7, x=0.2, y=0.1, width=0.3, height=0.4)
    assert result.x + result.width <= 1


def test_detection_rejects_box_outside_frame():
    with pytest.raises(ValidationError, match="beyond frame width"):
        Detection(label="laptop", confidence=0.7, x=0.9, y=0.1, width=0.3, height=0.4)

