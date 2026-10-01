"""
Builds the hero reel from videos/clip_1.mp4 ... clip_8.mp4.

Steps:
  1. slow each clip by its SPEED factor, motion-interpolating the in-between
     frames (plain frame repetition judders at these rates), and sharpen a
     touch to win back what the clips' web compression softened
  2. join the clips with short dissolves into one lossless-ish master
  3. encode a landscape (16:9) and a portrait (4:5 centre crop) rendition,
     each as AV1 + H.264 MP4, without audio
  4. write first/last-frame stills and the segment timeline the hero script
     uses to place its text (src/scripts/hero-reel.json)
  5. prepare the soundtrack (videos/audio-6s.mp3): lift its level and fade
     the tail, which otherwise cuts off at full swell

One file instead of eight keeps playback gapless on every browser, and lets
the page time its text off video.currentTime.

Usage:
  python3 tools/hero_reel.py      (needs ffmpeg + ffprobe on PATH)
"""

import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "videos"
OUT = ROOT / "src" / "assets" / "hero"
TIMELINE = ROOT / "src" / "scripts" / "hero-reel.json"

FPS = "24000/1001"
FRAME = 1001 / 24000
XFADE = 0.5  # s, dissolve between clips

# (clip, playback speed). Clips carrying text run slower so it can be read.
SEGMENTS = [
    (1, 0.65),  # opening hold
    (2, 0.60),  # "In a changing world"
    (3, 0.65),
    (4, 0.65),
    (5, 0.65),
    (6, 0.35),  # "We must rethink"
    (7, 0.40),  # Ad Astra Acriter -> ΛΛΛ
    (8, 0.70),  # runs out to the closing still
]

PORTRAIT_CROP = "crop=864:1080:(iw-864)/2:0"  # 4:5 from the 1080p frame
SHARPEN = "cas=0.35"  # contrast-adaptive, so flat areas don't get noisier

SOUND_IN = SRC / "audio-6s.mp3"
SOUND_PEAK = -6.0   # dBFS; the source peaks around -18
SOUND_FADE = 0.8    # s, fade-out at the end

INTERPOLATE = (
    "minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"
).format(fps=FPS)


def run(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def frame_count(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
         "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    return int(out.stdout.strip())


def render_segment(clip, speed, dest):
    vf = [f"setpts=PTS/{speed}"]
    if speed != 1:
        vf.append(INTERPOLATE)
    vf += [SHARPEN, f"fps={FPS}", "format=yuv420p", "setsar=1"]
    run("-i", str(SRC / f"clip_{clip}.mp4"), "-an", "-vf", ",".join(vf),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "10", str(dest))


def join(parts, durations, dest):
    """Chain xfade over all parts; returns each segment's (start, end) in the result."""
    chain, spans = [], []
    prev, start = "[0:v]", 0.0
    for k in range(1, len(parts)):
        spans.append((start, start + durations[k - 1]))
        offset = start + durations[k - 1] - XFADE
        label = f"[x{k}]"
        chain.append(f"{prev}[{k}:v]xfade=transition=fade:duration={XFADE}:offset={offset:.4f}{label}")
        prev, start = label, offset
    spans.append((start, start + durations[-1]))

    inputs = [a for p in parts for a in ("-i", str(p))]
    run(*inputs, "-filter_complex", ";".join(chain), "-map", prev,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "10", "-pix_fmt", "yuv420p", str(dest))
    return spans


def encode(master, name, vf=None):
    filters = ["-vf", vf] if vf else []
    common = ["-an", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    # AV1 for browsers with a decoder for it (smaller, cleaner), H.264 for the rest
    run("-i", str(master), *filters, *common,
        "-c:v", "libsvtav1", "-preset", "4", "-crf", "32", "-g", "240", str(OUT / f"{name}-av1.mp4"))
    run("-i", str(master), *filters, *common,
        "-c:v", "libx264", "-preset", "slow", "-crf", "23", "-profile:v", "high", str(OUT / f"{name}.mp4"))


def sound(dest):
    out = subprocess.run(
        ["ffmpeg", "-i", str(SOUND_IN), "-af", "volumedetect", "-f", "null", "-"],
        check=True, capture_output=True, text=True,
    ).stderr
    peak = float(out.split("max_volume:")[1].split("dB")[0])
    length = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(SOUND_IN)],
        check=True, capture_output=True, text=True,
    ).stdout)
    af = f"volume={SOUND_PEAK - peak:.2f}dB,afade=t=out:st={length - SOUND_FADE:.3f}:d={SOUND_FADE}"
    run("-i", str(SOUND_IN), "-af", af, "-c:a", "libmp3lame", "-q:a", "2", str(dest))


def still(master, frame, dest):
    run("-i", str(master), "-vf", f"select=eq(n\\,{frame})", "-frames:v", "1", "-q:v", "3", str(dest))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        parts, durations = [], []
        for clip, speed in SEGMENTS:
            part = tmp / f"seg_{clip}.mp4"
            print(f"clip {clip} at {speed}x")
            render_segment(clip, speed, part)
            parts.append(part)
            durations.append(frame_count(part) * FRAME)

        master = tmp / "master.mp4"
        print("joining")
        spans = join(parts, durations, master)
        frames = frame_count(master)

        print("encoding")
        encode(master, "reel")
        encode(master, "reel-portrait", PORTRAIT_CROP)
        still(master, 0, OUT / "first.jpg")
        still(master, frames - 1, OUT / "last.jpg")
    sound(OUT / "sound.mp3")

    timeline = {
        "duration": round(frames * FRAME, 3),
        "segments": [
            {"clip": clip, "start": round(s, 3), "end": round(e, 3)}
            for (clip, _), (s, e) in zip(SEGMENTS, spans)
        ],
    }
    TIMELINE.write_text(json.dumps(timeline, indent=2) + "\n")
    print(json.dumps(timeline, indent=2))


if __name__ == "__main__":
    main()
