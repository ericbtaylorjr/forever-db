import { useMemo } from 'react';
import { getItems, getMeta, getSpells, type ItemRow, type Meta, type SpellRow } from '../lib/data.ts';
import { activeFilters, itemFilter, sortDir, sortRows, spellFilter } from '../lib/filters.ts';
import { formatMs, qualityColor, QUALITY_NAMES, schoolNames, shortVersion, slotName } from '../lib/format.ts';
import { navigate, useQueryParams } from '../lib/router.ts';
import { useAsync } from '../lib/useAsync.ts';
import { ItemFilterPanel, SpellFilterPanel } from '../components/FilterPanels.tsx';
import { ErrorBox, GameIcon, Loading, Chip } from '../components/ui.tsx';
import { VirtualTable, type Column } from '../components/VirtualTable.tsx';

const versionName = (meta: Meta, i: number) => (i < 0 || !meta.versions[i] ? '—' : shortVersion(meta.versions[i]));

function Toolbar({ shown, total, active, onClear, what }: { shown: number; total: number; active: number; onClear: () => void; what: string }) {
  return (
    <div className="flex items-center justify-between text-sm text-mute" aria-live="polite">
      <span>
        {shown.toLocaleString()} of {total.toLocaleString()} {what}
      </span>
      {active > 0 && (
        <button type="button" onClick={onClear} className="text-link hover:underline">
          Clear {active} filter{active > 1 ? 's' : ''}
        </button>
      )}
    </div>
  );
}

