import { useMemo, useState } from 'react';
import type { EntityRecord, HistoryEvent, Meta } from '../lib/data.ts';
import { fieldLabel, valueLabel } from '../lib/describe.ts';
import { areaLabel } from '../lib/format.ts';
import { diffFlat, existsAt, flatAt, timeline, areaOf } from '../lib/history.ts';
import { toHash } from '../lib/router.ts';
import { Chip, EncryptedBadge, Field, Panel, SelectInput } from './ui.tsx';

/** Fields that only restate another one (className follows classId): left out of the compare so each change shows once. */
const DERIVED = new Set(['className', 'subclassName', 'qualityName', 'isGear']);

const TYPE_LABEL: Record<HistoryEvent['t'], { text: string; tone: 'good' | 'accent' | 'enc' | 'bad' }> = {
  added: { text: 'Added', tone: 'good' },
  changed: { text: 'Changed', tone: 'accent' },
  discovered: { text: 'Discovered', tone: 'enc' },
  removed: { text: 'Removed', tone: 'bad' },
};

export function HistoryPanel({ rec, meta }: { rec: EntityRecord; meta: Meta }) {
  const events = timeline(rec.h);
  const first = meta.versions[rec.f];
  return (
    <Panel title="History">
      {events.length === 0 ? (
        <p className="text-mute">
          No changes recorded since tracking began ({meta.versions[0].label}). {rec.b ? 'It was already in the game files then, so any earlier history is unknown.' : ''}
        </p>
      ) : (
        <ol className="space-y-3">
          {events.map((ev) => (
            <li key={`${ev.v}-${ev.t}`} className="rounded border border-line p-3">
              <div className="flex flex-wrap items-center gap-2">
                <a className="font-medium" href={toHash(['build', String(ev.v)])}>{meta.versions[ev.v].label}</a>
                <Chip tone={TYPE_LABEL[ev.t].tone}>{TYPE_LABEL[ev.t].text}</Chip>
                {ev.t === 'added' && ev.d === 'encrypted' && <EncryptedBadge title="Appeared in this version, still encrypted" />}
                {(ev.a ?? []).map((a) => <Chip key={a}>{areaLabel(a)}</Chip>)}
              </div>
              {ev.c && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-sm text-mute">{Object.keys(ev.c).length} field{Object.keys(ev.c).length > 1 ? 's' : ''} changed</summary>
                  <table className="mt-2 w-full text-sm">
                    <tbody>
                      {Object.entries(ev.c).slice(0, 60).map(([path, [a, b]]) => (
                        <tr key={path} className="border-t border-line/50 align-top">
                          <td className="py-1 pr-3 text-mute">{fieldLabel(path, meta.statNames)}</td>
                          <td className="py-1 pr-3 break-words text-bad">{valueLabel(path, a, meta.statNames)}</td>
                          <td className="py-1 break-words text-good">{valueLabel(path, b, meta.statNames)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </details>
              )}
            </li>
          ))}
        </ol>
      )}
      <p className="mt-3 text-xs text-mute">
        First seen in {first?.label}
        {rec.b ? ' (the first version tracked; it may be older)' : ''}.
      </p>
    </Panel>
  );
}

export function ComparePanel({ rec, meta }: { rec: EntityRecord; meta: Meta }) {
  const available = useMemo(() => meta.versions.filter((v) => existsAt(rec, v.i)), [rec, meta]);
  const latest = available[available.length - 1]?.i ?? meta.latest;
  const lastChange = rec.h.length ? Math.max(...rec.h.map((e) => e.v)) : rec.f;
  const [b, setB] = useState(String(latest));
  const [a, setA] = useState(String(Math.max(rec.f, Math.min(lastChange - 1, latest))));
  const [all, setAll] = useState(false);
  const options = available.map((v): [string, string] => [String(v.i), v.label]);

  const rows = useMemo(() => {
    const fa = flatAt(rec, Number(a)), fb = flatAt(rec, Number(b));
    if (!fa || !fb) return [];
    const changed = diffFlat(fa, fb).filter((d) => !DERIVED.has(d.path));
    if (!all) return changed;
    const seen = new Set(changed.map((c) => c.path));
    const same = [...fb.keys()].filter((p) => !seen.has(p) && !DERIVED.has(p)).map((path) => ({ path, a: fa.get(path) ?? null, b: fb.get(path) ?? null, area: areaOf(path) }));
    return [...changed, ...same].sort((x, y) => (x.path < y.path ? -1 : 1));
  }, [rec, a, b, all]);

  const groups = useMemo(() => {
    const out = new Map<string, typeof rows>();
    for (const r of rows) out.set(r.area, [...(out.get(r.area) ?? []), r]);
    return [...out.entries()];
  }, [rows]);
  const changedCount = rows.filter((r) => JSON.stringify(r.a) !== JSON.stringify(r.b)).length;

  return (
    <Panel
      title="Compare versions"
      actions={
        <label className="flex items-center gap-2 text-xs text-mute">
          <input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} /> Show unchanged fields
        </label>
      }
    >
      {available.length < 2 ? (
        <p className="text-mute">Only one version of this entry exists so far, so there is nothing to compare yet.</p>
      ) : (
        <>
          <div className="mb-3 grid grid-cols-2 gap-3 sm:max-w-xl">
            <Field label="From">
              <SelectInput value={a} onChange={setA} options={options} any="—" />
            </Field>
            <Field label="To">
              <SelectInput value={b} onChange={setB} options={options} any="—" />
            </Field>
          </div>
          {changedCount === 0 && !all ? (
            <p className="text-mute">No differences between these versions.</p>
          ) : (
            <div className="space-y-4">
              {groups.map(([area, list]) => (
                <div key={area}>
                  <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-mute">{areaLabel(area)}</h3>
                  <table className="w-full table-fixed text-sm">
                    <colgroup><col className="w-1/3" /><col className="w-1/3" /><col className="w-1/3" /></colgroup>
                    <tbody>
                      {list.map((r) => {
                        const diff = JSON.stringify(r.a) !== JSON.stringify(r.b);
                        return (
                          <tr key={r.path} className="border-t border-line/50 align-top">
                            <td className="py-1 pr-3 text-mute">{fieldLabel(r.path, meta.statNames)}</td>
                            <td className={`py-1 pr-3 break-words ${diff ? 'bg-bad/10 text-bad' : 'text-mute'}`}>{valueLabel(r.path, r.a, meta.statNames)}</td>
                            <td className={`py-1 break-words ${diff ? 'bg-good/10 text-good' : 'text-mute'}`}>{valueLabel(r.path, r.b, meta.statNames)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </Panel>
  );
}
