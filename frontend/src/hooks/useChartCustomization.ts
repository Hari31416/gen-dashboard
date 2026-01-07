import { useState, useCallback, useEffect, useRef } from 'react'
import type { ChartCustomization, ChartCustomizationState } from '@/types/chart-customization'
import { dashboardApi } from '@/api/client'

const STORAGE_KEY_PREFIX = 'chart_customization_'

interface UseChartCustomizationOptions {
  sessionId: string | null
  persist?: boolean
  initialCustomizations?: ChartCustomizationState
}

export function useChartCustomization(options: UseChartCustomizationOptions) {
  const { sessionId, persist = true, initialCustomizations } = options
  const storageKey = sessionId ? `${STORAGE_KEY_PREFIX}${sessionId}` : null

  const [customizations, setCustomizations] = useState<ChartCustomizationState>(
    initialCustomizations || {}
  )
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const isInitializedRef = useRef(false)

  // Load from localStorage on mount (fallback), or use initialCustomizations from backend
  useEffect(() => {
    if (!persist || !storageKey) return

    // If we have initial customizations from backend, use those
    if (initialCustomizations && Object.keys(initialCustomizations).length > 0) {
      setCustomizations(initialCustomizations)
      isInitializedRef.current = true
      return
    }

    // Otherwise try to load from localStorage
    try {
      const stored = localStorage.getItem(storageKey)
      if (stored) {
        setCustomizations(JSON.parse(stored))
      }
      isInitializedRef.current = true
    } catch (error) {
      console.warn('Failed to load chart customizations:', error)
      isInitializedRef.current = true
    }
  }, [storageKey, persist, initialCustomizations])

  // Save to localStorage and backend on change (debounced)
  useEffect(() => {
    if (!persist || !storageKey || !sessionId) return
    // Skip saving on initial load
    if (!isInitializedRef.current) return

    try {
      // Always update localStorage immediately
      if (Object.keys(customizations).length > 0) {
        localStorage.setItem(storageKey, JSON.stringify(customizations))
      } else {
        localStorage.removeItem(storageKey)
      }

      // Debounce backend save - only save if there are customizations
      // Skip saving empty {} to avoid overwriting stored customizations
      if (Object.keys(customizations).length > 0) {
        if (saveTimeoutRef.current) {
          clearTimeout(saveTimeoutRef.current)
        }
        saveTimeoutRef.current = setTimeout(async () => {
          try {
            await dashboardApi.updateChartCustomizations(sessionId, customizations)
          } catch (error) {
            console.warn('Failed to save customizations to backend:', error)
          }
        }, 1000) // 1 second debounce
      }

    } catch (error) {
      console.warn('Failed to save chart customizations:', error)
    }

    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current)
      }
    }
  }, [customizations, storageKey, persist, sessionId])

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
