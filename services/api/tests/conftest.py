"""Tiny fake models, so tests can run the real code path without real weights.

Their scores mean nothing. They only prove the wiring works.
"""

import json

import numpy as np
import onnx
import pytest
from onnx import TensorProto, helper

from app.config import settings
from app.inference.registry import get_model


def _save_xray_model(folder):
    # Score: average of all pixels, squashed to 0-1. Heatmap: average over 32 x 32 patches.
    graph = helper.make_graph(
        [
            helper.make_node("ReduceMean", ["image"], ["mean"], axes=[1, 2, 3], keepdims=0),
            helper.make_node("Sigmoid", ["mean"], ["probability"]),
            helper.make_node(
                "AveragePool", ["image"], ["patches"], kernel_shape=[32, 32], strides=[32, 32]
            ),
            helper.make_node("ReduceMean", ["patches"], ["cam"], axes=[1], keepdims=0),
        ],
        "tiny_xray",
        [helper.make_tensor_value_info("image", TensorProto.FLOAT, [None, 3, 224, 224])],
        [
            helper.make_tensor_value_info("probability", TensorProto.FLOAT, [None]),
            helper.make_tensor_value_info("cam", TensorProto.FLOAT, [None, 7, 7]),
        ],
    )
    _write(folder, graph, threshold=0.0, counts=True, status="test")


def _save_cough_model(folder):
    graph = helper.make_graph(
        [
            helper.make_node("ReduceMean", ["features"], ["mean"], axes=[1], keepdims=0),
            helper.make_node("Sigmoid", ["mean"], ["probability"]),
        ],
        "tiny_cough",
        [helper.make_tensor_value_info("features", TensorProto.FLOAT, [None, 168])],
        [helper.make_tensor_value_info("probability", TensorProto.FLOAT, [None])],
    )
    _write(folder, graph, threshold=0.0, counts=False, status="experimental")


def _write(folder, graph, threshold, counts, status):
    folder.mkdir(parents=True)
    model = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    model.ir_version = 8
    onnx.save(model, folder / "model.onnx")
    meta = {
        "version": "test",
        "threshold": threshold,
        "counts_towards_referral": counts,
        "status": status,
        "note": "Test model.",
    }
    (folder / "model.json").write_text(json.dumps(meta))


@pytest.fixture
def tiny_models(tmp_path, monkeypatch):
    """Point the server at the fake models for one test."""
    _save_xray_model(tmp_path / "xray")
    _save_cough_model(tmp_path / "cough")
    monkeypatch.setattr(settings, "model_dir", str(tmp_path))
    get_model.cache_clear()
    yield
    get_model.cache_clear()


@pytest.fixture
def no_models(tmp_path, monkeypatch):
    """Point the server at an empty folder, as on a machine without weights."""
    monkeypatch.setattr(settings, "model_dir", str(tmp_path))
    get_model.cache_clear()
    yield
    get_model.cache_clear()


@pytest.fixture
def cough_wav():
    """Half a second of quiet, then a loud burst: a stand-in for a cough."""
    import io

    import soundfile

    rng = np.random.default_rng(0)
    sound = np.concatenate([np.zeros(8000), rng.uniform(-1, 1, 16000)]).astype(np.float32)
    buffer = io.BytesIO()
    soundfile.write(buffer, sound, 16000, format="WAV")
    return buffer.getvalue()


@pytest.fixture
def xray_png():
    """A plain grey picture, wider than it is tall."""
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("L", (300, 200), 128).save(buffer, format="PNG")
    return buffer.getvalue()
