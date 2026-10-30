import type { ReactNode } from 'react';
import type { ItemIndex, Meta, SpellIndex } from '../lib/data.ts';
import { SCHOOLS, QUALITY_NAMES, SLOT_NAMES, qualityColor, statName } from '../lib/format.ts';
import { viewOf } from '../lib/filters.ts';
import { Checkbox, Field, MultiChips, SelectInput, Segmented, TextInput } from './ui.tsx';

type Set = (patch: Record<string, string | null>) => void;

const VIEW_OPTIONS: [string, string][] = [['all', 'All'], ['discovered', 'Discovered'], ['encrypted', 'Encrypted']];

function VersionFilters({ params, set, meta }: { params: URLSearchParams; set: Set; meta: Meta }) {
  const options = meta.versions.map((v): [string, string] => [String(v.i), v.label]);
  return (
    <>
      <Field label="Changed since">
        <SelectInput value={params.get('since') ?? ''} onChange={(v) => set({ since: v })} options={options} />
      </Field>
      <Field label="Discovered since">
        <SelectInput value={params.get('discSince') ?? ''} onChange={(v) => set({ discSince: v })} options={options} any="Any / never" />
      </Field>
      <Field label="Added since">
        <SelectInput value={params.get('addedSince') ?? ''} onChange={(v) => set({ addedSince: v })} options={options} />
      </Field>
    </>
  );
}

function Shell({ children, more }: { children: ReactNode; more: ReactNode }) {
  return (
    <div className="space-y-3 rounded-lg border border-line bg-panel p-3">
      <div className="flex flex-wrap items-end gap-3">{children}</div>
      <details className="group">
        <summary className="cursor-pointer text-sm text-mute hover:text-ink">More filters</summary>
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">{more}</div>
      </details>
    </div>
  );
}

export function ItemFilterPanel({ params, set, index, meta, versionFilters = true }: { params: URLSearchParams; set: Set; index: ItemIndex; meta: Meta; versionFilters?: boolean }) {
  const g = (k: string) => params.get(k) ?? '';
  const cls = g('cls');
  const classOptions = Object.entries(index.classes).map(([id, n]): [string, string] => [id, n]).sort((a, b) => a[1].localeCompare(b[1]));
  const subOptions = Object.entries(index.subclasses)
    .filter(([k]) => !cls || k.startsWith(`${cls}:`))
    .map(([k, n]): [string, string] => [k, n])
    .sort((a, b) => a[1].localeCompare(b[1]));
  const statOptions = Object.entries(meta.statNames).map(([id]): [string, string] => [id, statName(meta.statNames, id)]).sort((a, b) => a[1].localeCompare(b[1]));
  const slotOptions = Object.entries(SLOT_NAMES).filter(([k]) => k !== '0').map(([k, n]): [string, string] => [k, n]);
  return (
    <Shell
      more={
        <>
          <Field label="Class">
            <SelectInput value={cls} onChange={(v) => set({ cls: v, sub: null })} options={classOptions} />
          </Field>
          <Field label="Subclass">
            <SelectInput value={g('sub')} onChange={(v) => set({ sub: v })} options={subOptions} />
          </Field>
          <Field label="Item level (min)">
            <TextInput type="number" value={g('ilvlMin')} onChange={(v) => set({ ilvlMin: v })} />
          </Field>
          <Field label="Item level (max)">
            <TextInput type="number" value={g('ilvlMax')} onChange={(v) => set({ ilvlMax: v })} />
          </Field>
          <Field label="Required level (min)">
            <TextInput type="number" value={g('lvlMin')} onChange={(v) => set({ lvlMin: v })} />
          </Field>
          <Field label="Required level (max)">
            <TextInput type="number" value={g('lvlMax')} onChange={(v) => set({ lvlMax: v })} />
          </Field>
          <Field label="Has stat">
            <SelectInput value={g('stat')} onChange={(v) => set({ stat: v })} options={statOptions} />
          </Field>
          <Field label="…at least">
            <TextInput type="number" value={g('statMin')} onChange={(v) => set({ statMin: v })} placeholder="1" />
          </Field>
          <Field label="Armor (min)">
            <TextInput type="number" value={g('armorMin')} onChange={(v) => set({ armorMin: v })} />
          </Field>
          <Field label="Weapon DPS (min)">
            <TextInput type="number" value={g('dpsMin')} onChange={(v) => set({ dpsMin: v })} />
          </Field>
          <div className="col-span-2 flex items-end pb-1">
            <Checkbox checked={g('set') === '1'} onChange={(v) => set({ set: v ? '1' : null })} label="Part of an item set" />
          </div>
          {versionFilters && <VersionFilters params={params} set={set} meta={meta} />}
          <div className="col-span-full">
            <Field label="Slot">
              <MultiChips options={slotOptions} value={g('inv')} onChange={(v) => set({ inv: v })} />
            </Field>
          </div>
        </>
      }
    >
      <div className="min-w-56 flex-1">
        <Field label="Search name or id">
          <TextInput value={g('q')} onChange={(v) => set({ q: v })} placeholder="e.g. Thunderfury or 19019" />
        </Field>
      </div>
      <Segmented options={VIEW_OPTIONS} value={viewOf(params)} onChange={(v) => set({ view: v === 'all' ? null : v })} />
      <Checkbox checked={g('gear') === '1'} onChange={(v) => set({ gear: v ? '1' : null })} label="Gear only" />
      <Checkbox checked={g('hideTest') === '1'} onChange={(v) => set({ hideTest: v ? '1' : null })} label="Hide test items" />
      <div className="basis-full">
        <MultiChips
          options={QUALITY_NAMES.map((n, i): [string, string, string] => [String(i), n, qualityColor(i)])}
          value={g('quality')}
          onChange={(v) => set({ quality: v })}
        />
      </div>
    </Shell>
  );
}

