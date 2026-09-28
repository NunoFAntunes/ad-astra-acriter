"""
Builds the hero hourglass assets from the source clip.

The camera and hourglass are static, so a single silhouette mask covers the
whole clip. Steps:
  1. median frame -> fit the glass outline (ray search on top, superellipse on the base)
  2. flat-field grade: divide out a smooth background plate so the backdrop
     seen through the glass becomes the page colour, keeping glass highlights
  3. crossfade the tail into the head for a seamless loop
  4. encode WebM (VP9) + MP4 (H.264), write the alpha mask PNG and a poster

The mask is applied in CSS (mask-image), so the videos themselves have no alpha.

Usage:
  pip install numpy opencv-python-headless
  python tools/hourglass.py
"""

import subprocess
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "videos" / "source.mp4"
OUT = ROOT / "src" / "assets"

PAGE_BGR = np.array([245, 247, 247], np.float32)  # #F7F7F5
CROP = (72, 0, 1776, 999)  # x, y, w, h in source pixels (16:9)
OUT_W, OUT_H = 1280, 720
LOOP_XFADE = 12  # frames
TOP_FADE = 300  # source px over which the glass dissolves into the top edge

# Rough outline (source px), used to guide the edge search.
ROUGH = np.array([
    (490, 0), (340, 100), (180, 240), (110, 380), (90, 500), (120, 640), (240, 780),
    (320, 850), (450, 924), (600, 956), (750, 974), (900, 976), (1050, 972),
    (1200, 962), (1350, 944), (1500, 904), (1600, 850), (1740, 720), (1800, 580),
    (1804, 480), (1760, 340), (1660, 230), (1520, 100), (1400, 0),
], np.float32)


def read_frames(path):
    cap = cv2.VideoCapture(str(path))
    frames = []
    while True:
        ok, f = cap.read()
        if not ok:
            break
        frames.append(f)
    return frames


def highpass(img, blur=2):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    hp = g - cv2.GaussianBlur(g, (0, 0), 25)
    return cv2.GaussianBlur(hp, (0, 0), blur)


def fit_upper(hp, centre=(950.0, 520.0)):
    """Snap rays from the centre to the strongest glass edge near the rough outline."""
    c = np.array(centre, np.float32)
    rv = ROUGH - c
    ang = np.arctan2(rv[:, 1], rv[:, 0])
    rad = np.hypot(rv[:, 0], rv[:, 1])
    order = np.argsort(ang)
    angles = np.linspace(-np.pi, np.pi, 720, endpoint=False)
    r0s = np.interp(angles, ang[order], rad[order], period=2 * np.pi)

    radii = []
    for a, r0 in zip(angles, r0s):
        rs = np.arange(r0 - 60, r0 + 60, 1.0)
        xs, ys = c[0] + rs * np.cos(a), c[1] + rs * np.sin(a)
        ok = (xs >= 0) & (xs < hp.shape[1]) & (ys >= 0) & (ys < hp.shape[0])
        if not ok.any():
            radii.append(r0)
            continue
        v = hp[ys[ok].astype(int), xs[ok].astype(int)]
        radii.append(rs[ok][np.argmax(v)])

    r = np.array(radii, np.float32)
    k = 15
    padded = np.concatenate([r[-k:], r, r[:k]])
    r = np.median(np.lib.stride_tricks.sliding_window_view(padded, 2 * k + 1), axis=1)
    padded = np.concatenate([r[-20:], r, r[:20]])
    r = np.convolve(padded, cv2.getGaussianKernel(41, 8).ravel(), "same")[20:-20]
    pts = np.stack([c[0] + r * np.cos(angles), c[1] + r * np.sin(angles)], 1)
    return pts


def fit_lower(hp, base_y=972):
    """Superellipse through the widest points and the glass foot."""
    t = np.linspace(0, np.pi, 400)

    def curve(cx, cy, a, b, n):
        ct, st = np.cos(t), np.sin(t)
        return cx + a * np.sign(ct) * np.abs(ct) ** (2 / n), cy + b * np.abs(st) ** (2 / n)

    best = None
    for cx in range(930, 971, 10):
        for cy in range(440, 541, 20):
            for a in range(840, 891, 10):
                for n in (1.8, 2.0, 2.2, 2.4, 2.6, 2.8, 3.0):
                    x, y = curve(cx, cy, a, base_y - cy, n)
                    ok = (x >= 0) & (x < hp.shape[1]) & (y >= 0) & (y < hp.shape[0])
                    s = hp[y[ok].astype(int), x[ok].astype(int)].mean()
                    if best is None or s > best[0]:
                        best = (s, (cx, cy, a, base_y - cy, n))
    cx, cy, a, b, n = best[1]
    x, y = curve(cx, cy, a, b, n)
    return np.stack([x, y], 1), cy


