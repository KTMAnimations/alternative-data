import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || ''
const API_KEY = import.meta.env.VITE_API_KEY || ''

const client = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
    ...(API_KEY && { 'X-API-Key': API_KEY }),
  },
})

// API functions
export const getHealth = async () => {
  const { data } = await client.get('/health')
  return data
}

export const getFactors = async (category) => {
  const params = category ? { category } : {}
  const { data } = await client.get('/api/v1/factors', { params })
  return data
}

export const getFactorValues = async (factorName, entityId, startDate, endDate) => {
  const params = {
    entity_id: entityId,
    ...(startDate && { start_date: startDate }),
    ...(endDate && { end_date: endDate }),
  }
  const { data } = await client.get(`/api/v1/factors/${factorName}`, { params })
  return data
}

export const getCategories = async () => {
  const { data } = await client.get('/api/v1/categories')
  return data
}

export const getEntities = async (search, entityType, page = 1, pageSize = 50) => {
  const params = {
    page,
    page_size: pageSize,
    ...(search && { search }),
    ...(entityType && { entity_type: entityType }),
  }
  const { data } = await client.get('/api/v1/entities', { params })
  return data
}

export const getEntity = async (entityId) => {
  const { data } = await client.get(`/api/v1/entities/${entityId}`)
  return data
}

export const getSources = async () => {
  const { data } = await client.get('/api/v1/sources')
  return data
}

export default client
