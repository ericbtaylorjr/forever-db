import type { ReactNode } from 'react';
import { config } from '../config.ts';
import { toHash } from '../lib/router.ts';
import type { Meta } from '../lib/data.ts';

const NAV: [string, string][] = [['items', 'Items'], ['spells', 'Spells'], ['builds', 'Builds']];

export function Layout({ current, meta, children }: { current: string; meta: Meta | undefined; children: ReactNode }) {
  const latest = meta?.versions[meta.latest];
  return (
    <div className="flex min-h-full flex-col">
      <header className="border-b border-line bg-panel">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <a href={toHash([])} className="text-lg font-bold text-ink no-underline">
            <span className="text-accent">★</span> {config.siteName}
          </a>
          <nav className="flex gap-1" aria-label="Main">
            {NAV.map(([path, label]) => (
              <a
                key={path}
                href={toHash([path])}
                aria-current={current === path ? 'page' : undefined}
                className={`rounded px-3 py-1.5 no-underline ${current === path ? 'bg-panel2 text-accent' : 'text-mute hover:text-ink'}`}
              >
                {label}
              </a>
            ))}
          </nav>
          {latest && (
            <a href={toHash(['build', String(latest.i)])} className="ml-auto text-xs text-mute" title="The newest version in the data">
              Data as of {latest.label}
            </a>
          )}
        </div>
      </header>
      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-5">{children}</main>
      <footer className="border-t border-line px-4 py-4 text-center text-xs text-mute">
        Built from the WoW Forever game files. Fan-made and unofficial; not affiliated with or endorsed by Blizzard Entertainment. Icons are linked from a public icon host.
      </footer>
    </div>
  );
}