def outline(median):
    hp = highpass(median)
    upper = fit_upper(hp)
    lower, cy = fit_lower(highpass(median, 3))
    upper = upper[upper[:, 1] < cy]
    upper = upper[np.argsort(upper[:, 0])]
    pts = np.concatenate([lower, upper])

    # resample by arc length, then smooth the closed curve (keeps the top edge exact)
    d = np.r_[0, np.cumsum(np.hypot(*np.diff(pts, axis=0).T))]
    u = np.linspace(0, d[-1], 1200, endpoint=False)
    pts = np.stack([np.interp(u, d, pts[:, 0]), np.interp(u, d, pts[:, 1])], 1)
    padded = np.concatenate([pts[-30:], pts, pts[:30]])
    k = cv2.getGaussianKernel(61, 10).ravel()
    smooth = np.stack([np.convolve(padded[:, i], k, "same") for i in (0, 1)], 1)[30:-30]
    top = pts[:, 1] < 5
    smooth[top] = pts[top]
    smooth[top, 1] = -40  # push past the frame so the fill reaches the edge
    return smooth


def build_mask(pts, shape):
    h, w = shape
    m = np.zeros((h, w), np.uint8)
    cv2.fillPoly(m, [pts.astype(np.int32)], 255)
    m = cv2.dilate(m, np.ones((7, 7), np.uint8))
    m = cv2.GaussianBlur(m.astype(np.float32) / 255, (0, 0), 5)
    y = np.arange(h, dtype=np.float32)[:, None] / TOP_FADE
    fade = np.clip(y, 0, 1)
    fade = fade * fade * (3 - 2 * fade)
    return m * fade


def background_plate(median):
    small = cv2.resize(median, (480, 270))
    hole = (sand_weight(small) > 0.05).astype(np.uint8) * 255
    hole = cv2.dilate(hole, np.ones((9, 9), np.uint8))
    plate = cv2.inpaint(small, hole, 15, cv2.INPAINT_TELEA).astype(np.float32)
    plate = cv2.GaussianBlur(plate, (0, 0), 18)
    return cv2.resize(plate, (median.shape[1], median.shape[0]), interpolation=cv2.INTER_CUBIC)


def sand_weight(frame):
    sat = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)[..., 1].astype(np.float32) / 255
    s = np.clip((sat - 0.28) / 0.15, 0, 1)
    return cv2.GaussianBlur(s, (0, 0), 6 * frame.shape[1] / 1920)


def grade(frame, plate):
    f = frame.astype(np.float32)
    glass = PAGE_BGR * (f / np.maximum(plate, 1))
    sand = np.clip(f * 1.22 + 10, 0, 255)
    s = sand_weight(frame)[..., None]
    return np.clip(glass * (1 - s) + sand * s, 0, 255).astype(np.uint8)


def crop(img):
    x, y, w, h = CROP
    return cv2.resize(img[y:y + h, x:x + w], (OUT_W, OUT_H), interpolation=cv2.INTER_AREA)


def encode(frames, fps, path, args):
    cmd = [
        "ffmpeg", "-v", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{OUT_W}x{OUT_H}", "-r", fps, "-i", "-",
        *args,
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
        "-an", str(path),
    ]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in frames:
        p.stdin.write(f.tobytes())
    p.stdin.close()
    if p.wait():
        raise SystemExit(f"ffmpeg failed for {path}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    frames = read_frames(SRC)
    median = np.median(np.stack(frames[::3]), axis=0).astype(np.uint8)

    mask = build_mask(outline(median), median.shape[:2])
    plate = background_plate(median)
    graded = [crop(grade(f, plate)) for f in frames]

    # seamless loop: the last K frames dissolve into the first K
    n, k = len(graded), LOOP_XFADE
    loop = []
    for i in range(n - k):
        if i < k:
            a = (i + 0.5) / k
            a = a * a * (3 - 2 * a)
            loop.append(cv2.addWeighted(graded[n - k + i], 1 - a, graded[i], a, 0))
        else:
            loop.append(graded[i])

    fps = "24000/1001"
    encode(loop, fps, OUT / "hourglass.webm",
           ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", "34", "-row-mt", "1", "-pix_fmt", "yuv420p"])
    encode(loop, fps, OUT / "hourglass.mp4",
           ["-c:v", "libx264", "-crf", "22", "-preset", "slow", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-tag:v", "avc1"])

    m = crop((mask * 255).astype(np.uint8)[..., None].repeat(3, 2))[..., 0]
    m = cv2.resize(m, (OUT_W // 2, OUT_H // 2), interpolation=cv2.INTER_AREA)
    rgba = np.zeros((*m.shape, 4), np.uint8)
    rgba[..., 3] = m
    cv2.imwrite(str(OUT / "hourglass-mask.png"), rgba, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    cv2.imwrite(str(OUT / "hourglass-poster.jpg"), loop[0], [cv2.IMWRITE_JPEG_QUALITY, 86])

    # preview on the page colour, for checking the cut
    mm = cv2.resize(m, (OUT_W, OUT_H)).astype(np.float32)[..., None] / 255
    preview = loop[0] * mm + PAGE_BGR * (1 - mm)
    cv2.imwrite(str(ROOT / "tools" / "hourglass-preview.png"), preview.astype(np.uint8))
    print(f"{len(loop)} frames -> {OUT}")


if __name__ == "__main__":
    main()
