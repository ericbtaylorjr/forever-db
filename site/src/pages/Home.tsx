import { getItems, getMeta, getSpells } from '../lib/data.ts';
import { qualityColor, shortVersion } from '../lib/format.ts';
import { toHash } from '../lib/router.ts';
import { useAsync } from '../lib/useAsync.ts';
import { Chip, ErrorBox, GameIcon, Loading, Panel } from '../components/ui.tsx';

export function HomePage() {
  const meta = useAsync(getMeta, []);
  const items = useAsync(getItems, []);
  const spells = useAsync(getSpells, []);
  const error = meta.error || items.error || spells.error;
  if (error) return <ErrorBox error={error} />;
  if (!meta.data || !items.data || !spells.data) return <Loading />;
  const m = meta.data, latest = m.versions[m.latest];
  const total = (k: 'items' | 'spells') => latest.discovery?.[k];
  const recentFrom = Math.max(1, m.latest - 2);
  const newItems = items.data.rows.filter((r) => !r.enc && r.disc >= recentFrom).sort((a, b) => b.disc - a.disc || a.id - b.id);
  const newSpells = spells.data.rows.filter((r) => !r.enc && r.disc >= recentFrom).sort((a, b) => b.disc - a.disc || a.id - b.id);

  const card = (label: string, kind: 'items' | 'spells', path: string) => {
    const t = total(kind);
    return (
      <a href={toHash([path])} className="block rounded-lg border border-line bg-panel p-4 no-underline hover:border-accent">
        <div className="text-sm text-mute">{label}</div>
        <div className="text-3xl font-semibold text-ink tabular-nums">{t ? (t.discovered + t.encrypted).toLocaleString() : '—'}</div>
        {t && <div className="mt-1 text-sm text-mute"><span className="text-good">{t.discovered.toLocaleString()} discovered</span> · <span className="text-enc">{t.encrypted.toLocaleString()} encrypted</span></div>}
      </a>
    );
  };

  return (
    <div className="space-y-5">
      <section>
        <h1 className="text-2xl font-semibold">Every item, spell and piece of gear in WoW Forever</h1>
        <p className="mt-1 max-w-3xl text-mute">
          Read straight from the game files, rebuilt on every update. See what each build changed, compare any two versions of an entry, and tell at a glance what the game has
          <em> discovered</em> and what is still <em>encrypted</em>.
        </p>
      </section>
      <div className="grid gap-4 sm:grid-cols-3">
        {card('Items', 'items', 'items')}
        {card('Spells', 'spells', 'spells')}
        <a href={toHash(['build', String(m.latest)])} className="block rounded-lg border border-line bg-panel p-4 no-underline hover:border-accent">
          <div className="text-sm text-mute">Latest version</div>
          <div className="text-xl font-semibold text-ink">{latest.label}</div>
          <div className="mt-1 text-sm text-mute">{latest.lockedRows.toLocaleString()} rows still locked behind unknown keys</div>
        </a>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title={`Recently discovered items (since ${m.versions[recentFrom].label})`} actions={<a href={toHash(['items'], { view: 'discovered', discSince: String(recentFrom), sort: 'changed', dir: 'desc' })} className="text-xs">See all</a>}>
          {newItems.length === 0 ? <p className="text-mute">No items were revealed in the last few versions.</p> : (
            <ul className="space-y-1.5 text-sm">
              {newItems.slice(0, 12).map((r) => (
                <li key={r.id} className="flex items-center gap-2">
                  <GameIcon name={items.data!.icons[r.icon]} size={24} />
                  <a href={toHash(['item', String(r.id)])} style={{ color: qualityColor(r.quality) }}>{r.name}</a>
                  <Chip tone="enc">{shortVersion(m.versions[r.disc])}</Chip>
                </li>
              ))}
              {newItems.length > 12 && <li className="text-xs text-mute">…and {newItems.length - 12} more</li>}
            </ul>
          )}
        </Panel>
        <Panel title={`Recently discovered spells (since ${m.versions[recentFrom].label})`} actions={<a href={toHash(['spells'], { view: 'discovered', discSince: String(recentFrom), sort: 'changed', dir: 'desc' })} className="text-xs">See all</a>}>
          {newSpells.length === 0 ? <p className="text-mute">No spells were revealed in the last few versions.</p> : (
            <ul className="space-y-1.5 text-sm">
              {newSpells.slice(0, 12).map((r) => (
                <li key={r.id} className="flex items-center gap-2">
                  <GameIcon name={spells.data!.icons[r.icon]} size={24} />
                  <a href={toHash(['spell', String(r.id)])}>{r.name}</a>
                  <Chip tone="enc">{shortVersion(m.versions[r.disc])}</Chip>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
      <Panel title="How to read this site">
        <ul className="list-disc space-y-1 pl-5 text-sm text-mute">
          <li><Chip tone="enc">Encrypted</Chip> entries exist in the game files but the game has not revealed their name or details yet. They get a lock; what the files do show (slot, type, icon, class) is kept.</li>
          <li><strong>Discovered</strong> means the details are readable. “Discovered in Build N” is when this site first saw them readable.</li>
          <li>History starts at {m.versions[0].label}. Anything marked “by {m.versions[0].label}” may be older than we can tell.</li>
          <li>Numbers in spell text are the spell's own values at level 60, without your spell power or attack power. Text we cannot compute exactly is shown as the raw template, never guessed.</li>
        </ul>
      </Panel>
    </div>
  );
}
