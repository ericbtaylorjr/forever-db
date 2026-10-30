import { useEffect } from 'react';
import { getMeta } from './lib/data.ts';
import { useRoute } from './lib/router.ts';
import { useAsync } from './lib/useAsync.ts';
import { Layout } from './components/Layout.tsx';
import { BuildPage } from './pages/Build.tsx';
import { BuildsPage } from './pages/Builds.tsx';
import { ItemsPage, SpellsPage } from './pages/Browse.tsx';
import { ItemPage, SpellPage } from './pages/Entity.tsx';
import { HomePage } from './pages/Home.tsx';

const TITLES: Record<string, string> = { items: 'Items', spells: 'Spells', builds: 'Builds', item: 'Item', spell: 'Spell', build: 'Build' };

export default function App() {
  const { path } = useRoute();
  const meta = useAsync(getMeta, []);
  const [section, arg] = path;
  const id = Number(arg);

  useEffect(() => {
    document.title = `${TITLES[section] ? `${TITLES[section]}${arg ? ` ${arg}` : ''} · ` : ''}Forever DB`;
    window.scrollTo({ top: 0 });
  }, [section, arg]);

  let page;
  switch (section) {
    case 'items': page = <ItemsPage />; break;
    case 'spells': page = <SpellsPage />; break;
    case 'item': page = Number.isInteger(id) ? <ItemPage id={id} /> : <HomePage />; break;
    case 'spell': page = Number.isInteger(id) ? <SpellPage id={id} /> : <HomePage />; break;
    case 'builds': page = <BuildsPage />; break;
    case 'build': page = Number.isInteger(id) ? <BuildPage index={id} /> : <BuildsPage />; break;
    default: page = <HomePage />;
  }
  const nav = section === 'item' ? 'items' : section === 'spell' ? 'spells' : section === 'build' ? 'builds' : section ?? '';
  return <Layout current={nav} meta={meta.data}>{page}</Layout>;
}
