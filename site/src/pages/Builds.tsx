import { getMeta } from '../lib/data.ts';
import { toHash } from '../lib/router.ts';
import { useAsync } from '../lib/useAsync.ts';
import { Chip, ErrorBox, Loading, Panel } from '../components/ui.tsx';

export function BuildsPage() {
  const meta = useAsync(getMeta, []);
  if (meta.error) return <ErrorBox error={meta.error} />;
  if (!meta.data) return <Loading what="builds" />;
  const versions = [...meta.data.versions].reverse();
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Builds</h1>
      <p className="max-w-3xl text-mute">
        Every version of the game files we have scanned, newest first. A build with “hotfix” in its name includes the changes the server pushed on top of that build. Entries marked as base data
        are the build as shipped, before any hotfix.
      </p>
      <Panel>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase text-mute">
              <tr>
                <th className="pr-4">Version</th>
                <th className="pr-4">Items (+ / ~ / − / 🔓)</th>
                <th className="pr-4">Spells (+ / ~ / − / 🔓)</th>
                <th className="pr-4">Encrypted items</th>
                <th className="pr-4">Encrypted spells</th>
                <th>Locked rows</th>
              </tr>
            </thead>
            <tbody>
              {versions.map((v) => {
                const i = v.counts.items, s = v.counts.spells, first = v.i === 0;
                return (
                  <tr key={v.i} className="border-t border-line/50 align-top">
                    <td className="py-2 pr-4">
                      <a href={toHash(['build', String(v.i)])} className="font-medium">{v.label}</a>
                      <div className="mt-1 flex gap-1">{v.push === 0 ? <Chip title="The build as shipped, without hotfixes">base data</Chip> : <Chip tone="accent">with hotfixes</Chip>}{first && <Chip title="First version tracked: everything counts as added">first tracked</Chip>}</div>
                    </td>
                    <td className="py-2 pr-4 tabular-nums">{first ? '—' : `${i.added} / ${i.changed} / ${i.removed} / `}{!first && <span className="text-enc">{i.discovered}</span>}</td>
                    <td className="py-2 pr-4 tabular-nums">{first ? '—' : `${s.added} / ${s.changed} / ${s.removed} / `}{!first && <span className="text-enc">{s.discovered}</span>}</td>
                    <td className="py-2 pr-4 tabular-nums">{v.discovery ? v.discovery.items.encrypted.toLocaleString() : '—'}</td>
                    <td className="py-2 pr-4 tabular-nums">{v.discovery ? v.discovery.spells.encrypted.toLocaleString() : '—'}</td>
                    <td className="py-2 tabular-nums">
                      {v.lockedRows.toLocaleString()}
                      {v.unlocked.length > 0 && <Chip tone="good" title={v.unlocked.join(', ')}>{v.unlocked.length} key{v.unlocked.length > 1 ? 's' : ''} unlocked</Chip>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
