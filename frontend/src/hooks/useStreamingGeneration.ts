import { useState, useCallback, useRef } from 'react'
import type { ComposedDashboardSpec } from '@/types/dashboard'
import type { GenerationProgress } from '@/types/progress'

interface StreamingGenerationResult {
  success: boolean
  session_id: string
  dashboard: ComposedDashboardSpec | null
  error?: string
  generation_time_ms?: number
}

interface UseStreamingGenerationOptions {
  onProgress?: (progress: GenerationProgress) => void
  onComplete?: (result: StreamingGenerationResult) => void
  onError?: (error: string) => void
}

export function useStreamingGeneration(options: UseStreamingGenerationOptions = {}) {
  const { onProgress, onComplete, onError } = options
  const [progress, setProgress] = useState<GenerationProgress>({
    isLoading: false,
    progress: 0,
    stage: '',
    message: '',
  })
  const [result, setResult] = useState<StreamingGenerationResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const generate = useCallback(async (request: {
    user_prompt: string
    connection_name: string
    max_charts?: number
    theme?: string
  }) => {
    // Reset state
    setProgress({ isLoading: true, progress: 0, stage: 'starting', message: 'Starting...' })
    setResult(null)
    setError(null)

    // Create abort controller for cancellation
    abortControllerRef.current = new AbortController()

    try {
      const token = localStorage.getItem('token')

      const response = await fetch('/api/dashboard/generate/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : '',
        },
        body: JSON.stringify(request),
        signal: abortControllerRef.current.signal,
      })

      if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // Parse SSE events from buffer
        const events = buffer.split('\n\n')
        buffer = events.pop() || '' // Keep incomplete event in buffer

        for (const eventStr of events) {
          if (!eventStr.trim()) continue

          const lines = eventStr.split('\n')
          let eventType = ''
          let eventData = ''

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7)
            } else if (line.startsWith('data: ')) {
              eventData = line.slice(6)
            }
          }

          if (!eventType || !eventData) continue

          try {
            const data = JSON.parse(eventData)

            if (eventType === 'progress') {
              const newProgress: GenerationProgress = {
                isLoading: true,
                progress: data.progress,
                stage: data.stage,
                message: data.message,
                details: data.details,
              }
              setProgress(newProgress)
              onProgress?.(newProgress)
            } else if (eventType === 'complete') {
              setProgress(prev => ({ ...prev, isLoading: false, progress: 100 }))
              setResult(data)
              onComplete?.(data)
            } else if (eventType === 'error') {
              const errorMsg = data.error || 'Unknown error'
              setError(errorMsg)
              setProgress(prev => ({ ...prev, isLoading: false }))
              onError?.(errorMsg)
            }
          } catch (parseError) {
            console.error('Failed to parse SSE event:', parseError)
          }
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        console.log('Generation cancelled')
        return
      }
      const errorMsg = err instanceof Error ? err.message : 'Unknown error'
      setError(errorMsg)
      setProgress(prev => ({ ...prev, isLoading: false }))
      onError?.(errorMsg)
    }
  }, [onProgress, onComplete, onError])

  const cancel = useCallback(() => {
    abortControllerRef.current?.abort()
    setProgress(prev => ({ ...prev, isLoading: false }))
  }, [])

  return {
    generate,
    cancel,
    progress,
    result,
    error,
    isLoading: progress.isLoading,
  }
}
