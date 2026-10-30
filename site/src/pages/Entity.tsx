import type { ReactNode } from 'react';
import { getEntity, getItems, getMeta, getSpells, type EntityRecord, type ItemIndex, type Meta, type SpellIndex } from '../lib/data.ts';
import { itemTrigger } from '../lib/describe.ts';
import { formatMs, money, QUALITY_NAMES, qualityColor, refName, schoolNames, slotName, statName } from '../lib/format.ts';
import { toHash } from '../lib/router.ts';
import { useAsync } from '../lib/useAsync.ts';
import { ComparePanel, HistoryPanel } from '../components/History.tsx';
import { Chip, DiscoveryBadge, ErrorBox, GameIcon, Loading, Panel } from '../components/ui.tsx';

const BINDING: Record<number, string> = { 1: 'Binds when picked up', 2: 'Binds when equipped', 3: 'Binds when used', 4: 'Quest item' };

function Facts({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1.5 text-sm">
      {rows.filter(([, v]) => v !== null && v !== undefined && v !== '').map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-mute">{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function EncryptedNotice({ kind, known }: { kind: 'item' | 'spell'; known: string }) {
  return (
    <div className="rounded-lg border border-enc/50 bg-encbg p-4 text-sm" role="note">
      <strong className="text-enc">This {kind} is encrypted.</strong> The game has not revealed its {kind === 'item' ? 'name or stats' : 'name or effects'} yet, so neither has the data.
      {' '}It will show up as <em>discovered</em> in a later build once it is found in game. {known}
    </div>
  );
}

/** Spell description with `{icon:ID}` markers (inline spell icons) and line breaks. */
function Tooltip({ text, spells }: { text: string; spells: SpellIndex }) {
  const parts = text.split(/(\{icon:\d+\})/);
  return (
    <p className="whitespace-pre-wrap leading-relaxed">
      {parts.map((part, i) => {
        const m = part.match(/^\{icon:(\d+)\}$/);
        if (!m) return <span key={i}>{part.replace(/\r\n/g, '\n')}</span>;
        const row = spells.byId.get(Number(m[1]));
        return <span key={i} className="mx-1 inline-block align-middle"><GameIcon name={row ? spells.icons[row.icon] : undefined} size={20} /></span>;
      })}
    </p>
  );
}

function Header({ icon, locked, title, color, subtitle, badges }: { icon: string | undefined; locked: boolean; title: ReactNode; color?: string; subtitle?: ReactNode; badges: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-4">
      <GameIcon name={icon} size={56} locked={locked} />
      <div className="min-w-0 flex-1">
        <h1 className="text-2xl font-semibold" style={color ? { color } : undefined}>{title}</h1>
        {subtitle && <div className="text-mute">{subtitle}</div>}
      </div>
      <div className="flex flex-wrap items-center gap-2">{badges}</div>
    </div>
  );
}

function useEntityPage(kind: 'items' | 'spells', id: number) {
  const meta = useAsync(getMeta, []);
  const items = useAsync(getItems, []);
  const spells = useAsync(getSpells, []);
  const row = kind === 'items' ? items.data?.byId.get(id) : spells.data?.byId.get(id);
  const rec = useAsync(() => (row ? getEntity(kind, id, row.shard) : Promise.resolve(undefined)), [kind, id, row?.shard]);
  const error = meta.error || items.error || spells.error || rec.error;
  const ready = meta.data && items.data && spells.data;
  return { meta: meta.data, items: items.data, spells: spells.data, row, rec: rec.data, error, ready, recLoading: rec.loading };
}

export function ItemPage({ id }: { id: number }) {
  const s = useEntityPage('items', id);
  if (s.error) return <ErrorBox error={s.error} />;
  if (!s.ready || s.recLoading) return <Loading what="item" />;
  if (!s.row || !s.rec) return <NotFound what="item" id={id} />;
  return <ItemView id={id} meta={s.meta!} items={s.items!} spells={s.spells!} rec={s.rec} />;
}

function ItemView({ id, meta, items, spells, rec }: { id: number; meta: Meta; items: ItemIndex; spells: SpellIndex; rec: EntityRecord }) {
  const d = rec.d, row = items.byId.get(id)!;
  const enc = d.discovery === 'encrypted';
  const c = d.computed ?? {};
  const type = [d.className, d.subclassName].filter(Boolean).join(' › ');
  const stats = Object.entries<number>(c.stats ?? {});
  const known = `What the files do expose: ${[type, d.inventoryType ? `slot ${slotName(d.inventoryType)}` : null, d.itemSet ? `part of the set "${d.itemSet.name}"` : null].filter(Boolean).join(', ') || 'only that it exists'}.`;
  return (
    <div className="space-y-4">
      <Header
        icon={items.icons[row.icon]}
        locked={enc}
        title={enc ? <span className="italic text-mute">Encrypted item</span> : d.name}
        color={enc ? undefined : qualityColor(d.quality)}
        subtitle={<>Item #{id}{d.nameDescription ? ` · ${d.nameDescription}` : ''}</>}
        badges={<><DiscoveryBadge enc={enc} disc={rec.x} versions={meta.versions} />{d.isGear && <Chip>Gear</Chip>}</>}
      />
      {enc && <EncryptedNotice kind="item" known={known} />}
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Details">
          <Facts
            rows={[
              ['Quality', d.quality !== null && d.quality !== undefined ? <span style={{ color: qualityColor(d.quality) }}>{QUALITY_NAMES[d.quality]}</span> : null],
              ['Type', type || null],
              ['Slot', d.inventoryType ? slotName(d.inventoryType) : null],
              ['Item level', d.itemLevel],
              ['Required level', d.requiredLevel || null],
              ['Binding', BINDING[d.sparse?.Bonding] ?? null],
              ['Armor', c.armor],
              ['Weapon', c.weapon ? `${c.weapon.min} – ${c.weapon.max} damage, speed ${c.weapon.speed.toFixed(2)} (${(((c.weapon.min + c.weapon.max) / 2) / c.weapon.speed).toFixed(1)} dps)` : null],
              ['Set', d.itemSet?.name],
              ['Sells for', d.sparse?.SellPrice ? money(d.sparse.SellPrice) : null],
              ['Flavor text', d.description ? `“${d.description}”` : null],
            ]}
          />
          {enc && <p className="mt-2 text-sm text-mute">Name, quality, level and stats appear here once the item is discovered.</p>}
        </Panel>
        <div className="space-y-4">
          {stats.length > 0 && (
            <Panel title="Stats">
              <ul className="space-y-1 text-sm">
                {stats.map(([sid, value]) => <li key={sid}><span className="text-good">+{value}</span> {statName(meta.statNames, sid)}</li>)}
              </ul>
              <p className="mt-2 text-xs text-mute">Computed from the game's stat budgets. Stats granted by an effect are listed under Effects instead.</p>
            </Panel>
          )}
          {d.effects?.length > 0 && (
            <Panel title="Effects">
              <ul className="space-y-2 text-sm">
                {d.effects.map((e: Record<string, any>, i: number) => {
                  const spell = spells.byId.get(e.SpellID);
                  return (
                    <li key={i} className="flex flex-wrap items-center gap-2">
                      <Chip>{itemTrigger(e.TriggerType)}</Chip>
                      <a href={toHash(['spell', String(e.SpellID)])}>{spell?.name || `Spell #${e.SpellID}`}</a>
                      {spell?.enc && <Chip tone="enc">Encrypted</Chip>}
                      {e.Charges ? <span className="text-mute">{Math.abs(e.Charges)} charges</span> : null}
                      {e.CoolDownMSec > 0 ? <span className="text-mute">{formatMs(e.CoolDownMSec)} cooldown</span> : null}
                    </li>
                  );
                })}
              </ul>
            </Panel>
          )}
        </div>
      </div>
      <HistoryPanel rec={rec} meta={meta} />
      <ComparePanel rec={rec} meta={meta} />
      <details className="text-sm text-mute"><summary className="cursor-pointer">Raw data</summary><pre className="mt-2 max-h-96 overflow-auto rounded bg-panel2 p-3 text-xs">{JSON.stringify(rec.d, null, 1)}</pre></details>
    </div>
  );
}

export function SpellPage({ id }: { id: number }) {
  const s = useEntityPage('spells', id);
  if (s.error) return <ErrorBox error={s.error} />;
  if (!s.ready || s.recLoading) return <Loading what="spell" />;
  if (!s.row || !s.rec) return <NotFound what="spell" id={id} />;
  return <SpellView id={id} meta={s.meta!} items={s.items!} spells={s.spells!} rec={s.rec} />;
}

function SpellView({ id, meta, items, spells, rec }: { id: number; meta: Meta; items: ItemIndex; spells: SpellIndex; rec: EntityRecord }) {
  const d = rec.d, row = spells.byId.get(id)!;
  const enc = d.discovery === 'encrypted';
  const rel: Record<string, Record<string, any>[]> = d.related ?? {};
  const effects = [...(rel.SpellEffect ?? [])].sort((a, b) => (a.EffectIndex ?? 0) - (b.EffectIndex ?? 0));
  const power = rel.SpellPower?.[0], cooldown = rel.SpellCooldowns?.[0], levels = rel.SpellLevels?.[0];
  const tags: string[] = d.computed?.availability ?? [];
  const tip = d.computed?.tooltip ?? {};
  const known = tags.length ? `What the files do expose: ${tags.map((t) => t.replace(/^class:/, '')).join(', ')}.` : '';
  const showText = (key: 'description' | 'auraDescription') => {
    const raw: string = d[key];
    if (!raw) return null;
    if (!raw.includes('$')) return <Tooltip text={raw} spells={spells} />;
    const rendered = tip[key];
    return rendered ? <Tooltip text={rendered} spells={spells} /> : (
      <div>
        <p className="font-mono text-sm text-mute">{raw}</p>
        <p className="mt-1 text-xs text-warn">Shown as the game's raw template: it refers to things this site cannot compute exactly ({(d.computed?.tooltipBlockedBy ?? []).join(', ')}).</p>
      </div>
    );
  };
  return (
    <div className="space-y-4">
      <Header
        icon={spells.icons[row.icon]}
        locked={enc}
        title={enc ? <span className="italic text-mute">Encrypted spell</span> : d.name}
        subtitle={<>Spell #{id}{d.subtext ? ` · ${d.subtext}` : ''}</>}
        badges={<DiscoveryBadge enc={enc} disc={rec.x} versions={meta.versions} />}
      />
      {enc && <EncryptedNotice kind="spell" known={known} />}
      {tags.length > 0 && <div className="flex flex-wrap gap-1.5">{tags.map((t) => <Chip key={t} tone={t === 'marked-obsolete' ? 'warn' : 'plain'}>{t}</Chip>)}</div>}
      <div className="grid gap-4 lg:grid-cols-2">
        {!enc && <Panel title="Details">
          <Facts
            rows={[
              ['School', d.schoolMask ? schoolNames(d.schoolMask) : null],
              ['Cast time', d.castTimeMs !== undefined && d.castTimeMs !== null ? formatMs(d.castTimeMs) : null],
              ['Duration', d.durationMs ? `${formatMs(d.durationMs)}${d.durationPerLevelMs ? ` (+${d.durationPerLevelMs} ms per level)` : ''}` : null],
              ['Range', d.range?.name],
              ['Cost', power ? `${power.ManaCost ?? power.PowerCostPct ?? 0}${power.PowerCostPct ? '%' : ''} ${refName('power', power.PowerType ?? 0)}` : null],
              ['Cooldown', cooldown?.RecoveryTime || cooldown?.CategoryRecoveryTime ? formatMs(cooldown.RecoveryTime || cooldown.CategoryRecoveryTime) : null],
              ['Spell level', levels?.BaseLevel || null],
            ]}
          />
        </Panel>}
        <Panel title="Text">
          {enc ? <p className="text-mute">Not available until the spell is discovered.</p> : (
            <div className="space-y-3">
              {showText('description')}
              {showText('auraDescription') && <div><h3 className="mb-1 text-xs uppercase tracking-wide text-mute">While active</h3>{showText('auraDescription')}</div>}
              {!d.description && !d.auraDescription && <p className="text-mute">This spell has no description.</p>}
              <p className="text-xs text-mute">Numbers are the spell's own values at level 60, without spell power or attack power.</p>
            </div>
          )}
        </Panel>
      </div>
      {effects.length > 0 && (
        <Panel title="Effects">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase text-mute">
                <tr><th className="pr-3">#</th><th className="pr-3">Effect</th><th className="pr-3">Aura</th><th className="pr-3">Base points</th><th className="pr-3">Per level</th><th className="pr-3">Period</th><th>Triggers</th></tr>
              </thead>
              <tbody>
                {effects.map((e, i) => (
                  <tr key={i} className="border-t border-line/50">
                    <td className="py-1 pr-3 text-mute">{(e.EffectIndex ?? i) + 1}</td>
                    <td className="py-1 pr-3">{refName('effect', e.Effect ?? 0)}</td>
                    <td className="py-1 pr-3">{e.EffectAura ? refName('aura', e.EffectAura) : '—'}</td>
                    <td className="py-1 pr-3 tabular-nums">{e.EffectBasePointsF ?? 0}</td>
                    <td className="py-1 pr-3 tabular-nums">{e.EffectRealPointsPerLevel ?? 0}</td>
                    <td className="py-1 pr-3">{e.EffectAuraPeriod ? formatMs(e.EffectAuraPeriod) : '—'}</td>
                    <td className="py-1">{e.EffectTriggerSpell ? <a href={toHash(['spell', String(e.EffectTriggerSpell)])}>{spells.byId.get(e.EffectTriggerSpell)?.name || `Spell #${e.EffectTriggerSpell}`}</a> : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
      {(rec.un ?? 0) > 0 && (
        <Panel title={`Used by ${rec.un} item${rec.un! > 1 ? 's' : ''}`}>
          <ul className="grid gap-1 text-sm sm:grid-cols-2 lg:grid-cols-3">
            {(rec.u ?? []).slice(0, 60).map((iid) => {
              const it = items.byId.get(iid);
              return <li key={iid}><a href={toHash(['item', String(iid)])} style={{ color: it?.enc ? undefined : qualityColor(it?.quality ?? null) }}>{it?.enc ? `Encrypted item #${iid}` : it?.name || `Item #${iid}`}</a></li>;
            })}
          </ul>
          {rec.un! > 60 && <p className="mt-2 text-xs text-mute">…and {rec.un! - 60} more.</p>}
        </Panel>
      )}
      <HistoryPanel rec={rec} meta={meta} />
      <ComparePanel rec={rec} meta={meta} />
      <details className="text-sm text-mute"><summary className="cursor-pointer">Raw data</summary><pre className="mt-2 max-h-96 overflow-auto rounded bg-panel2 p-3 text-xs">{JSON.stringify(rec.d, null, 1)}</pre></details>
    </div>
  );
}

function NotFound({ what, id }: { what: string; id: number }) {
  return (
    <Panel title="Not found">
      <p>No {what} with id {id} in the current data. It may have been removed from the game files, or the id may be wrong.</p>
      <p className="mt-2"><a href={toHash([what === 'item' ? 'items' : 'spells'])}>Browse all {what}s</a></p>
    </Panel>
  );
}
