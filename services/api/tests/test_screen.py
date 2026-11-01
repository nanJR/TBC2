"""The rule that matters most: a model can add a referral but can never cancel one."""

import io
import tempfile

from fastapi.testclient import TestClient
from PIL import Image

from app.inference.referral import decide, is_presumptive, rescale
from app.main import app

client = TestClient(app)


def post(data=None, files=None):
    return client.post("/screen", data={"age": 40, **(data or {})}, files=files)


def test_symptoms_go_to_naat_even_when_no_model_flags(no_models):
    body = post({"symptoms": ["fever"]}).json()
    assert body["next_step"] == "naat"


def test_short_cough_only_counts_for_vulnerable_people():
    assert not is_presumptive({"cough_under_2_weeks"}, set())
    assert is_presumptive({"cough_under_2_weeks"}, {"diabetes"})
    assert is_presumptive({"cough_over_2_weeks"}, set())


def test_vulnerable_person_without_symptoms_is_offered_an_xray(no_models):
    body = post({"vulnerabilities": ["household_contact"]}).json()
    assert body["next_step"] == "offer_xray"
    assert any("doesn't rule out TB" in note for note in body["notes"])


def test_age_over_60_counts_as_vulnerable(no_models):
    body = client.post("/screen", data={"age": 65}).json()
    assert body["next_step"] == "offer_xray"


def test_no_risk_recorded_is_routine_care_but_never_says_no_tb(no_models):
    body = post().json()
    assert body["next_step"] == "routine_care"
    assert any("doesn't rule out TB" in note for note in body["notes"])


def test_flagged_xray_goes_to_naat():
    assert decide(set(), set(), xray_flagged=True, xray_scored=True)[0] == "naat"


def test_experimental_cough_never_changes_the_next_step(tiny_models, cough_wav):
    body = post(files={"cough": ("c.wav", cough_wav, "audio/wav")}).json()
    assert body["cough"]["counts_towards_referral"] is False
    assert body["next_step"] == "routine_care"
    assert body["risk_score"] is None


def test_real_xray_score_comes_with_heatmap(tiny_models, xray_png):
    response = post(files={"xray": ("x.png", xray_png, "image/png")})
    assert response.status_code == 200
    body = response.json()
    assert body["is_mock"] is False
    assert body["xray"]["flagged"] is True
    assert body["next_step"] == "naat"
    assert body["xray_heatmap_png"]
    assert 0 <= body["risk_score"] <= 1


def test_phone_photo_gets_a_warning(tiny_models, xray_png):
    body = post({"image_source": "phone_photo"}, {"xray": ("x.png", xray_png, "image/png")}).json()
    assert any("phone photos" in note for note in body["notes"])


def test_models_are_not_used_under_15(tiny_models, xray_png):
    response = client.post(
        "/screen", data={"age": 12}, files={"xray": ("x.png", xray_png, "image/png")}
    )
    body = response.json()
    assert body["xray"] is None
    assert any("aged 15 and over" in note for note in body["notes"])


def test_colour_photo_is_refused(tiny_models):
    buffer = io.BytesIO()
    Image.new("RGB", (100, 100), (255, 0, 0)).save(buffer, format="PNG")
    response = post(files={"xray": ("selfie.png", buffer.getvalue(), "image/png")})
    assert response.status_code == 422


def test_files_that_are_not_what_they_claim_are_refused(tiny_models):
    bad = b"this is not a real file"
    assert post(files={"xray": ("x.png", bad, "image/png")}).status_code == 422
    assert post(files={"cough": ("c.wav", bad, "audio/wav")}).status_code == 422


def test_oversized_upload_is_refused(tiny_models):
    too_big = b"0" * (21 * 1024 * 1024)
    response = post(files={"xray": ("x.png", too_big, "image/png")})
    assert response.status_code == 413


def test_missing_models_leave_scores_empty(no_models, cough_wav):
    body = post(files={"cough": ("c.wav", cough_wav, "audio/wav")}).json()
    assert body["cough"] is None


def test_uploads_are_never_written_to_disk(tiny_models, monkeypatch):
    """Python writes a spooled upload to a temporary file only by "rolling over"."""

    def fail(self):
        raise AssertionError("An upload was written to disk")

    monkeypatch.setattr(tempfile.SpooledTemporaryFile, "rollover", fail)
    buffer = io.BytesIO()
    noise = Image.effect_noise((2000, 2000), 80)
    noise.save(buffer, format="PNG")
    assert buffer.tell() > 2 * 1024 * 1024
    response = post(files={"xray": ("x.png", buffer.getvalue(), "image/png")})
    assert response.status_code == 200


def test_rescale_puts_every_threshold_at_one_half():
    assert rescale(0.75, 0.75) == 0.5
    assert rescale(0.41, 0.41) == 0.5
    assert rescale(1.0, 0.75) == 1.0
    assert rescale(0.0, 0.75) == 0.0
