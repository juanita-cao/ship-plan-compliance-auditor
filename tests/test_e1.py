"""Tests for E1 · e1_extract_counts.

E1 now calls the LLM with a 2x upscaled image and parses the model's
final counts JSON directly — no instance-level output, no E2/E3.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from src.backend.e_nodes import e1_extract_counts
from src.backend.schemas import CANONICAL_CATEGORIES, E3CountResult

# ─── Shared test data ─────────────────────────────────────────────────────────

_ZERO_COUNTS = {cat: 0 for cat in CANONICAL_CATEGORIES}
_VALID_COUNTS = {**_ZERO_COUNTS, "extinguisher_CO2_5kg": 1, "extinguisher_dry_powder_6kg": 4}
_VALID_JSON = json.dumps(_VALID_COUNTS)
_ZERO_JSON = json.dumps(_ZERO_COUNTS)
_MISSING_CATEGORY_JSON = json.dumps({"extinguisher_CO2_5kg": 1})
_WRONG_TYPE_JSON = json.dumps({**_ZERO_COUNTS, "extinguisher_CO2_5kg": "not_a_number"})


@pytest.fixture()
def image_file(tmp_path: Path) -> Path:
    """Valid 4×4 PNG — PIL opens and upscales it without error."""
    p = tmp_path / "test.png"
    img = Image.new("RGB", (4, 4), color=(128, 128, 128))
    img.save(str(p), format="PNG")
    return p


def _mock_cloud_client(json_content: str) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.output_text = json_content
    client = MagicMock()
    client.responses.create.return_value = mock_resp
    return client


def _mock_local_resp(json_content: str) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"response": json_content}
    resp.raise_for_status.return_value = None
    return resp


# ─── E1-S01 ───────────────────────────────────────────────────────────────────


def test_e1_s01_cloud_happy_path(image_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_VISION_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    client = _mock_cloud_client(_VALID_JSON)

    with patch("openai.OpenAI", return_value=client):
        result = e1_extract_counts(image_file, "prompt", "cloud", 0)

    assert isinstance(result, E3CountResult)
    assert result.total_by_category["extinguisher_CO2_5kg"] == 1
    assert result.total_by_category["extinguisher_dry_powder_6kg"] == 4


# ─── E1-S02 ───────────────────────────────────────────────────────────────────


def test_e1_s02_local_happy_path(image_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_VISION_MODEL", "llava")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")

    with patch("httpx.post", return_value=_mock_local_resp(_VALID_JSON)):
        result = e1_extract_counts(image_file, "prompt", "local", 1)

    assert isinstance(result, E3CountResult)
    assert result.run_id == 1


# ─── E1-S03 ───────────────────────────────────────────────────────────────────


def test_e1_s03_run_id_recorded(image_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_VISION_MODEL", "gpt-4o")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    with patch("openai.OpenAI", return_value=_mock_cloud_client(_VALID_JSON)):
        result = e1_extract_counts(image_file, "prompt", "cloud", 2)

    assert result.run_id == 2


# ─── E1-S05 ───────────────────────────────────────────────────────────────────


def test_e1_s05_all_zero_counts_ok(image_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_VISION_MODEL", "gpt-4o")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    with patch("openai.OpenAI", return_value=_mock_cloud_client(_ZERO_JSON)):
        result = e1_extract_counts(image_file, "prompt", "cloud", 0)

    assert all(v == 0 for v in result.total_by_category.values())


# ─── E1-S06 ───────────────────────────────────────────────────────────────────


def test_e1_s06_missing_openai_model_env_raises(
    image_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OPENAI_VISION_MODEL", raising=False)

    with patch("openai.OpenAI") as mock_cls:
        with pytest.raises((KeyError, RuntimeError)):
            e1_extract_counts(image_file, "prompt", "cloud", 0)
    mock_cls.assert_not_called()


# ─── E1-S07 ───────────────────────────────────────────────────────────────────


def test_e1_s07_missing_ollama_model_env_raises(
    image_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("OLLAMA_VISION_MODEL", raising=False)

    with patch("httpx.post") as mock_post:
        with pytest.raises((KeyError, RuntimeError)):
            e1_extract_counts(image_file, "prompt", "local", 0)
    mock_post.assert_not_called()


# ─── E1-S08 ───────────────────────────────────────────────────────────────────


def test_e1_s08_json_parse_fails_all_retries(
    image_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_VISION_MODEL", "gpt-4o")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    client = _mock_cloud_client("NOT VALID JSON {{{")

    with patch("openai.OpenAI", return_value=client), patch("time.sleep"):
        with pytest.raises(RuntimeError):
            e1_extract_counts(image_file, "prompt", "cloud", 0)

    assert client.responses.create.call_count == 3


# ─── E1-S09 ───────────────────────────────────────────────────────────────────


def test_e1_s09_missing_category_key_all_retries(
    image_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_VISION_MODEL", "gpt-4o")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    client = _mock_cloud_client(_MISSING_CATEGORY_JSON)

    with patch("openai.OpenAI", return_value=client), patch("time.sleep"):
        with pytest.raises(RuntimeError):
            e1_extract_counts(image_file, "prompt", "cloud", 0)

    assert client.responses.create.call_count == 3


# ─── E1-S10 ───────────────────────────────────────────────────────────────────


def test_e1_s10_wrong_value_type_all_retries(
    image_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_VISION_MODEL", "gpt-4o")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    client = _mock_cloud_client(_WRONG_TYPE_JSON)

    with patch("openai.OpenAI", return_value=client), patch("time.sleep"):
        with pytest.raises(RuntimeError):
            e1_extract_counts(image_file, "prompt", "cloud", 0)

    assert client.responses.create.call_count == 3


# ─── E1-S11 ───────────────────────────────────────────────────────────────────


def test_e1_s11_api_error_retry_succeeds(image_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_VISION_MODEL", "gpt-4o")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    mock_ok = MagicMock()
    mock_ok.output_text = _VALID_JSON
    client = MagicMock()
    client.responses.create.side_effect = [Exception("network error"), mock_ok]

    with patch("openai.OpenAI", return_value=client), patch("time.sleep"):
        result = e1_extract_counts(image_file, "prompt", "cloud", 0)

    assert isinstance(result, E3CountResult)
    assert client.responses.create.call_count == 2


# ─── E1-S12 ───────────────────────────────────────────────────────────────────


def test_e1_s12_api_error_all_retries(image_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_VISION_MODEL", "gpt-4o")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    client = MagicMock()
    client.responses.create.side_effect = Exception("network error")

    with patch("openai.OpenAI", return_value=client), patch("time.sleep"):
        with pytest.raises(RuntimeError):
            e1_extract_counts(image_file, "prompt", "cloud", 0)

    assert client.responses.create.call_count == 3


# ─── E1-S13 ───────────────────────────────────────────────────────────────────


def test_e1_s13_image_sent_as_base64_cloud(
    image_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_VISION_MODEL", "gpt-4o")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    client = _mock_cloud_client(_VALID_JSON)

    with patch("openai.OpenAI", return_value=client):
        e1_extract_counts(image_file, "test-prompt", "cloud", 0)

    kwargs = client.responses.create.call_args.kwargs
    input_msgs = kwargs["input"]
    image_parts = [
        part
        for msg in input_msgs
        for part in (msg.get("content") or [])
        if isinstance(part, dict) and part.get("type") == "input_image"
    ]
    assert len(image_parts) == 1
    url = image_parts[0]["image_url"]
    assert url.startswith("data:image/png;base64,")
    assert len(url) > len("data:image/png;base64,")  # some content present


def test_e1_s13_image_sent_as_base64_local(
    image_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OLLAMA_VISION_MODEL", "llava")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")

    with patch("httpx.post", return_value=_mock_local_resp(_VALID_JSON)) as mock_post:
        e1_extract_counts(image_file, "test-prompt", "local", 0)

    request_json = mock_post.call_args.kwargs.get("json") or {}
    images = request_json.get("images", [])
    assert len(images) == 1
    assert len(images[0]) > 0  # non-empty base64 string


# ─── E1-S14 ───────────────────────────────────────────────────────────────────


def test_e1_s14_invalid_backend_raises(image_file: Path) -> None:
    with pytest.raises(ValueError):
        e1_extract_counts(image_file, "prompt", "invalid", 0)  # type: ignore[arg-type]


# ─── E1-S15 ───────────────────────────────────────────────────────────────────


def test_e1_s15_missing_image_file_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_VISION_MODEL", "gpt-4o")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    missing = tmp_path / "does_not_exist.png"

    with patch("openai.OpenAI") as mock_cls:
        with pytest.raises(FileNotFoundError):
            e1_extract_counts(missing, "prompt", "cloud", 0)
    mock_cls.assert_not_called()


# ─── E1-S16 ───────────────────────────────────────────────────────────────────


def test_e1_s16_image_path_is_directory_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_VISION_MODEL", "gpt-4o")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    with patch("openai.OpenAI") as mock_cls:
        with pytest.raises((ValueError, IsADirectoryError)):
            e1_extract_counts(tmp_path, "prompt", "cloud", 0)
    mock_cls.assert_not_called()


# ─── E1-S17 ───────────────────────────────────────────────────────────────────


def test_e1_s17_ollama_base_url_default(image_file: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_VISION_MODEL", "llava")
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)

    with patch("httpx.post", return_value=_mock_local_resp(_VALID_JSON)) as mock_post:
        result = e1_extract_counts(image_file, "prompt", "local", 0)

    assert isinstance(result, E3CountResult)
    url = mock_post.call_args.args[0] if mock_post.call_args.args else ""
    assert "localhost:11434" in url


# ─── E1-S18 ───────────────────────────────────────────────────────────────────


def test_e1_s18_cloud_output_text_none_all_retries(
    image_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_VISION_MODEL", "gpt-4o")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    mock_resp = MagicMock()
    mock_resp.output_text = None
    client = MagicMock()
    client.responses.create.return_value = mock_resp

    with patch("openai.OpenAI", return_value=client), patch("time.sleep"):
        with pytest.raises(RuntimeError):
            e1_extract_counts(image_file, "prompt", "cloud", 0)

    assert client.responses.create.call_count == 3


# ─── E1-S19 ───────────────────────────────────────────────────────────────────


def test_e1_s19_local_response_key_missing_all_retries(
    image_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OLLAMA_VISION_MODEL", "llava")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    resp = MagicMock()
    resp.json.return_value = {"model": "llava", "done": True}
    resp.raise_for_status.return_value = None

    with patch("httpx.post", return_value=resp) as mock_post, patch("time.sleep"):
        with pytest.raises(RuntimeError):
            e1_extract_counts(image_file, "prompt", "local", 0)

    assert mock_post.call_count == 3


# ─── E1-S20 ───────────────────────────────────────────────────────────────────


def test_e1_s20_httpx_timeout_all_retries(
    image_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import httpx

    monkeypatch.setenv("OLLAMA_VISION_MODEL", "llava")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")

    with (
        patch("httpx.post", side_effect=httpx.TimeoutException("timeout")) as mock_post,
        patch("time.sleep"),
    ):
        with pytest.raises(RuntimeError):
            e1_extract_counts(image_file, "prompt", "local", 0)

    assert mock_post.call_count == 3
