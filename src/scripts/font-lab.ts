import mazius from '../assets/fonts/lab/MaziusDisplay-Regular.woff2?url';
import happyTimes from '../assets/fonts/lab/HappyTimes-Regular.woff2?url';

// Font lab: hero lines set in candidate typefaces so the client can compare
// them on the real reel (components/FontLab.astro, opened with ?fonts).
// Every face is free for commercial use: SIL OFL (Google Fonts, Collletttivo,
// Velvetyne) or the ITF Free Font License (Fontshare). The candidates load
// from their CDNs for the test; the one picked gets self-hosted like Jost.

type Load =
  | { google: string } // css2 family spec, e.g. "Ysabeau:wght@380"
  | { fontshare: string } // api slug + weight, e.g. "zodiak@300"
  | { file: string } // self-hosted woff2
  | null; // already on the page

export interface LabFont {
  id: string;
  name: string;
  kind: 'Serif' | 'Sans';
  source: string;
  family: string;
  weight: number;
  /** Optical correction so every face sits at roughly the same size. */
  scale?: number;
  tracking?: string;
  load: Load;
  note: string;
}

export const FONTS: LabFont[] = [
  {
    id: 'jost', name: 'Jost', kind: 'Sans', source: 'Current · Google Fonts',
    family: 'Jost', weight: 380, tracking: '.015em', load: null,
    note: 'The current face. Geometric, after Futura, matching the logo.',
  },
  {
    id: 'zodiak', name: 'Zodiak', kind: 'Serif', source: 'Fontshare · ITF Free Font',
    family: 'Zodiak', weight: 300, load: { fontshare: 'zodiak@300' },
    note: 'Sharp, high-contrast serif. Calm and confident.',
  },
  {
    id: 'boska', name: 'Boska', kind: 'Serif', source: 'Fontshare · ITF Free Font',
    family: 'Boska', weight: 400, scale: 1.06, load: { fontshare: 'boska@400' },
    note: 'Light editorial serif with calligraphic strokes. Quiet, literary.',
  },
  {
    id: 'marcellus', name: 'Marcellus', kind: 'Serif', source: 'Google Fonts · OFL',
    family: 'Marcellus', weight: 400, load: { google: 'Marcellus' },
    note: 'Flared Roman letters, cut in stone. Fits the Latin name.',
  },
  {
    id: 'mazius', name: 'Mazius Display', kind: 'Serif', source: 'Collletttivo · OFL',
    family: 'Mazius Display', weight: 400, load: { file: mazius },
    note: 'Old-style serif with quirky, calligraphic details.',
  },
  {
    id: 'ysabeau', name: 'Ysabeau', kind: 'Sans', source: 'Google Fonts · OFL',
    family: 'Ysabeau', weight: 380, load: { google: 'Ysabeau:wght@380' },
    note: 'A sans with Garamond in its bones. Warm and elegant.',
  },
  {
    id: 'tenor', name: 'Tenor Sans', kind: 'Sans', source: 'Google Fonts · OFL',
    family: 'Tenor Sans', weight: 400, scale: .94, tracking: '.01em', load: { google: 'Tenor Sans' },
    note: 'Wide humanist sans with classical proportions.',
  },
  {
    id: 'rowan', name: 'Rowan', kind: 'Serif', source: 'Fontshare · ITF Free Font',
    family: 'Rowan', weight: 300, load: { fontshare: 'rowan@300' },
    note: 'Compact, crisp serif. Modern and to the point.',
  },
  {
    id: 'gambetta', name: 'Gambetta', kind: 'Serif', source: 'Fontshare · ITF Free Font',
    family: 'Gambetta', weight: 300, load: { fontshare: 'gambetta@300' },
    note: 'Classic book serif, made sharper. Trustworthy.',
  },
  {
    id: 'melodrama', name: 'Melodrama', kind: 'Serif', source: 'Fontshare · ITF Free Font',
    family: 'Melodrama', weight: 400, scale: 1.06, load: { fontshare: 'melodrama@400' },
    note: 'Fine, high-contrast display face with theatrical curves.',
  },
  {
    id: 'caslon', name: 'Libre Caslon Display', kind: 'Serif', source: 'Google Fonts · OFL',
    family: 'Libre Caslon Display', weight: 400, scale: 1.06, load: { google: 'Libre Caslon Display' },
    note: 'Caslon cut for large sizes. Refined, slightly narrow.',
  },
  {
    id: 'kalnia', name: 'Kalnia', kind: 'Serif', source: 'Google Fonts · OFL',
    family: 'Kalnia', weight: 300, scale: .9, load: { google: 'Kalnia:wght@300' },
    note: 'Wide, high-contrast serif. Spacious and stately.',
  },
  {
    id: 'brygada', name: 'Brygada 1918', kind: 'Serif', source: 'Google Fonts · OFL',
    family: 'Brygada 1918', weight: 400, load: { google: 'Brygada 1918:wght@400' },
    note: 'Revival of a 1918 Polish typeface. Warm, with a past.',
  },
  {
    id: 'happy-times', name: 'Happy Times', kind: 'Serif', source: 'Velvetyne · OFL',
    family: 'Happy Times at the IKOB', weight: 400, load: { file: happyTimes },
    note: 'Times New Roman, rethought for a contemporary art museum.',
  },
  {
    id: 'gloock', name: 'Gloock', kind: 'Serif', source: 'Google Fonts · OFL',
    family: 'Gloock', weight: 400, scale: .96, load: { google: 'Gloock' },
    note: 'Bold, high-contrast display serif. The loudest of the set.',
  },
];

/** Stylesheets and @font-face rules that make every candidate available. */
export function fontSources(): { stylesheets: string[]; faces: string } {
  const google = FONTS.flatMap(({ load }) => (load && 'google' in load ? [load.google] : []));
  const fontshare = FONTS.flatMap(({ load }) => (load && 'fontshare' in load ? [load.fontshare] : []));
  const stylesheets = [
    `https://fonts.googleapis.com/css2?${google.map((f) => `family=${f.replace(/ /g, '+')}`).join('&')}&display=swap`,
    `https://api.fontshare.com/v2/css?${fontshare.map((f) => `f[]=${f}`).join('&')}&display=swap`,
  ];
  const faces = FONTS.flatMap(({ family, weight, load }) => (load && 'file' in load
    ? [`@font-face{font-family:"${family}";src:url("${load.file}") format("woff2");font-weight:${weight};font-display:swap}`]
    : [])).join('\n');
  return { stylesheets, faces };
}
