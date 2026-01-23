import { useQuery } from '@tanstack/react-query'
import { getEntities, getEntity } from '../api/client'

export function useEntities(search, entityType, page = 1, pageSize = 50) {
  return useQuery({
    queryKey: ['entities', search, entityType, page, pageSize],
    queryFn: () => getEntities(search, entityType, page, pageSize),
  })
}

export function useEntity(entityId) {
  return useQuery({
    queryKey: ['entity', entityId],
    queryFn: () => getEntity(entityId),
    enabled: !!entityId,
  })
}
