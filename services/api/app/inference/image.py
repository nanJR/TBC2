"""Prepare a chest X-ray for the model, and draw the heatmap on top of it.

Uses only Pillow and NumPy, so the server doesn't need PyTorch. The steps must match
ml/cxr/extract_features.py exactly; ml/export/export_cxr.py checks that they do.
"""

import base64
import io

import numpy as np
from PIL import Image

SIZE = 224
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

# X-rays are grey or lightly tinted. The most tinted of 2,500 JU-TB images scored 34, so
# anything above this limit is a colour picture. This only catches strongly coloured
# uploads. It can't confirm that a grey image really is a chest X-ray.
MAX_COLOUR_DIFFERENCE = 45.0


def colour_difference(image: Image.Image) -> float:
    """Average gap between colour channels, 0-255. Close to 0 for a grey image."""
    small = np.asarray(image.convert("RGB").resize((64, 64)), dtype=np.float32)
    return float(np.abs(small - small.mean(axis=2, keepdims=True)).mean())


def preprocess(image: Image.Image) -> np.ndarray:
    """Turn an image into the 1 x 3 x 224 x 224 array the network expects."""
    # The network expects 3 colour channels, even for grey X-rays.
    image = image.convert("RGB")
    width, height = image.size
    # Shrink the shorter side to 224, keeping the shape, then cut out the middle square.
    if width <= height:
        new_size = (SIZE, int(SIZE * height / width))
    else:
        new_size = (int(SIZE * width / height), SIZE)
    image = image.resize(new_size, Image.Resampling.BICUBIC)
    left = int(round((new_size[0] - SIZE) / 2.0))
    top = int(round((new_size[1] - SIZE) / 2.0))
    image = image.crop((left, top, left + SIZE, top + SIZE))
    # Scale to 0-1, then normalise the way the network was trained.
    pixels = np.asarray(image, dtype=np.float32) / 255.0
    pixels = (pixels - MEAN) / STD
    return pixels.transpose(2, 0, 1)[np.newaxis].astype(np.float32)


def heatmap_png(image: Image.Image, cam: np.ndarray) -> str:
    """Overlay where the model looked on the X-ray. Returns a base64 PNG.

    Only positive values are shown: those are the areas that pushed the score towards TB.
    """
    base = image.convert("RGB")
    base.thumbnail((512, 512))
    positive = np.clip(cam, 0, None)
    peak = positive.max()
    if peak > 0:
        positive = positive / peak
    # Stretch the small 7 x 7 map up to the size of the picture, smoothly.
    mask = Image.fromarray((positive * 255).astype(np.uint8)).resize(base.size, Image.BICUBIC)
    red = Image.new("RGB", base.size, (220, 38, 38))
    # At most 60% red, so the X-ray can still be seen underneath.
    blended = Image.composite(red, base, mask.point(lambda v: int(v * 0.6)))
    buffer = io.BytesIO()
    blended.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")