export function ItemsPage() {
  const meta = useAsync(getMeta, []);
  const index = useAsync(getItems, []);
  const [params, set] = useQueryParams();
  const key = params.toString();
  const rows = useMemo(() => {
    if (!index.data) return [];
    return sortRows(index.data.rows.filter(itemFilter(params)), params.get('sort') ?? 'name', sortDir(params, 'asc'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index.data, key]);
  if (meta.error || index.error) return <ErrorBox error={(meta.error || index.error)!} />;
  if (!meta.data || !index.data) return <Loading what="items" />;
  const m = meta.data, idx = index.data;
  const sort = params.get('sort') ?? 'name', dir = sortDir(params, 'asc');

  const columns: Column<ItemRow>[] = [
    {
      key: 'name', label: 'Item', width: 'minmax(140px,3fr)', sortable: true, narrow: true,
      render: (r) => (
        <span className="flex items-center gap-2">
          <GameIcon name={idx.icons[r.icon]} size={28} locked={r.enc} />
          {r.enc ? <span className="italic text-mute">Encrypted item <span className="not-italic">#{r.id}</span></span> : <span style={{ color: qualityColor(r.quality) }}>{r.name}</span>}
        </span>
      ),
    },
    { key: 'quality', label: 'Quality', width: '90px', sortable: true, render: (r) => (r.quality === null ? <span className="text-mute">—</span> : <span style={{ color: qualityColor(r.quality) }}>{QUALITY_NAMES[r.quality]}</span>) },
    { key: 'inv', label: 'Slot', width: '110px', sortable: true, narrow: true, render: (r) => (r.inv ? slotName(r.inv) : <span className="text-mute">—</span>) },
    { key: 'sub', label: 'Type', width: 'minmax(110px,1fr)', render: (r) => idx.subclasses[`${r.cls}:${r.sub}`] ?? idx.classes[String(r.cls)] ?? '—' },
    { key: 'ilvl', label: 'iLvl', width: '56px', sortable: true, align: 'right', narrow: true, render: (r) => r.ilvl ?? '—' },
    { key: 'reqLvl', label: 'Req', width: '48px', sortable: true, align: 'right', render: (r) => r.reqLvl ?? '—' },
    { key: 'armor', label: 'Armor', width: '64px', sortable: true, align: 'right', render: (r) => r.armor || '' },
    { key: 'dps', label: 'DPS', width: '60px', sortable: true, align: 'right', render: (r) => r.dps || '' },
    { key: 'changed', label: 'Changed', width: '96px', sortable: true, align: 'right', render: (r) => (r.base && r.changed <= 0 ? <span className="text-mute">—</span> : versionName(m, r.changed)) },
  ];

  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">Items & gear</h1>
      <ItemFilterPanel params={params} set={set} index={idx} meta={m} />
      <Toolbar shown={rows.length} total={idx.rows.length} active={activeFilters(params)} what="items" onClear={() => navigate(['items'])} />
      <VirtualTable
        rows={rows}
        columns={columns}
        rowKey={(r) => r.id}
        sort={sort}
        dir={dir}
        onSort={(k) => set({ sort: k, dir: sort === k && dir === 'asc' ? 'desc' : 'asc' })}
        onOpen={(r) => navigate(['item', String(r.id)])}
        rowClass={(r) => (r.enc ? 'enc-row' : '')}
      />
    </div>
  );
}

export function SpellsPage() {
  const meta = useAsync(getMeta, []);
  const index = useAsync(getSpells, []);
  const [params, set] = useQueryParams();
  const key = params.toString();
  const rows = useMemo(() => {
    if (!index.data) return [];
    return sortRows(index.data.rows.filter(spellFilter(params, index.data)), params.get('sort') ?? 'name', sortDir(params, 'asc'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index.data, key]);
  if (meta.error || index.error) return <ErrorBox error={(meta.error || index.error)!} />;
  if (!meta.data || !index.data) return <Loading what="spells" />;
  const m = meta.data, idx = index.data;
  const sort = params.get('sort') ?? 'name', dir = sortDir(params, 'asc');

  const columns: Column<SpellRow>[] = [
    {
      key: 'name', label: 'Spell', width: 'minmax(140px,3fr)', sortable: true, narrow: true,
      render: (r) => (
        <span className="flex items-center gap-2">
          <GameIcon name={idx.icons[r.icon]} size={28} locked={r.enc} />
          {r.enc ? <span className="italic text-mute">Encrypted spell <span className="not-italic">#{r.id}</span></span> : r.name}
        </span>
      ),
    },
    { key: 'school', label: 'School', width: '110px', sortable: true, narrow: true, render: (r) => (r.school ? schoolNames(r.school) : <span className="text-mute">—</span>) },
    { key: 'castMs', label: 'Cast', width: '80px', sortable: true, render: (r) => formatMs(r.castMs) },
    { key: 'durMs', label: 'Duration', width: '84px', sortable: true, render: (r) => (r.durMs ? formatMs(r.durMs) : <span className="text-mute">—</span>) },
    {
      key: 'tags', label: 'Where from', width: 'minmax(140px,2fr)',
      render: (r) => (
        <span className="flex gap-1 overflow-hidden">
          {r.tags.slice(0, 3).map((t) => <Chip key={t}>{idx.tags[t].replace(/^class:/, '')}</Chip>)}
        </span>
      ),
    },
    { key: 'text', label: 'Text', width: '56px', sortable: true, render: (r) => (r.text === 1 ? '✓' : r.text === 2 ? <span className="text-warn" title="Description could not be fully rendered">~</span> : <span className="text-mute">—</span>) },
    { key: 'changed', label: 'Changed', width: '96px', sortable: true, align: 'right', render: (r) => (r.base && r.changed <= 0 ? <span className="text-mute">—</span> : versionName(m, r.changed)) },
  ];

  return (
    <div className="space-y-3">
      <h1 className="text-xl font-semibold">Spells</h1>
      <SpellFilterPanel params={params} set={set} index={idx} meta={m} />
      <Toolbar shown={rows.length} total={idx.rows.length} active={activeFilters(params)} what="spells" onClear={() => navigate(['spells'])} />
      <VirtualTable
        rows={rows}
        columns={columns}
        rowKey={(r) => r.id}
        sort={sort}
        dir={dir}
        onSort={(k) => set({ sort: k, dir: sort === k && dir === 'asc' ? 'desc' : 'asc' })}
        onOpen={(r) => navigate(['spell', String(r.id)])}
        rowClass={(r) => (r.enc ? 'enc-row' : '')}
      />
    </div>
  );
}

