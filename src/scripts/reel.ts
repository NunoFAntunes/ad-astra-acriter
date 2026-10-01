import timeline from './hero-reel.json';
import { watchSize } from './wordmark';

// The hero reel is one video (built by tools/hero_reel.py); its words and
// soundtrack are timed off video.currentTime, so they stay with the footage
// through buffering, tab switches and skips.

interface Rendition { av1: string; h264: string }
export interface ReelSources { landscape: Rendition; portrait: Rendition }

type Orientation = keyof ReelSources;

const segment = (clip: number) => {
  const s = timeline.segments.find((seg) => seg.clip === clip);
  if (!s) throw new Error(`hero-reel.json has no clip ${clip}`);
  return s;
};

// Cue times in seconds on the reel, anchored to the clip each belongs to.
// Fade-outs start early enough to finish as their clip dissolves away.
const CUES = (() => {
  const words1 = segment(2);
  const words2 = segment(6);
  const name = segment(7);
  return {
    header: 0.8,
    line1: [words1.start + 0.4, words1.end - 1.6],
    line2: [words2.start + 0.3, words2.end - 1.5],
    markIn: name.start + 0.4,
    markCollapse: name.start + 3.6,
    markOut: name.end - 1.4,
  } as const;
})();

// Sound is on unless the visitor turned it off before. Browsers may still
// refuse to start it without a click, in which case the toggle shows it off.
const SOUND_KEY = 'aaa:sound';
const SOUND_DRIFT = 0.3; // s the soundtrack may wander from the picture

function readSoundPref(): boolean {
  try { return localStorage.getItem(SOUND_KEY) !== 'off'; } catch { return true; }
}

function storeSoundPref(on: boolean): void {
  try { localStorage.setItem(SOUND_KEY, on ? 'on' : 'off'); } catch { /* storage blocked */ }
}

// The veil behind the words rises a little before them and lingers after.
const VEIL_LEAD = 0.3;
const VEIL_TAIL = 0.6;

const within = (t: number, from: number, to: number) => t >= from - VEIL_LEAD && t < to + VEIL_TAIL;

interface Elements {
  hero: HTMLElement;
  video: HTMLVideoElement;
  header: HTMLElement | null;
  lines: [HTMLElement, HTMLElement];
  mark: HTMLElement;
  audio: HTMLAudioElement;
  controls: HTMLElement;
  control: HTMLButtonElement;
  mute: HTMLButtonElement;
  label: HTMLElement;
  sources: ReelSources;
}

function orientation(hero: HTMLElement): Orientation {
  return hero.clientWidth < hero.clientHeight ? 'portrait' : 'landscape';
}

function pickSource(video: HTMLVideoElement, rendition: Rendition): string {
  return video.canPlayType('video/mp4; codecs="av01.0.08M.08"') === 'probably' ? rendition.av1 : rendition.h264;
}

function showWords(els: Elements, t: number): void {
  const { hero, header, lines: [line1, line2], mark } = els;

  if (t >= CUES.header) header?.classList.add('is-in');

  for (const [line, [from, to]] of [[line1, CUES.line1], [line2, CUES.line2]] as const) {
    line.classList.toggle('is-in', t >= from);
    line.classList.toggle('is-out', t >= to);
  }

  // The full name lights up, then folds down to ΛΛΛ and fades.
  mark.classList.toggle('is-in', t >= CUES.markIn && t < CUES.markOut);
  mark.classList.toggle('is-open', t < CUES.markCollapse);
  mark.classList.toggle('is-lit', t >= CUES.markIn && t < CUES.markCollapse);

  hero.classList.toggle('has-text',
    within(t, ...CUES.line1) || within(t, ...CUES.line2) || within(t, CUES.markIn, CUES.markOut));
}

