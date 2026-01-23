import { useQuery } from '@tanstack/react-query'
import { getFactors, getFactorValues, getCategories } from '../api/client'

export function useFactors(category) {
  return useQuery({
    queryKey: ['factors', category],
    queryFn: () => getFactors(category),
  })
}

export function useFactorValues(factorName, entityId, startDate, endDate) {
  return useQuery({
    queryKey: ['factorValues', factorName, entityId, startDate, endDate],
    queryFn: () => getFactorValues(factorName, entityId, startDate, endDate),
    enabled: !!factorName && !!entityId,
  })
}

export function useCategories() {
  return useQuery({
    queryKey: ['categories'],
    queryFn: getCategories,
  })
}
