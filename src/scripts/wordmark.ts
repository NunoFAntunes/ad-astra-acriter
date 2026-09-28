// Tails animate between 0 and their natural width, so measure it (and re-measure
// when fonts load or the viewport changes the font size).
function measure(wordmark: HTMLElement): void {
  wordmark.querySelectorAll<HTMLElement>('.wm-tail').forEach((tail) => {
    const letters = tail.firstElementChild;
    if (!letters) return;
    tail.style.setProperty('--w', `${letters.getBoundingClientRect().width}px`);
  });
}

export function watchSize(wordmark: HTMLElement): void {
  measure(wordmark);
  const ro = new ResizeObserver(() => measure(wordmark));
  wordmark.querySelectorAll('.wm-letters').forEach((el) => ro.observe(el));
}

export function setOpen(wordmark: HTMLElement, open: boolean): void {
  wordmark.classList.toggle('is-open', open);
  wordmark.classList.toggle('is-lit', open);
}

// Expand on hover / keyboard focus. The short leave delay stops it flickering
// when the pointer grazes the edge.
export function bindHover(trigger: HTMLElement, wordmark: HTMLElement): void {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const open = () => { clearTimeout(timer); setOpen(wordmark, true); };
  const close = () => { clearTimeout(timer); timer = setTimeout(() => setOpen(wordmark, false), 140); };
  trigger.addEventListener('pointerenter', (e) => { if (e.pointerType === 'mouse') open(); });
  trigger.addEventListener('pointerleave', (e) => { if (e.pointerType === 'mouse') close(); });
  trigger.addEventListener('focus', () => { if (trigger.matches(':focus-visible')) open(); });
  trigger.addEventListener('blur', close);
}
