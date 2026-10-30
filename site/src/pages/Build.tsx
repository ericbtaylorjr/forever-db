import { useMemo, useState } from 'react';
import { getBuild, getItems, getMeta, getSpells, type BuildChange, type ItemIndex, type Meta, type SpellIndex, type VersionMeta } from '../lib/data.ts';
import { fieldLabel, valueLabel } from '../lib/describe.ts';
import { itemFilter, spellFilter } from '../lib/filters.ts';
import { areaLabel, qualityColor } from '../lib/format.ts';
import { navigate, toHash, useQueryParams } from '../lib/router.ts';
import { useAsync } from '../lib/useAsync.ts';
import { ItemFilterPanel, SpellFilterPanel } from '../components/FilterPanels.tsx';
import { Chip, EncryptedBadge, ErrorBox, GameIcon, Loading, MultiChips, Panel, Segmented, TextInput, Field } from '../components/ui.tsx';

const EVENT_TYPES: [string, string][] = [['added', 'Added'], ['changed', 'Changed'], ['discovered', 'Discovered'], ['removed', 'Removed']];
const PAGE = 150;

function Stat({ label, value, tone }: { label: string; value: number | string; tone?: string }) {
  return (
    <div className="rounded border border-line bg-panel2 px-3 py-2">
      <div className={`text-lg font-semibold tabular-nums ${tone ?? ''}`}>{typeof value === 'number' ? value.toLocaleString() : value}</div>
      <div className="text-xs text-mute">{label}</div>
    </div>
  );
}

function Summary({ v, prev }: { v: VersionMeta; prev: VersionMeta | undefined }) {
  const first = v.i === 0;
  const cell = (kind: 'items' | 'spells', label: string) => {
    const c = v.counts[kind];
    return (
      <Panel title={label}>
        {first ? (
          <p className="text-sm text-mute">First version tracked, so everything counts as added: {c.added.toLocaleString()} {kind}.</p>
        ) : (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label="Added" value={c.added} tone="text-good" />
            <Stat label="Changed" value={c.changed - c.discovered} tone="text-accent" />
            <Stat label="Discovered" value={c.discovered} tone="text-enc" />
            <Stat label="Removed" value={c.removed} tone="text-bad" />
          </div>
        )}
        {v.discovery && (
          <p className="mt-2 text-xs text-mute">
            {v.discovery[kind].discovered.toLocaleString()} discovered · {v.discovery[kind].encrypted.toLocaleString()} still encrypted
            {prev?.discovery ? ` (was ${prev.discovery[kind].encrypted.toLocaleString()})` : ''}
          </p>
        )}
      </Panel>
    );
  };
  return <div className="grid gap-4 md:grid-cols-2">{cell('items', 'Items')}{cell('spells', 'Spells')}</div>;
}

