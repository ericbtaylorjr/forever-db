import { useCallback, useEffect, useState } from 'react';

/**
 * A tiny hash router: #/items?q=sword&quality=3,4 . Hash routing works on GitHub Pages without server rewrites, and
 * every filter lives in the URL so any view can be shared or bookmarked.
 */
export interface Route {
  path: string[];
  params: URLSearchParams;
}

export function parseHash(hash: string): Route {
  const raw = hash.replace(/^#\/?/, '');
  const [path, query = ''] = raw.split('?');
  return { path: path.split('/').filter(Boolean).map(decodeURIComponent), params: new URLSearchParams(query) };
}

export function toHash(path: string[], params?: URLSearchParams | Record<string, string>): string {
  const query = new URLSearchParams(params).toString();
  return `#/${path.map(encodeURIComponent).join('/')}${query ? `?${query}` : ''}`;
}

const current = (): Route => parseHash(window.location.hash);

export function useRoute(): Route {
  const [route, setRoute] = useState(current);
  useEffect(() => {
    const on = () => setRoute(current());
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);
  return route;
}

export function navigate(path: string[], params?: Record<string, string>): void {
  window.location.hash = toHash(path, params);
}

/** Read and update the query parameters of the current page without adding history entries for every keystroke. */
export function useQueryParams(): [URLSearchParams, (patch: Record<string, string | null>) => void] {
  const { params } = useRoute();
  const set = useCallback((patch: Record<string, string | null>) => {
    const next = new URLSearchParams(current().params);
    for (const [k, v] of Object.entries(patch)) {
      if (v === null || v === '') next.delete(k);
      else next.set(k, v);
    }
    const route = current();
    window.history.replaceState(null, '', toHash(route.path, next));
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  }, []);
  return [params, set];
}