export function SpellFilterPanel({ params, set, index, meta, versionFilters = true }: { params: URLSearchParams; set: Set; index: SpellIndex; meta: Meta; versionFilters?: boolean }) {
  const g = (k: string) => params.get(k) ?? '';
  const classTags = index.tags.filter((t) => t.startsWith('class:')).sort();
  const otherTags = index.tags.filter((t) => !t.startsWith('class:')).sort();
  return (
    <Shell
      more={
        <>
          <Field label="Cast time">
            <SelectInput value={g('cast')} onChange={(v) => set({ cast: v })} options={[['instant', 'Instant'], ['cast', 'Has a cast time']]} />
          </Field>
          <Field label="Duration">
            <SelectInput value={g('dur')} onChange={(v) => set({ dur: v })} options={[['has', 'Has a duration'], ['none', 'No duration']]} />
          </Field>
          <Field label="Description text">
            <SelectInput
              value={g('text')}
              onChange={(v) => set({ text: v })}
              options={[['ok', 'Fully rendered'], ['partial', 'Not fully rendered'], ['none', 'No description']]}
            />
          </Field>
          {versionFilters && <VersionFilters params={params} set={set} meta={meta} />}
          <div className="col-span-full">
            <Field label="Where a player gets it (any of)">
              <MultiChips options={[...classTags, ...otherTags].map((t): [string, string] => [t, t.replace(/^class:/, '').replace(/^class-family:/, 'family: ')])} value={g('tag')} onChange={(v) => set({ tag: v })} />
            </Field>
          </div>
        </>
      }
    >
      <div className="min-w-56 flex-1">
        <Field label="Search name or id">
          <TextInput value={g('q')} onChange={(v) => set({ q: v })} placeholder="e.g. Fireball or 133" />
        </Field>
      </div>
      <Segmented options={VIEW_OPTIONS} value={viewOf(params)} onChange={(v) => set({ view: v === 'all' ? null : v })} />
      <Checkbox checked={g('hideTest') === '1'} onChange={(v) => set({ hideTest: v ? '1' : null })} label="Hide old/test spells" />
      <div className="basis-full">
        <Field label="School (any of)">
          <MultiChips options={SCHOOLS.map(([bit, n]): [string, string] => [String(bit), n])} value={g('school')} onChange={(v) => set({ school: v })} />
        </Field>
      </div>
    </Shell>
  );
}
