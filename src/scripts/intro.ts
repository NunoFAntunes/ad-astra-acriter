import { bindHover, setOpen, watchSize } from './wordmark';

// Intro timings (ms). Each step waits for the previous one.
const INTRO = {
  headerIn: 300,
  hourglassIn: 200,
  line1In: 1100,
  line1Hold: 2600,
  line2In: 900,     // after line 1 starts fading out
  line2Hold: 2600,
  markIn: 1300,     // after line 2 starts fading out
  markHold: 3200,
  collapse: 2400,   // time for the collapse to settle
} as const;

interface IntroElements {
  header: HTMLElement;
  hourglass: HTMLElement;
  lines: [HTMLElement, HTMLElement];
  heroMark: HTMLElement;
}

const wait = (ms: number) => new Promise<void>((r) => setTimeout(r, ms));
const nextFrame = () => new Promise<void>((r) => requestAnimationFrame(() => requestAnimationFrame(() => r())));

// Reduced motion gets the settled ΛΛΛ straight away;
// only the gentle fade-in remains.
function showEndState({ header, hourglass, heroMark }: IntroElements): void {
  heroMark.classList.add('no-anim');
  heroMark.classList.remove('is-open', 'is-lit');
  heroMark.getBoundingClientRect();
  requestAnimationFrame(() => {
    heroMark.classList.remove('no-anim');
    [header, hourglass, heroMark].forEach((el) => el.classList.add('is-in'));
  });
}

async function playIntro({ header, hourglass, lines, heroMark }: IntroElements): Promise<void> {
  const [line1, line2] = lines;

  await wait(INTRO.hourglassIn);
  hourglass.classList.add('is-in');
  await wait(INTRO.headerIn);
  header.classList.add('is-in');

  await wait(INTRO.line1In);
  line1.classList.add('is-in');
  await wait(INTRO.line1Hold);
  line1.classList.add('is-out');

  await wait(INTRO.line2In);
  line2.classList.add('is-in');
  await wait(INTRO.line2Hold);
  line2.classList.add('is-out');

  // The full name appears, then the tails fold away leaving ΛΛΛ.
  await wait(INTRO.markIn);
  heroMark.classList.add('is-in', 'is-lit');
  await wait(INTRO.markHold);
  heroMark.classList.remove('is-lit', 'is-open');
  await wait(INTRO.collapse);
}

export async function runIntro(): Promise<void> {
  const header = document.querySelector<HTMLElement>('.site-header');
  const hourglass = document.querySelector<HTMLElement>('.hourglass');
  const video = hourglass?.querySelector('video');
  const line1 = document.querySelector<HTMLElement>('[data-line="1"]');
  const line2 = document.querySelector<HTMLElement>('[data-line="2"]');
  const heroMark = document.querySelector<HTMLElement>('[data-hero-mark]');
  if (!header || !hourglass || !video || !line1 || !line2 || !heroMark) return;

  const els: IntroElements = { header, hourglass, lines: [line1, line2], heroMark };

  const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduceMotion) {
    video.removeAttribute('autoplay');
    video.pause();
  }

  await document.fonts.ready;
  watchSize(heroMark);

  if (reduceMotion) {
    showEndState(els);
  } else {
    await nextFrame();
    await playIntro(els);
  }

  bindHover(heroMark, heroMark);
  // The pointer may already be resting on the mark when the intro ends.
  if (heroMark.matches(':hover')) setOpen(heroMark, true);
}
