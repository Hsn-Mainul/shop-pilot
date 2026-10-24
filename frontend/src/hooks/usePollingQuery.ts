import { useQuery, type QueryKey, type UseQueryOptions } from '@tanstack/react-query'

/**
 * Polls on an interval as a fallback; prefer useRealtime for instant updates.
 * Interval backs off when the tab is hidden.
 */
export function usePollingQuery<T>(
  key: QueryKey,
  fn: () => Promise<T>,
  intervalMs = 8000,
  options?: Omit<UseQueryOptions<T>, 'queryKey' | 'queryFn'>,
) {
  return useQuery({
    queryKey: key,
    queryFn: fn,
    refetchInterval: intervalMs,
    refetchIntervalInBackground: false,
    ...options,
  })
}
