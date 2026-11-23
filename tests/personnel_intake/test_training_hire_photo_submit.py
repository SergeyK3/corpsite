from io import BytesIO
from unittest.mock import Mock

import pytest
from PIL import Image

from app.personnel_intake.application.intake_service import _validate_training_hire_photo
from app.personnel_intake.domain.errors import PersonnelIntakeValidationError


def _photo() -> bytes:
    output = BytesIO()
    Image.new("RGB", (600, 800), "white").save(output, format="JPEG")
    return output.getvalue()


def test_training_hire_submission_rejects_missing_photo(monkeypatch):
    monkeypatch.setenv("TRAINING_MODE", "1")
    monkeypatch.setenv("HIRE_PATH_REHEARSAL", "1")
    conn = Mock()
    conn.execute.return_value.scalar_one_or_none.return_value = 1

    with pytest.raises(PersonnelIntakeValidationError, match="фотографию 3×4"):
        _validate_training_hire_photo(conn, 545, {"personal": {}})


def test_training_hire_submission_accepts_saved_valid_photo(monkeypatch):
    monkeypatch.setenv("TRAINING_MODE", "1")
    monkeypatch.setenv("HIRE_PATH_REHEARSAL", "1")
    conn = Mock()
    conn.execute.return_value.scalar_one_or_none.return_value = 1
    monkeypatch.setattr(
        "app.personnel_intake.infrastructure.photo_storage.read_intake_photo",
        lambda application_id, photo_id: _photo(),
    )

    _validate_training_hire_photo(conn, 545, {"personal": {"photo_file_id": "a" * 32}})


def test_other_intake_is_unaffected(monkeypatch):
    monkeypatch.delenv("HIRE_PATH_REHEARSAL", raising=False)
    conn = Mock()
    _validate_training_hire_photo(conn, 545, {"personal": {}})
    conn.execute.assert_not_called()
