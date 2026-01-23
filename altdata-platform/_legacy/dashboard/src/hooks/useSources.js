import { useQuery } from '@tanstack/react-query'
import { getSources, getHealth } from '../api/client'

export function useSources() {
  return useQuery({
    queryKey: ['sources'],
    queryFn: getSources,
  })
}

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 30000, // Refresh every 30 seconds
  })
}
