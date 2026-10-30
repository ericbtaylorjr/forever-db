import { useState, type ReactNode } from 'react';
import { config } from '../config.ts';
import type { VersionMeta } from '../lib/data.ts';

export function LockIcon({ className = 'h-3.5 w-3.5' }: { className?: string }) {
  return (
    <svg viewBox="0 0 16 16" className={className} fill="currentColor" aria-hidden="true">
      <path d="M8 1a3.5 3.5 0 0 0-3.5 3.5V6H4a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1h-.5V4.5A3.5 3.5 0 0 0 8 1Zm2 5H6V4.5a2 2 0 1 1 4 0V6Z" />
    </svg>
  );
}

/** A game icon, linked from the icon host. Encrypted entries keep their icon (the files expose it) with a lock on it. */
export function GameIcon({ name, size = 36, locked = false }: { name: string | undefined; size?: number; locked?: boolean }) {
  const [failed, setFailed] = useState(false);
  const box = { width: size, height: size };
  return (
    <span className="relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded border border-line bg-panel2" style={box}>
      {name && !failed ? (
        <img
          src={config.iconUrl(name, size > 40 ? 'large' : 'medium')}
          alt=""
          width={size}
          height={size}
          loading="lazy"
          onError={() => setFailed(true)}
          className={locked ? 'opacity-50 grayscale' : ''}
        />
      ) : (
        <span className="text-mute">?</span>
      )}
      {locked && (
        <span className="absolute bottom-0 right-0 rounded-tl bg-encbg p-0.5 text-enc">
          <LockIcon className="h-3 w-3" />
        </span>
      )}
    </span>
  );
}

export function Chip({ children, tone = 'plain', title }: { children: ReactNode; tone?: 'plain' | 'enc' | 'good' | 'warn' | 'bad' | 'accent'; title?: string }) {
  const tones: Record<string, string> = {
    plain: 'border-line text-mute',
    enc: 'border-enc/50 bg-encbg text-enc',
    good: 'border-good/50 text-good',
    warn: 'border-warn/50 text-warn',
    bad: 'border-bad/50 text-bad',
    accent: 'border-accent/60 text-accent',
  };
  return (
    <span title={title} className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-xs ${tones[tone]}`}>
      {children}
    </span>
  );
}

export const EncryptedBadge = ({ title = 'Encrypted: the game has not revealed this yet' }: { title?: string }) => (
  <Chip tone="enc" title={title}>
    <LockIcon /> Encrypted
  </Chip>
);

const versionLabel = (versions: VersionMeta[], i: number) => versions[i]?.label ?? `Version ${i}`;

/** "Discovered in Build X", or the honest "already discovered when tracking began" for baseline entities. */
export function DiscoveryBadge({ enc, disc, versions }: { enc: boolean; disc: number; versions: VersionMeta[] }) {
  if (enc) return <EncryptedBadge />;
  if (disc <= 0)
    return (
      <Chip tone="good" title={`Already discovered when tracking began (${versionLabel(versions, 0)}); the real date is earlier`}>
        Discovered (by {versionLabel(versions, 0)})
      </Chip>
    );
  return <Chip tone="good">Discovered in {versionLabel(versions, disc)}</Chip>;
}

export function Panel({ title, children, actions }: { title?: ReactNode; children: ReactNode; actions?: ReactNode }) {
  return (
    <section className="rounded-lg border border-line bg-panel">
      {(title || actions) && (
        <header className="flex items-center justify-between gap-2 border-b border-line px-4 py-2.5">
          <h2 className="text-sm font-semibold">{title}</h2>
          {actions}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export const Loading = ({ what = 'data' }: { what?: string }) => (
  <div className="p-6" role="status" aria-live="polite">
    <div className="skeleton h-4 w-48 rounded" />
    <p className="mt-3 text-mute">Loading {what}…</p>
  </div>
);

export const ErrorBox = ({ error }: { error: Error }) => (
  <div className="m-4 rounded-lg border border-bad/50 bg-panel p-4" role="alert">
    <strong className="text-bad">Could not load data.</strong>
    <p className="mt-1 text-mute">{error.message}. If you are running locally, generate the data first: <code>python3 pipeline/site_data.py</code>.</p>
  </div>
);

/* ------------------------------ filter controls ------------------------------ */

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="flex min-w-0 flex-col gap-1 text-xs text-mute">
      <span>{label}</span>
      {children}
    </label>
  );
}

const inputCls = 'w-full rounded border border-line bg-panel2 px-2 py-1.5 text-sm text-ink placeholder:text-mute';

export const TextInput = ({ value, onChange, placeholder, type = 'text' }: { value: string; onChange: (v: string) => void; placeholder?: string; type?: string }) => (
  <input className={inputCls} type={type} value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} />
);

export const SelectInput = ({ value, onChange, options, any = 'Any' }: { value: string; onChange: (v: string) => void; options: [string, string][]; any?: string }) => (
  <select className={inputCls} value={value} onChange={(e) => onChange(e.target.value)}>
    <option value="">{any}</option>
    {options.map(([v, l]) => (
      <option key={v} value={v}>
        {l}
      </option>
    ))}
  </select>
);

/** A row of toggle chips for picking several values (stored as a comma list). */
export function MultiChips({ options, value, onChange }: { options: [string, string, string?][]; value: string; onChange: (v: string) => void }) {
  const on = new Set(value.split(',').filter(Boolean));
  const toggle = (v: string) => {
    const next = new Set(on);
    if (next.has(v)) next.delete(v);
    else next.add(v);
    onChange([...next].join(','));
  };
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map(([v, l, color]) => (
        <button
          key={v}
          type="button"
          aria-pressed={on.has(v)}
          onClick={() => toggle(v)}
          style={on.has(v) && color ? { borderColor: color, color } : undefined}
          className={`rounded-full border px-2.5 py-1 text-xs ${on.has(v) ? 'border-accent bg-panel2 text-accent' : 'border-line text-mute hover:text-ink'}`}
        >
          {l}
        </button>
      ))}
    </div>
  );
}

export function Segmented({ options, value, onChange }: { options: [string, string][]; value: string; onChange: (v: string) => void }) {
  return (
    <div className="inline-flex overflow-hidden rounded border border-line" role="group">
      {options.map(([v, l]) => (
        <button
          key={v}
          type="button"
          aria-pressed={value === v}
          onClick={() => onChange(v)}
          className={`px-3 py-1.5 text-sm ${value === v ? 'bg-accent text-accentink' : 'bg-panel2 text-mute hover:text-ink'}`}
        >
          {l}
        </button>
      ))}
    </div>
  );
}

export const Checkbox = ({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) => (
  <label className="flex items-center gap-2 text-sm">
    <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="h-4 w-4 accent-[var(--accent)]" />
    {label}
  </label>
);