function LockedPanel({ v, locked, unlocked, newly }: { v: VersionMeta; locked: Record<string, Record<string, number>>; unlocked: string[]; newly: string[] }) {
  const tables = Object.entries(locked).sort((a, b) => Object.values(b[1]).reduce((x, y) => x + y, 0) - Object.values(a[1]).reduce((x, y) => x + y, 0));
  const keys = new Set(tables.flatMap(([, k]) => Object.keys(k)));
  return (
    <Panel title="Encrypted rows behind unknown keys">
      <p className="text-sm">
        <strong>{v.lockedRows.toLocaleString()}</strong> rows in {tables.length} tables are still locked behind {keys.size} key{keys.size === 1 ? '' : 's'}. They cannot be read at all yet, not even to say which
        item or spell they are, so they only show up here as counts. When a key becomes known, its rows appear above as new entries.
      </p>
      {unlocked.length > 0 && <p className="mt-2 text-sm text-good">🔓 Unlocked in this version: {unlocked.join(', ')}</p>}
      {newly.length > 0 && <p className="mt-2 text-sm text-warn">New locked keys in this version: {newly.join(', ')}</p>}
      {tables.length > 0 && (
        <details className="mt-3">
          <summary className="cursor-pointer text-sm text-mute">By table and key</summary>
          <table className="mt-2 text-sm">
            <tbody>
              {tables.map(([table, byKey]) => (
                <tr key={table} className="border-t border-line/50">
                  <td className="py-1 pr-4">{table}</td>
                  <td className="py-1 text-mute">{Object.entries(byKey).map(([k, n]) => `${k.slice(0, 8)}…: ${n}`).join(' · ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </Panel>
  );
}

function ChangeRow({ ch, name, icon, enc, quality, meta }: { ch: BuildChange; name: string; icon: string | undefined; enc: boolean; quality: number | null; meta: Meta }) {
  const kindPath = ch.k === 'i' ? 'item' : 'spell';
  const tone = ch.t === 'added' ? 'good' : ch.t === 'discovered' ? 'enc' : ch.t === 'removed' ? 'bad' : 'accent';
  return (
    <li className="flex gap-3 rounded border border-line bg-panel p-3">
      <GameIcon name={icon} size={36} locked={enc} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <a href={toHash([kindPath, String(ch.id)])} className="font-medium" style={ch.k === 'i' && !enc ? { color: qualityColor(quality) } : undefined}>
            {enc ? <span className="italic text-mute">Encrypted {kindPath} #{ch.id}</span> : name || `${kindPath} #${ch.id}`}
          </a>
          <Chip>{ch.k === 'i' ? 'Item' : 'Spell'}</Chip>
          <Chip tone={tone}>{ch.t}</Chip>
          {ch.t === 'added' && ch.d === 'encrypted' && <EncryptedBadge title="Appeared in this version, still encrypted" />}
          {(ch.a ?? []).filter((a) => a !== 'discovery').map((a) => <Chip key={a}>{areaLabel(a)}</Chip>)}
        </div>
        {ch.c && ch.c.length > 0 && ch.t !== 'discovered' && (
          <ul className="mt-1.5 space-y-0.5 text-sm">
            {ch.c.slice(0, 4).map(([path, a, b]) => (
              <li key={path} className="truncate">
                <span className="text-mute">{fieldLabel(path, meta.statNames)}: </span>
                <span className="text-bad">{valueLabel(path, a, meta.statNames)}</span> → <span className="text-good">{valueLabel(path, b, meta.statNames)}</span>
              </li>
            ))}
            {(ch.n ?? 0) > 4 && <li className="text-xs text-mute">…and {(ch.n ?? 0) - 4} more field{(ch.n ?? 0) - 4 > 1 ? 's' : ''}</li>}
          </ul>
        )}
        {ch.t === 'discovered' && <p className="mt-1 text-sm text-mute">Revealed in this version: its name and details are now readable.</p>}
      </div>
    </li>
  );
}

export function BuildPage({ index }: { index: number }) {
  const meta = useAsync(getMeta, []);
  const items = useAsync(getItems, []);
  const spells = useAsync(getSpells, []);
  const build = useAsync(() => getBuild(index), [index]);
  const [params, set] = useQueryParams();
  const [shown, setShown] = useState(PAGE);
  const error = meta.error || items.error || spells.error || build.error;
  const key = params.toString();

  const view = useMemo(() => {
    if (!items.data || !spells.data || !build.data) return undefined;
    return filterChanges(build.data.changes, params, items.data, spells.data);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items.data, spells.data, build.data, key]);

  if (error) return <ErrorBox error={error} />;
  if (!meta.data || !items.data || !spells.data || !build.data || !view) return <Loading what="build" />;
  const m = meta.data, v = m.versions[index];
  if (!v) return <Panel title="Not found"><p>No build #{index}. <a href={toHash(['builds'])}>See all builds</a>.</p></Panel>;
  const prev = m.versions[index - 1];
  const kind = params.get('k') ?? 'all';
  const areasPresent = [...new Set(build.data.changes.flatMap((c) => c.a ?? []))].sort();
  const changeKinds = (patch: Record<string, string | null>) => { setShown(PAGE); set(patch); };

  return (
    <div className="space-y-4">
      <div>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold">{v.label}</h1>
          {v.push === 0 ? <Chip title="The build as shipped, before any hotfix">base data</Chip> : <Chip tone="accent">includes hotfixes</Chip>}
        </div>
        <p className="text-mute">
          {v.version}
          {v.hotfixes && v.push !== 0 ? ` · ${v.hotfixes}` : ''}
          {prev && <> · compared with <a href={toHash(['build', String(prev.i)])}>{prev.label}</a></>}
        </p>
        <nav className="mt-2 flex gap-3 text-sm">
          {prev && <a href={toHash(['build', String(prev.i)])}>← {prev.label}</a>}
          {m.versions[index + 1] && <a href={toHash(['build', String(index + 1)])}>{m.versions[index + 1].label} →</a>}
        </nav>
      </div>
      <Summary v={v} prev={prev} />
      <LockedPanel v={v} locked={build.data.locked} unlocked={build.data.unlocked} newly={build.data.newlyLocked} />

      <Panel title={`What changed (${view.rows.length.toLocaleString()} of ${build.data.changes.length.toLocaleString()})`}>
        {index === 0 ? (
          <p className="text-mute">This is the first version tracked: nothing is compared against it. Browse the full lists under Items and Spells.</p>
        ) : (
          <div className="space-y-3">
            <div className="flex flex-wrap items-end gap-3">
              <Segmented options={[['all', 'Everything'], ['i', 'Items'], ['s', 'Spells']]} value={kind} onChange={(k) => changeKinds({ k: k === 'all' ? null : k, ...(k === 'all' ? { quality: null, inv: null, cls: null, sub: null, gear: null, stat: null, statMin: null, armorMin: null, dpsMin: null, ilvlMin: null, ilvlMax: null, lvlMin: null, lvlMax: null, set: null, tag: null, school: null, cast: null, dur: null, text: null } : {}) })} />
              <div className="min-w-48 flex-1"><Field label="Event"><MultiChips options={EVENT_TYPES} value={params.get('ev') ?? ''} onChange={(x) => changeKinds({ ev: x })} /></Field></div>
            </div>
            {areasPresent.length > 0 && (
              <Field label="What changed (any of)">
                <MultiChips options={areasPresent.map((a): [string, string] => [a, areaLabel(a)])} value={params.get('area') ?? ''} onChange={(x) => changeKinds({ area: x })} />
              </Field>
            )}
            {kind === 'i' && <ItemFilterPanel params={params} set={changeKinds} index={items.data} meta={m} versionFilters={false} />}
            {kind === 's' && <SpellFilterPanel params={params} set={changeKinds} index={spells.data} meta={m} versionFilters={false} />}
            {kind === 'all' && (
              <div className="flex flex-wrap items-end gap-3">
                <div className="min-w-56 flex-1"><Field label="Search name or id"><TextInput value={params.get('q') ?? ''} onChange={(x) => changeKinds({ q: x })} /></Field></div>
                <Segmented options={[['all', 'All'], ['discovered', 'Discovered'], ['encrypted', 'Encrypted']]} value={params.get('view') ?? 'all'} onChange={(x) => changeKinds({ view: x === 'all' ? null : x })} />
              </div>
            )}
            <ul className="space-y-2">
              {view.rows.slice(0, shown).map((r) => <ChangeRow key={`${r.ch.k}${r.ch.id}${r.ch.t}`} ch={r.ch} name={r.name} icon={r.icon} enc={r.enc} quality={r.quality} meta={m} />)}
            </ul>
            {view.rows.length === 0 && <p className="text-mute">Nothing in this build matches these filters.</p>}
            {view.rows.length > shown && <button type="button" onClick={() => setShown(shown + PAGE)} className="rounded border border-line bg-panel2 px-4 py-2 hover:text-accent">Show {Math.min(PAGE, view.rows.length - shown)} more</button>}
            {Object.keys(Object.fromEntries(params)).length > 0 && <button type="button" onClick={() => navigate(['build', String(index)])} className="ml-3 text-sm text-link hover:underline">Clear filters</button>}
          </div>
        )}
      </Panel>
    </div>
  );
}

interface ChangeView { ch: BuildChange; name: string; icon: string | undefined; enc: boolean; quality: number | null }

function filterChanges(changes: BuildChange[], params: URLSearchParams, items: ItemIndex, spells: SpellIndex): { rows: ChangeView[] } {
  const kind = params.get('k');
  const events = new Set((params.get('ev') ?? '').split(',').filter(Boolean));
  const areas = new Set((params.get('area') ?? '').split(',').filter(Boolean));
  const pi = itemFilter(params), ps = spellFilter(params, spells);
  // Entity filters need the entity's row; a removed entity has none, so it only passes when no entity filter is set.
  const entityFilterActive = [...params.keys()].some((k) => !['k', 'ev', 'area', 'sort', 'dir'].includes(k));
  const rows: ChangeView[] = [];
  for (const ch of changes) {
    if (kind === 'i' && ch.k !== 'i') continue;
    if (kind === 's' && ch.k !== 's') continue;
    if (events.size && !events.has(ch.t)) continue;
    if (areas.size && !(ch.a ?? []).some((a) => areas.has(a))) continue;
    if (ch.k === 'i') {
      const row = items.byId.get(ch.id);
      if (row ? !pi(row) : entityFilterActive) continue;
      rows.push({ ch, name: row?.name || ch.nm || '', icon: row ? items.icons[row.icon] : ch.ic || undefined, enc: row?.enc ?? false, quality: row?.quality ?? null });
    } else {
      const row = spells.byId.get(ch.id);
      if (row ? !ps(row) : entityFilterActive) continue;
      rows.push({ ch, name: row?.name || ch.nm || '', icon: row ? spells.icons[row.icon] : ch.ic || undefined, enc: row?.enc ?? false, quality: null });
    }
  }
  return { rows };
}
