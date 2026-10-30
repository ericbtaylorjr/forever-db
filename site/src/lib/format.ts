import reference from '../data/reference.json';

export const QUALITY_NAMES = ['Poor', 'Common', 'Uncommon', 'Rare', 'Epic', 'Legendary', 'Artifact', 'Heirloom'];
export const qualityColor = (q: number | null): string => (q === null || q < 0 || q > 7 ? 'var(--mute)' : `var(--q${q})`);

/** ItemSparse.InventoryType */
export const SLOT_NAMES: Record<number, string> = {
  0: 'Not equippable', 1: 'Head', 2: 'Neck', 3: 'Shoulder', 4: 'Shirt', 5: 'Chest', 6: 'Waist', 7: 'Legs', 8: 'Feet', 9: 'Wrist',
  10: 'Hands', 11: 'Finger', 12: 'Trinket', 13: 'One-Hand', 14: 'Shield', 15: 'Ranged', 16: 'Back', 17: 'Two-Hand', 18: 'Bag',
  19: 'Tabard', 20: 'Chest (robe)', 21: 'Main Hand', 22: 'Off Hand', 23: 'Held In Off-Hand', 24: 'Ammo', 25: 'Thrown',
  26: 'Ranged', 27: 'Quiver', 28: 'Relic',
};
export const slotName = (inv: number): string => SLOT_NAMES[inv] ?? `Slot ${inv}`;

export const SCHOOLS: [number, string][] = [
  [1, 'Physical'], [2, 'Holy'], [4, 'Fire'], [8, 'Nature'], [16, 'Frost'], [32, 'Shadow'], [64, 'Arcane'],
];
export function schoolNames(mask: number): string {
  const names = SCHOOLS.filter(([bit]) => mask & bit).map(([, n]) => n);
  return names.length ? names.join(' + ') : '—';
}

export function formatMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '—';
  if (ms === 0) return 'Instant';
  const s = ms / 1000;
  if (s < 60) return `${+s.toFixed(2)} sec`;
  if (s < 3600) return `${+(s / 60).toFixed(2)} min`;
  return `${+(s / 3600).toFixed(2)} hr`;
}

export const money = (copper: number): string => {
  const g = Math.floor(copper / 10000), s = Math.floor((copper % 10000) / 100), c = copper % 100;
  return [g && `${g}g`, (s || g) && `${s}s`, `${c}c`].filter(Boolean).join(' ');
};

type RefKey = keyof typeof reference;
const humanize = (raw: string): string => raw.toLowerCase().replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());

/** Readable name for a numeric game id (effect type, aura type, power type ...), falling back to the number. */
export function refName(kind: RefKey, id: unknown): string {
  const key = String(id);
  const raw = (reference[kind] as Record<string, string>)[key];
  return raw ? humanize(raw) : `${kind} ${key}`;
}

export const statName = (names: Record<string, string>, id: string): string => names[id] ?? `Stat ${id}`;

/** "ItemSparse" etc. are database names; the UI groups fields by the record section they live in. */
/** Compact version label for narrow columns: 70707, or 70707 +hf when it includes hotfixes. */
export const shortVersion = (v: { build: number; push: number }): string => `${v.build}${v.push ? ' +hf' : ''}`;

export const AREA_LABELS: Record<string, string> = {
  discovery: 'Discovery', name: 'Name', description: 'Description', auraDescription: 'Aura description', subtext: 'Subtext',
  computed: 'Computed (stats, tooltip)', effects: 'Effects', related: 'Spell data', sparse: 'Item fields', item: 'Item base fields',
  quality: 'Quality', qualityName: 'Quality', itemLevel: 'Item level', requiredLevel: 'Required level', inventoryType: 'Slot',
  classId: 'Class', subclassId: 'Subclass', className: 'Class', subclassName: 'Subclass', iconFileDataID: 'Icon', icon: 'Icon',
  itemSet: 'Set', bonusTrees: 'Bonus trees', isGear: 'Gear', nameDescription: 'Name tag', schoolMask: 'School',
  castTimeMs: 'Cast time', durationMs: 'Duration', durationPerLevelMs: 'Duration', range: 'Range',
};
export const areaLabel = (area: string): string => AREA_LABELS[area] ?? area;

export function valueText(v: unknown): string {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'string') return v === '' ? '(empty)' : v;
  return JSON.stringify(v);
}

/** "Oct 30, 2026" from a UTC date string (YYYY-MM-DD); the day is not shifted by the viewer's time zone. */
export const formatDate = (iso: string | null | undefined): string =>
  iso ? new Date(`${iso}T00:00:00Z`).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC' }) : '—';

export const dateTitle = (source: string | null | undefined): string | undefined =>
  source ? `Source: ${source}. Dates are UTC.` : 'No public date for this version';
