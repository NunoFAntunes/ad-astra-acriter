"""
Builds the "neck" hero variant (clip_01: sand funnelling through the waist).

Same pipeline as hourglass.py (static camera -> one silhouette mask, flat-field
grade, crossfaded loop, CSS mask), but the outline is different: the glass
runs off the top, both sides and the bottom of the frame, so
  - the silhouette is found per row (the backdrop outside the glass is flat,
    so the first/last strong edge in each row is the outer wall), and
  - the mask dissolves into all four frame edges instead of just the top.

Usage:
  pip install numpy opencv-python-headless
  python tools/hourglass_neck.py
"""

from pathlib import Path

import cv2
import numpy as np

from hourglass import (
    LOOP_XFADE, OUT_H, OUT_W, PAGE_BGR,
    background_plate, encode, highpass, read_frames,
)

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "videos" / "clip_01.mp4"
OUT = ROOT / "src" / "assets"
NAME = "hourglass-neck"

EDGE_T = 2.0      # |high-pass| above this counts as glass (backdrop noise is ~0.3)
FADE_TOP = 360    # source px over which the sand mass dissolves into the top edge
FADE_BOTTOM = 170
FADE_SIDE = 160
# Sand seen through the thick walls is paler (sat ~.2-.35) than in the bulb clip;
# the clear glass and backdrop stay under ~.17.
SAND_SAT = (0.18, 0.12)  # threshold, ramp width


def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def smooth_1d(v, median_k=31, sigma=10):
    pad = median_k // 2
    p = np.pad(v, pad, mode="edge")
    v = np.median(np.lib.stride_tricks.sliding_window_view(p, median_k), axis=1)
    k = cv2.getGaussianKernel(6 * sigma + 1, sigma).ravel()
    p = np.pad(v, 3 * sigma, mode="edge")
    return np.convolve(p, k, "valid")


def sand_weight(frame):
    sat = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)[..., 1].astype(np.float32) / 255
    lo, span = SAND_SAT
    s = np.clip((sat - lo) / span, 0, 1)
    return cv2.GaussianBlur(s, (0, 0), 6 * frame.shape[1] / 1920)


def grade(frame, plate):
    """As hourglass.grade, with this clip's sand threshold."""
    f = frame.astype(np.float32)
    glass = PAGE_BGR * (f / np.maximum(plate, 1))
    sand = np.clip(f * 1.22 + 10, 0, 255)
    s = sand_weight(frame)[..., None]
    return np.clip(glass * (1 - s) + sand * s, 0, 255).astype(np.uint8)


def outline(median):
    """Left/right outer wall for every row, in source px (may run past the frame)."""
    e = cv2.GaussianBlur(np.abs(highpass(median, 2)), (0, 0), 2)
    h, w = e.shape
    hot = e > EDGE_T
    left = np.array([np.argmax(r) if r.any() else w // 2 for r in hot], np.float32)
    right = np.array([w - 1 - np.argmax(r[::-1]) if r.any() else w // 2 for r in hot], np.float32)
    # rows where the wall is already off-frame find the sand itself at x=0 / x=w-1
    left, right = smooth_1d(left), smooth_1d(right)
    left[left < 4] = -40
    right[right > w - 5] = w + 40
    return left, right


def build_mask(left, right, shape):
    h, w = shape
    xs = np.arange(w, dtype=np.float32)[None, :]
    m = ((xs >= left[:, None] - 4) & (xs <= right[:, None] + 4)).astype(np.float32)
    m = cv2.GaussianBlur(m, (0, 0), 5)
    y = np.arange(h, dtype=np.float32)[:, None]
    x = xs
    fade = (smoothstep(y / FADE_TOP) * smoothstep((h - 1 - y) / FADE_BOTTOM)
            * smoothstep(x / FADE_SIDE) * smoothstep((w - 1 - x) / FADE_SIDE))
    return m * fade


def resize(img):
    return cv2.resize(img, (OUT_W, OUT_H), interpolation=cv2.INTER_AREA)


def main():
    frames = read_frames(SRC)
    median = np.median(np.stack(frames), axis=0).astype(np.uint8)

    left, right = outline(median)
    mask = build_mask(left, right, median.shape[:2])
    plate = background_plate(median)
    graded = [resize(grade(f, plate)) for f in frames]

    n, k = len(graded), LOOP_XFADE
    loop = []
    for i in range(n - k):
        if i < k:
            a = smoothstep((i + 0.5) / k)
            loop.append(cv2.addWeighted(graded[n - k + i], 1 - a, graded[i], a, 0))
        else:
            loop.append(graded[i])

    fps = "24000/1001"
    encode(loop, fps, OUT / f"{NAME}.webm",
           ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "34", "-row-mt", "1", "-pix_fmt", "yuv420p"])
    encode(loop, fps, OUT / f"{NAME}.mp4",
           ["-c:v", "libx264", "-crf", "22", "-preset", "slow", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-tag:v", "avc1"])

    m = cv2.resize((mask * 255).astype(np.uint8), (OUT_W // 2, OUT_H // 2), interpolation=cv2.INTER_AREA)
    rgba = np.zeros((*m.shape, 4), np.uint8)
    rgba[..., 3] = m
    cv2.imwrite(str(OUT / f"{NAME}-mask.png"), rgba, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    cv2.imwrite(str(OUT / f"{NAME}-poster.jpg"), loop[0], [cv2.IMWRITE_JPEG_QUALITY, 86])

    mm = cv2.resize(m, (OUT_W, OUT_H)).astype(np.float32)[..., None] / 255
    preview = loop[0] * mm + PAGE_BGR * (1 - mm)
    cv2.imwrite(str(ROOT / "tools" / f"{NAME}-preview.png"), preview.astype(np.uint8))

    # outline check on the raw median
    dbg = median.copy()
    ys = np.arange(len(left))
    for xs in (left, right):
        pts = np.stack([xs, ys], 1).astype(np.int32)
        cv2.polylines(dbg, [pts], False, (0, 255, 0), 2)
    cv2.imwrite(str(ROOT / "tools" / f"{NAME}-outline.jpg"), cv2.resize(dbg, (1280, 720)))
    print(f"{len(loop)} frames -> {OUT}")


if __name__ == "__main__":
    main()