export function runReel(): void {
  const hero = document.querySelector<HTMLElement>('.hero');
  const video = hero?.querySelector<HTMLVideoElement>('.reel-video');
  const audio = hero?.querySelector<HTMLAudioElement>('.reel-sound');
  const controls = hero?.querySelector<HTMLElement>('.reel-controls');
  const mute = hero?.querySelector<HTMLButtonElement>('.reel-mute');
  const line1 = hero?.querySelector<HTMLElement>('[data-line="1"]');
  const line2 = hero?.querySelector<HTMLElement>('[data-line="2"]');
  const mark = hero?.querySelector<HTMLElement>('[data-hero-mark]');
  const control = hero?.querySelector<HTMLButtonElement>('.reel-control');
  const label = control?.querySelector<HTMLElement>('.reel-control-label');
  const header = document.querySelector<HTMLElement>('.site-header');

  if (!hero || !video?.dataset.sources || !audio || !line1 || !line2 || !mark || !controls || !control || !mute || !label) {
    header?.classList.add('is-in');
    return;
  }

  const els: Elements = {
    hero, video, audio, header, mark, controls, control, mute, label,
    lines: [line1, line2],
    sources: JSON.parse(video.dataset.sources) as ReelSources,
  };

  let loaded: Orientation | undefined;
  let frame = 0;
  let soundOn = readSoundPref();
  let stalled = true; // until the video is actually playing

  const setState = (state: 'loading' | 'playing' | 'ended') => { hero.dataset.state = state; };

  // The soundtrack is shorter than the reel and plays once from the top.
  const soundLeft = () => !(video.currentTime >= audio.duration - 0.05);

  const showSound = () => {
    if (mute.getAttribute('aria-pressed') !== String(soundOn)) {
      mute.setAttribute('aria-pressed', String(soundOn));
      mute.title = soundOn ? 'Mute' : 'Unmute';
    }
    mute.classList.toggle('is-gone', hero.dataset.state === 'ended' || !soundLeft());
  };

  const refused = (e: unknown) => {
    // NotAllowedError: no click yet, so the browser won't play sound.
    if (e instanceof DOMException && e.name === 'NotAllowedError') {
      soundOn = false;
      showSound();
    }
  };

  // Play, pause or re-align the soundtrack to match the picture.
  const syncSound = () => {
    const want = soundOn && hero.dataset.state !== 'ended' && !video.paused && !stalled && soundLeft();
    if (!want) {
      if (!audio.paused) audio.pause();
      return;
    }
    if (Math.abs(audio.currentTime - video.currentTime) > SOUND_DRIFT) audio.currentTime = video.currentTime;
    if (audio.paused) audio.play().catch(refused);
  };

  // Start the soundtrack from a click (or try to, on load): browsers only
  // unlock audio for play() calls made right there, so call it now and let
  // syncSound pause it again if the picture isn't running yet.
  const primeSound = () => {
    if (!soundOn || !soundLeft()) return;
    audio.currentTime = video.currentTime;
    audio.play().then(syncSound, refused);
  };

  const tick = () => {
    showWords(els, video.currentTime);
    control.style.setProperty('--progress', String(video.currentTime / timeline.duration));
    if (soundOn) syncSound();
    showSound();
    frame = video.paused || video.ended ? 0 : requestAnimationFrame(tick);
  };

  // Rest on the closing still with nothing over it.
  const end = (labelText = 'Replay') => {
    cancelAnimationFrame(frame);
    frame = 0;
    video.pause();
    audio.pause();
    showWords(els, Infinity);
    header?.classList.add('is-in');
    setState('ended');
    label.textContent = labelText;
    showSound();
  };

  // Load the rendition matching the hero's shape; keeps the position when
  // a rotation swaps it mid-play.
  const load = (want: Orientation) => {
    const at = video.currentTime;
    const playing = !video.paused;
    loaded = want;
    video.src = pickSource(video, els.sources[want]);
    if (at > 0) {
      video.addEventListener('loadedmetadata', () => { video.currentTime = at; }, { once: true });
      if (playing) video.play().catch(() => end());
    }
  };

  const start = () => {
    const want = orientation(hero);
    if (loaded !== want) load(want);
    video.currentTime = 0;
    showWords(els, 0);
    setState('loading');
    stalled = true;
    label.textContent = 'Skip intro';
    showSound();
    video.play().catch(() => end('Play intro'));
    primeSound();
  };

  video.addEventListener('playing', () => {
    setState('playing');
    stalled = false;
    syncSound();
    if (!frame) frame = requestAnimationFrame(tick);
  });
  video.addEventListener('waiting', () => { stalled = true; syncSound(); });
  video.addEventListener('pause', syncSound);
  video.addEventListener('ended', () => end());

  mute.addEventListener('click', () => {
    soundOn = !soundOn;
    storeSoundPref(soundOn);
    showSound();
    if (soundOn) primeSound();
    else audio.pause();
  });

  control.addEventListener('click', () => {
    if (hero.dataset.state === 'ended') start();
    else end();
  });

  let resizeTimer: ReturnType<typeof setTimeout> | undefined;
  new ResizeObserver(() => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      const want = orientation(hero);
      if (loaded && loaded !== want && hero.dataset.state !== 'ended') load(want);
    }, 250);
  }).observe(hero);

  document.fonts.ready.then(() => watchSize(mark));
  controls.hidden = false;

  if (matchMedia('(prefers-reduced-motion: reduce)').matches) end('Play intro');
  else start();
}
