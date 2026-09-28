// Hero video variants, switchable from the settings panel for review.
// The choice persists in localStorage; a ?hero=<variant> link overrides it.

export const HERO_VARIANTS = ['bulb', 'neck'] as const;
export type HeroVariant = (typeof HERO_VARIANTS)[number];

export interface HeroSources {
  webm: string;
  mp4: string;
  poster: string;
}

const KEY = 'aaa:hero-variant';
const PARAM = 'hero';
const EVENT = 'hero-variant';
const SWAP_OUT = 450;       // ms, matches .hourglass.is-swapping
const FRAME_TIMEOUT = 2000; // don't stay blank if the video never loads

export const isVariant = (v: unknown): v is HeroVariant => HERO_VARIANTS.includes(v as HeroVariant);

export function readVariant(): HeroVariant {
  const param = new URLSearchParams(location.search).get(PARAM);
  if (isVariant(param)) return param;
  try {
    const stored = localStorage.getItem(KEY);
    if (isVariant(stored)) return stored;
  } catch { /* storage blocked */ }
  return HERO_VARIANTS[0];
}

export function chooseVariant(variant: HeroVariant): void {
  try { localStorage.setItem(KEY, variant); } catch { /* storage blocked */ }
  // keep the address shareable as the variant being looked at
  const url = new URL(location.href);
  url.searchParams.set(PARAM, variant);
  history.replaceState(history.state, '', url);
  dispatchEvent(new CustomEvent<HeroVariant>(EVENT, { detail: variant }));
}

const wait = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));

function firstFrame(video: HTMLVideoElement): Promise<void> {
  return new Promise((resolve) => {
    if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) return resolve();
    video.addEventListener('loadeddata', () => resolve(), { once: true });
    setTimeout(resolve, FRAME_TIMEOUT);
  });
}

function setSources(hourglass: HTMLElement, video: HTMLVideoElement, sources: HeroSources, variant: HeroVariant): void {
  hourglass.dataset.variant = variant;
  video.poster = sources.poster;
  const [webm, mp4] = video.querySelectorAll('source');
  if (webm) webm.src = sources.webm;
  if (mp4) mp4.src = sources.mp4;
  // restarts resource selection; autoplay (if still set) resumes playback
  video.load();
}

// Applies the stored variant straight away (call before the intro), then
// crossfades whenever the settings panel picks another one.
export function bindHeroVariant(hourglass: HTMLElement): void {
  const video = hourglass.querySelector('video');
  if (!video || !hourglass.dataset.sources) return;
  const sources = JSON.parse(hourglass.dataset.sources) as Record<HeroVariant, HeroSources>;

  const initial = readVariant();
  if (initial !== hourglass.dataset.variant) setSources(hourglass, video, sources[initial], initial);

  let target = initial;
  let seq = 0;
  addEventListener(EVENT, async (e) => {
    const variant = (e as CustomEvent<HeroVariant>).detail;
    if (variant === target) return;
    target = variant;
    const id = ++seq;
    hourglass.classList.add('is-swapping');
    await wait(SWAP_OUT);
    if (id !== seq) return;
    setSources(hourglass, video, sources[variant], variant);
    await firstFrame(video);
    if (id === seq) hourglass.classList.remove('is-swapping');
  });
}
