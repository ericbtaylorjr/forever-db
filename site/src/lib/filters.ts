import type { ItemRow, SpellIndex, SpellRow } from './data.ts';

/**
 * Filtering and sorting for the browse tables and the build pages. Every filter is a URL query parameter, so a view
 * is shareable. Functions here are pure and take the whole row list; ~33k rows filter in a few milliseconds.
 */

const num = (p: URLSearchParams, key: string): number | null => {
  const v = p.get(key);
  if (v === null || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
};
const csv = (p: URLSearchParams, key: string): string[] => (p.get(key) ?? '').split(',').filter(Boolean);
const csvNums = (p: URLSearchParams, key: string): number[] => csv(p, key).map(Number).filter(Number.isFinite);

export type View = 'all' | 'discovered' | 'encrypted';
export const viewOf = (p: URLSearchParams): View => (p.get('view') === 'discovered' || p.get('view') === 'encrypted' ? (p.get('view') as View) : 'all');

const matchesText = (name: string, id: number, q: string): boolean => {
  if (!q) return true;
  const needle = q.trim().toLowerCase();
  return String(id) === needle || name.toLowerCase().includes(needle);
};

/** Filters shared by items and spells: text, discovery view, and the version-based "since" filters. */
function common(p: URLSearchParams) {
  const q = p.get('q') ?? '';
  const view = viewOf(p);
  const since = num(p, 'since'), discSince = num(p, 'discSince'), addedSince = num(p, 'addedSince');
  const hideTest = p.get('hideTest') === '1';
  return (r: { id: number; name: string; test: boolean; enc: boolean; changed: number; disc: number; first: number; base: boolean }): boolean => {
    if (hideTest && r.test) return false;
    if (view === 'discovered' && r.enc) return false;
    if (view === 'encrypted' && !r.enc) return false;
    if (since !== null && r.changed < since) return false;
    // Version 0 is the first one tracked: whatever was already there then has no known discovery/add date, so "since" skips it.
    // (An entity that was encrypted at version 0 and revealed later has an exact discovery version > 0.)
    if (discSince !== null && !(r.disc >= Math.max(discSince, 1))) return false;
    if (addedSince !== null && !(r.first >= Math.max(addedSince, 1))) return false;
    return matchesText(r.name, r.id, q);
  };
}

export function itemFilter(p: URLSearchParams): (r: ItemRow) => boolean {
  const base = common(p);
  const gear = p.get('gear') === '1';
  const quality = new Set(csvNums(p, 'quality'));
  const cls = num(p, 'cls');
  const sub = p.get('sub'); // "class:subclass"
  const inv = new Set(csvNums(p, 'inv'));
  const ilvlMin = num(p, 'ilvlMin'), ilvlMax = num(p, 'ilvlMax'), lvlMin = num(p, 'lvlMin'), lvlMax = num(p, 'lvlMax');
  const stat = p.get('stat'), statMin = num(p, 'statMin') ?? 1;
  const armorMin = num(p, 'armorMin'), dpsMin = num(p, 'dpsMin');
  const set = p.get('set') === '1';
  return (r) => {
    if (!base(r)) return false;
    if (gear && !r.gear) return false;
    if (quality.size && (r.quality === null || !quality.has(r.quality))) return false;
    if (cls !== null && r.cls !== cls) return false;
    if (sub && `${r.cls}:${r.sub}` !== sub) return false;
    if (inv.size && !inv.has(r.inv)) return false;
    if (ilvlMin !== null && (r.ilvl ?? -1) < ilvlMin) return false;
    if (ilvlMax !== null && (r.ilvl ?? Infinity) > ilvlMax) return false;
    if (lvlMin !== null && (r.reqLvl ?? -1) < lvlMin) return false;
    if (lvlMax !== null && (r.reqLvl ?? Infinity) > lvlMax) return false;
    if (stat && (r.stats?.[stat] ?? 0) < statMin) return false;
    if (armorMin !== null && r.armor < armorMin) return false;
    if (dpsMin !== null && r.dps < dpsMin) return false;
    if (set && !r.set) return false;
    return true;
  };
}

export function spellFilter(p: URLSearchParams, index: SpellIndex): (r: SpellRow) => boolean {
  const base = common(p);
  const wantTags = new Set(csv(p, 'tag'));
  const tagIds = new Set(index.tags.map((t, i) => (wantTags.has(t) ? i : -1)).filter((i) => i >= 0));
  const school = csvNums(p, 'school').reduce((m, b) => m | b, 0);
  const cast = p.get('cast'); // instant | cast
  const dur = p.get('dur'); // has | none
  const text = p.get('text'); // ok | partial | none
  return (r) => {
    if (!base(r)) return false;
    if (wantTags.size && !r.tags.some((t) => tagIds.has(t))) return false;
    if (school && !(r.school & school)) return false;
    if (cast === 'instant' && r.castMs !== 0) return false;
    if (cast === 'cast' && !(r.castMs && r.castMs > 0)) return false;
    if (dur === 'has' && !(r.durMs && r.durMs > 0)) return false;
    if (dur === 'none' && r.durMs && r.durMs > 0) return false;
    if (text === 'ok' && r.text !== 1) return false;
    if (text === 'partial' && r.text !== 2) return false;
    if (text === 'none' && r.text !== 0) return false;
    return true;
  };
}

export type SortDir = 'asc' | 'desc';
export const sortDir = (p: URLSearchParams, fallback: SortDir): SortDir => (p.get('dir') === 'asc' || p.get('dir') === 'desc' ? (p.get('dir') as SortDir) : fallback);

/** Stable sort by a column. Encrypted rows have no name, so on a name sort they go last either way. */
export function sortRows<T extends { id: number; name: string }>(rows: T[], key: string, dir: SortDir): T[] {
  const sign = dir === 'asc' ? 1 : -1;
  const value = (r: T): number | string => {
    if (key === 'name') return r.name ? r.name.toLowerCase() : '';
    const v = (r as Record<string, unknown>)[key];
    return typeof v === 'number' ? v : typeof v === 'boolean' ? Number(v) : -1;
  };
  return [...rows].sort((a, b) => {
    if (key === 'name' && !a.name !== !b.name) return a.name ? -1 : 1;
    const x = value(a), y = value(b);
    return x < y ? -sign : x > y ? sign : a.id - b.id;
  });
}

/** Number of active filter parameters, for the "clear filters" button. */
export const activeFilters = (p: URLSearchParams): number =>
  [...p.keys()].filter((k) => !['sort', 'dir', 'page'].includes(k) && p.get(k) !== '').length;
