import { useEffect, useRef, useState, type ReactNode } from 'react';
import { config } from '../config.ts';

export interface Column<T> {
  key: string;
  label: string;
  width: string; // CSS grid track, e.g. "minmax(220px,2fr)" or "80px"
  render: (row: T) => ReactNode;
  sortable?: boolean;
  align?: 'right';
  /** shown on phones too; columns without it are hidden below 720px */
  narrow?: boolean;
}

/**
 * A fixed-row-height virtual list: only the rows in view (plus a margin) are rendered, so tens of thousands of rows
 * scroll smoothly. Sorting is controlled by the parent (the sort key lives in the URL).
 */
/** True on phone-width screens, where the browse tables drop their secondary columns. */
export function useNarrow(): boolean {
  const query = '(max-width: 720px)';
  const [narrow, setNarrow] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const on = () => setNarrow(mq.matches);
    mq.addEventListener('change', on);
    return () => mq.removeEventListener('change', on);
  }, []);
  return narrow;
}

export function VirtualTable<T>({
  rows, columns: all, rowKey, sort, dir, onSort, onOpen, rowClass, height = 'calc(100vh - 260px)',
}: {
  rows: T[];
  columns: Column<T>[];
  rowKey: (row: T) => string | number;
  sort: string;
  dir: 'asc' | 'desc';
  onSort: (key: string) => void;
  onOpen: (row: T) => void;
  rowClass?: (row: T) => string;
  height?: string;
}) {
  const narrow = useNarrow();
  const columns = narrow ? all.filter((c) => c.narrow) : all;
  const box = useRef<HTMLDivElement>(null);
  const [top, setTop] = useState(0);
  const [view, setView] = useState(600);
  const rh = config.rowHeight;

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const measure = () => setView(el.clientHeight);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  useEffect(() => {
    box.current?.scrollTo({ top: 0 });
    setTop(0);
  }, [rows]);

  const first = Math.max(0, Math.floor(top / rh) - 8);
  const last = Math.min(rows.length, Math.ceil((top + view) / rh) + 8);
  const grid = columns.map((c) => c.width).join(' ');

  return (
    <div className="overflow-hidden rounded-lg border border-line bg-panel" role="table" aria-rowcount={rows.length}>
      <div className="grid items-center gap-3 border-b border-line bg-panel2 px-3 py-2 text-xs uppercase tracking-wide text-mute" style={{ gridTemplateColumns: grid }} role="row">
        {columns.map((c) => (
          <div key={c.key} role="columnheader" className={c.align === 'right' ? 'text-right' : ''}>
            {c.sortable ? (
              <button type="button" onClick={() => onSort(c.key)} className="uppercase hover:text-ink" aria-sort={sort === c.key ? (dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                {c.label} {sort === c.key ? (dir === 'asc' ? '▲' : '▼') : ''}
              </button>
            ) : (
              c.label
            )}
          </div>
        ))}
      </div>
      <div ref={box} style={{ height, overflowY: 'auto' }} onScroll={(e) => setTop(e.currentTarget.scrollTop)}>
        {rows.length === 0 ? (
          <p className="p-8 text-center text-mute">Nothing matches these filters.</p>
        ) : (
          <div style={{ height: rows.length * rh, position: 'relative' }}>
            {rows.slice(first, last).map((row, i) => (
              <div
                key={rowKey(row)}
                role="row"
                tabIndex={0}
                onClick={() => onOpen(row)}
                onKeyDown={(e) => (e.key === 'Enter' ? onOpen(row) : undefined)}
                className={`absolute left-0 right-0 grid cursor-pointer items-center gap-3 border-b border-line/60 px-3 hover:bg-panel2 ${rowClass?.(row) ?? ''}`}
                style={{ top: (first + i) * rh, height: rh, gridTemplateColumns: grid }}
              >
                {columns.map((c) => (
                  <div key={c.key} role="cell" className={`min-w-0 truncate ${c.align === 'right' ? 'text-right tabular-nums' : ''}`}>
                    {c.render(row)}
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
