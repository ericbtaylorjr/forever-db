import { refName, schoolNames, slotName, statName, QUALITY_NAMES } from './format.ts';

/** Turn a flattened record path and its value into something a person can read in the history and compare views. */

const TRIGGERS: Record<number, string> = { 0: 'Use', 1: 'Equip', 2: 'Chance on hit', 4: 'Soulstone', 5: 'Use (no delay)', 6: 'Learn' };

export function fieldLabel(path: string, stats: Record<string, string>): string {
  let m = path.match(/^computed\.stats\.(\d+)$/);
  if (m) return `Stat › ${statName(stats, m[1])}`;
  m = path.match(/^computed\.weapon\.(\w+)$/);
  if (m) return `Weapon › ${m[1]}`;
  m = path.match(/^computed\.tooltip\.(\w+)$/);
  if (m) return `Rendered text › ${m[1]}`;
  m = path.match(/^related\.(\w+)\[(\d+)\]\.(\w+)$/);
  if (m) return m[1] === 'SpellEffect' ? `Effect ${Number(m[2]) + 1} › ${m[3]}` : `${m[1]} #${Number(m[2]) + 1} › ${m[3]}`;
  m = path.match(/^effects\[(\d+)\]\.(\w+)$/);
  if (m) return `Item effect ${Number(m[1]) + 1} › ${m[2]}`;
  m = path.match(/^(sparse|item)\.(\w+)$/);
  if (m) return m[2];
  return path;
}

export function valueLabel(path: string, value: unknown, _stats: Record<string, string>): string {
  if (value === null || value === undefined) return '—';
  if (/\.Effect$/.test(path) && typeof value === 'number') return `${refName('effect', value)} (${value})`;
  if (/\.EffectAura$/.test(path) && typeof value === 'number') return `${refName('aura', value)} (${value})`;
  if (/\.PowerType$/.test(path) && typeof value === 'number') return `${refName('power', value)} (${value})`;
  if (/\.(EffectMechanic|Mechanic)$/.test(path) && typeof value === 'number') return `${refName('mechanic', value)} (${value})`;
  if (/^(related\.SpellMisc\[\d+\]\.)?SchoolMask$|^schoolMask$/.test(path.replace(/^related\.SpellMisc\[\d+\]\./, '')) && typeof value === 'number') return `${schoolNames(value)} (${value})`;
  if (path === 'inventoryType' && typeof value === 'number') return slotName(value);
  if (path === 'quality' && typeof value === 'number') return QUALITY_NAMES[value] ?? String(value);
  if (/^effects\[\d+\]\.TriggerType$/.test(path) && typeof value === 'number') return TRIGGERS[value] ?? `Trigger ${value}`;
  if (/^(castTimeMs|durationMs|durationPerLevelMs)$/.test(path) && typeof value === 'number') return `${value} ms`;
  if (typeof value === 'string') return value === '' ? '(empty)' : value;
  if (/^computed\.stats\./.test(path) && typeof value === 'number') return `+${value}`;
  return JSON.stringify(value);
}

export const itemTrigger = (t: number | undefined): string => TRIGGERS[t ?? 0] ?? `Trigger ${t}`;
