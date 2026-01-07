import { useState, useCallback, useEffect } from 'react'
import type { ChartCustomization, ChartCustomizationState } from '@/types/chart-customization'

const STORAGE_KEY_PREFIX = 'chart_customization_'

interface UseChartCustomizationOptions {
  sessionId: string | null
  persist?: boolean
}

export function useChartCustomization(options: UseChartCustomizationOptions) {
  const { sessionId, persist = true } = options
  const storageKey = sessionId ? `${STORAGE_KEY_PREFIX}${sessionId}` : null

  const [customizations, setCustomizations] = useState<ChartCustomizationState>({})

  // Load from localStorage on mount
  useEffect(() => {
    if (!persist || !storageKey) return

    try {
      const stored = localStorage.getItem(storageKey)
      if (stored) {
        setCustomizations(JSON.parse(stored))
      }
    } catch (error) {
      console.warn('Failed to load chart customizations:', error)
    }
  }, [storageKey, persist])

  // Save to localStorage on change
  useEffect(() => {
    if (!persist || !storageKey) return

    try {
      if (Object.keys(customizations).length > 0) {
        localStorage.setItem(storageKey, JSON.stringify(customizations))
      } else {
        localStorage.removeItem(storageKey)
      }
    } catch (error) {
      console.warn('Failed to save chart customizations:', error)
    }
  }, [customizations, storageKey, persist])

  const getCustomization = useCallback((chartId: string): ChartCustomization => {
    return customizations[chartId] || {}
  }, [customizations])

  const setCustomization = useCallback((chartId: string, customization: ChartCustomization) => {
    setCustomizations((prev) => ({
      ...prev,
      [chartId]: customization,
    }))
  }, [])

  const clearCustomization = useCallback((chartId: string) => {
    setCustomizations((prev) => {
      const next = { ...prev }
      delete next[chartId]
      return next
    })
  }, [])

  const clearAll = useCallback(() => {
    setCustomizations({})
    if (storageKey) {
      localStorage.removeItem(storageKey)
    }
  }, [storageKey])

  return {
    customizations,
    getCustomization,
    setCustomization,
    clearCustomization,
    clearAll,
  }
}
