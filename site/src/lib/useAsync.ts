import { useEffect, useState } from 'react';

export interface Async<T> {
  data: T | undefined;
  error: Error | undefined;
  loading: boolean;
}

/** Run an async loader when `deps` change; ignores a stale result if the inputs changed meanwhile. */
export function useAsync<T>(load: () => Promise<T>, deps: unknown[]): Async<T> {
  const [state, setState] = useState<Async<T>>({ data: undefined, error: undefined, loading: true });
  useEffect(() => {
    let live = true;
    setState((s) => ({ ...s, loading: true, error: undefined }));
    load().then(
      (data) => live && setState({ data, error: undefined, loading: false }),
      (error: Error) => live && setState({ data: undefined, error, loading: false }),
    );
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}
