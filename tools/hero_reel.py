"""
Builds the hero reel from videos/1.mp4 ... 8.mp4.

Steps:
  1. paint out the signature watermark on the clips that carry one (see
     WATERMARKS), slow each clip by its SPEED factor, motion-interpolating the
     in-between frames (plain frame repetition judders at these rates), and
     sharpen a touch to win back what the clips' web compression softened
  2. join the clips with short dissolves into one lossless-ish master
  3. encode a landscape (16:9) and a portrait (4:5 centre crop) rendition,
     each as AV1 + H.264 MP4, without audio
  4. write first/last-frame stills and the segment timeline the hero script
     uses to place its text (src/scripts/hero-reel.json)
  5. prepare the soundtrack from videos/audio-6s.mp3, which swells from
     silence to a steady patter: play it once, then carry that patter on
     unbroken for the rest of the reel (see bed()), lift its level and fade
     it out with the closing clip

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
    (1, 0.80),  # opening hold
    (2, 0.70),  # "In a changing world"
    (3, 0.90),
    (4, 0.90),
    (5, 0.90),
    (6, 0.60),  # "We must rethink"
    (7, 0.50),  # Ad Astra Acriter -> ΛΛΛ, which then holds
    (8, 0.80),  # runs out to the closing still
]

# A faint signature sits low in the dish on the first and last clip. It is
# painted over with the dish itself: the frame turned a little about the
# dish's centre puts beads from the same ring, moving the same way, over the
# mark. Only that copy's fine texture is used; its light comes from a smooth
# fill of the mark's surroundings, since the dish is lit unevenly around.
#   centre: dish centre (px), box: the mark (x0, y0, x1, y1), feather: px
WATERMARKS = {
    1: dict(centre=(959, 533), box=(865, 958, 1110, 988), feather=18),
    8: dict(centre=(982, 536), box=(850, 932, 1120, 990), feather=20),
}
WATERMARK_TURN = 40  # degrees; clears the mark's own width at its radius
WATERMARK_DETAIL = 12  # px, blur radius splitting texture from light

PORTRAIT_CROP = "crop=864:1080:(iw-864)/2:0"  # 4:5 from the 1080p frame
SHARPEN = "cas=0.35"  # contrast-adaptive, so flat areas don't get noisier

SOUND_IN = SRC / "audio-6s.mp3"
SOUND_PEAK = -6.0       # dBFS; the source peaks around -18
SOUND_FADE = 3.0        # s, fade-out as the last clip settles
# The patter that carries on after the swell is cut from the steady end of
# the source (its last ~2.5 s). Each take starts a little apart, plays a
# touch higher or lower and may swap channels, so the overlapping takes
# don't fall into an audible loop: (start s, rate, swap channels).
BED_TAKES = [(3.5, 1.00, False), (3.75, 0.97, True), (3.6, 1.03, False),
             (3.85, 1.00, True), (3.55, 0.97, False), (3.7, 1.03, True)]
BED_XFADE = 1.0         # s, equal-power overlap between takes

INTERPOLATE = (
    "minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"
).format(fps=FPS)


def run(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def probe(path, entries, stream=None):
    sel = ["-select_streams", stream] if stream else []
    out = subprocess.run(
        ["ffprobe", "-v", "error", *sel, *entries, "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    return out.stdout.strip()


def frame_count(path):
    return int(probe(path, ["-count_frames", "-show_entries", "stream=nb_read_frames"], "v:0"))


def unmark(src, centre, box, feather):
    """Filter graph from [0:v] to [clean] that paints the watermark out."""
    w, h = map(int, probe(src, ["-show_entries", "stream=width,height"], "v:0").split(","))
    cx, cy = centre
    x0, y0, x1, y1 = box
    # rotate turns about the frame centre, so pad the dish's centre onto it first
    pad = max(w, h) // 4
    ox, oy = w // 2 + pad - cx, h // 2 + pad - cy
    # the smooth fill takes its edge from just outside the feathered mask
    lx, ly = x0 - feather - 2, y0 - feather - 2
    lw, lh = x1 - x0 + 2 * feather + 4, y1 - y0 + 2 * feather + 4
    # 1 inside the box, falling to 0 over `feather` px outside it
    mask = (f"255*clip(1-hypot(max(max({x0}-X\\,X-{x1})\\,0)\\,"
            f"max(max({y0}-Y\\,Y-{y1})\\,0))/{feather}\\,0\\,1)")
    blur = f"gblur=sigma={WATERMARK_DETAIL}"
    # gbrp throughout: maskedmerge blends each plane by the mask's own plane
    return ";".join([
        "[0:v]format=gbrp,split=4[orig][turn][fill][mask]",
        f"[turn]pad={w + 2 * pad}:{h + 2 * pad}:{ox}:{oy},rotate={WATERMARK_TURN}*PI/180,"
        f"crop={w}:{h}:{ox}:{oy},split[t1][t2]",
        f"[t2]{blur}[tb]",
        "[t1][tb]blend=all_expr='A-B+128'[texture]",
        f"[fill]format=yuv444p,delogo={lx}:{ly}:{lw}:{lh},format=gbrp,{blur}[light]",
        "[light][texture]blend=all_expr='A+B-128'[patch]",
        f"[mask]format=gray,geq=lum={mask},format=gbrp[m]",
        "[orig][patch][m]maskedmerge,format=yuv420p[clean]",
    ])


def render_segment(clip, speed, dest):
    src = SRC / f"{clip}.mp4"
    vf = [f"setpts=PTS/{speed}"]
    if speed != 1:
        vf.append(INTERPOLATE)
    vf += [SHARPEN, f"fps={FPS}", "format=yuv420p", "setsar=1"]
    if clip in WATERMARKS:
        graph = f"{unmark(src, **WATERMARKS[clip])};[clean]{','.join(vf)}[v]"
    else:
        graph = f"[0:v]{','.join(vf)}[v]"
    run("-i", str(src), "-an", "-filter_complex", graph, "-map", "[v]",
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


def level(start, length):
    """RMS level (dB) of the source between start and start + length."""
    out = subprocess.run(
        ["ffmpeg", "-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", str(SOUND_IN), "-af",
         "astats=measure_perchannel=none:measure_overall=RMS_level", "-f", "null", "-"],
        check=True, capture_output=True, text=True,
    ).stderr
    return float(out.rsplit("RMS level dB:", 1)[1].split()[0])


def bed(duration):
    """Filter graph from [0:a] to [bed]: the source once, then its steady tail
    carried on in overlapping takes until `duration`.

    The patter still builds a little through the tail, so each take is levelled
    out to the tail's end, which is where the swell hands over to it."""
    length = float(probe(SOUND_IN, ["-show_entries", "format=duration"]))
    rate = int(probe(SOUND_IN, ["-show_entries", "stream=sample_rate"], "a:0"))
    top = level(length - 0.5, 0.5)
    takes, filled, k = [], length, 0
    while filled < duration:
        start, speed, swap = BED_TAKES[k % len(BED_TAKES)]
        span = length - start
        lift = top - level(start, 0.5)  # dB the take's head is under its tail
        chain = [f"atrim={start}:{length}", "asetpts=PTS-STARTPTS",
                 f"volume='pow(10,{lift:.2f}*(1-t/{span:.3f})/20)':eval=frame"]
        if speed != 1:
            chain += [f"asetrate={round(rate * speed)}", f"aresample={rate}"]
        if swap:
            chain.append("pan=stereo|c0=c1|c1=c0")
        takes.append(",".join(chain))
        filled += span / speed - BED_XFADE
        k += 1

    graph = [f"[0:a]asplit={len(takes) + 1}" + "".join(f"[s{i}]" for i in range(len(takes) + 1)),
             f"[s0]atrim=0:{length}[t0]"]
    graph += [f"[s{i + 1}]{take}[t{i + 1}]" for i, take in enumerate(takes)]
    prev = "[t0]"
    for i in range(1, len(takes) + 1):
        graph.append(f"{prev}[t{i}]acrossfade=d={BED_XFADE}:c1=qsin:c2=qsin[x{i}]")
        prev = f"[x{i}]"
    graph.append(f"{prev}atrim=duration={duration:.3f}[bed]")
    return ";".join(graph)


def sound(dest, duration):
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "bed.wav"
        run("-i", str(SOUND_IN), "-filter_complex", bed(duration), "-map", "[bed]", str(raw))
        out = subprocess.run(
            ["ffmpeg", "-i", str(raw), "-af", "volumedetect", "-f", "null", "-"],
            check=True, capture_output=True, text=True,
        ).stderr
        peak = float(out.split("max_volume:")[1].split("dB")[0])
        af = f"volume={SOUND_PEAK - peak:.2f}dB,afade=t=out:st={duration - SOUND_FADE:.3f}:d={SOUND_FADE}"
        run("-i", str(raw), "-af", af, "-c:a", "libmp3lame", "-b:a", "128k", str(dest))


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
    sound(OUT / "sound.mp3", frames * FRAME)

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
