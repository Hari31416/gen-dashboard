export interface ProgressEvent {
  stage: string
  progress: number
  message: string
  details?: {
    charts_planned?: number | null
    queries_executed?: number | null
    successful_queries?: number | null
    specs_created?: number | null
  }
}

export interface GenerationProgress {
  isLoading: boolean
  progress: number
  stage: string
  message: string
  details?: ProgressEvent['details']
}
