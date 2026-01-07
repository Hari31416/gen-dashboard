export type ColorPalette = 
  | 'default'
  | 'category10'
  | 'category20'
  | 'tableau10'
  | 'tableau20'
  | 'pastel1'
  | 'pastel2'
  | 'set1'
  | 'set2'
  | 'set3'
  | 'accent'
  | 'dark2'
  | 'paired'
  // Color-blind friendly
  | 'viridis'
  | 'plasma'
  | 'inferno'
  | 'magma'
  | 'cividis'
  | 'turbo'
  // Sequential
  | 'blues'
  | 'greens'
  | 'oranges'
  | 'purples'
  | 'reds'
  | 'greys'

export type LegendPosition = 
  | 'right'
  | 'left'
  | 'top'
  | 'bottom'
  | 'top-left'
  | 'top-right'
  | 'bottom-left'
  | 'bottom-right'
  | 'none'

export type ChartTheme = 
  | 'default'
  | 'quartz'
  | 'dark'
  | 'vox'
  | 'fivethirtyeight'
  | 'latimes'
  | 'ggplot2'
  | 'excel'
  | 'googlecharts'
  | 'powerbi'

export interface AxisConfig {
  title?: string
  titleFontSize?: number
  labelFontSize?: number
  labelAngle?: number
  tickCount?: number
  format?: string  // e.g., ",.0f" for numbers, "%Y-%m" for dates
  grid?: boolean
  domain?: boolean
}

export interface ChartCustomization {
  // Colors
  colorPalette?: ColorPalette
  customColors?: string[]  // User-defined array of hex colors
  
  // Titles
  title?: string
  titleFontSize?: number
  subtitle?: string
  
  // Axes
  xAxis?: AxisConfig
  yAxis?: AxisConfig
  
  // Legend
  legendPosition?: LegendPosition
  legendTitle?: string
  
  // Theme
  theme?: ChartTheme
  
  // Background
  backgroundColor?: string
}

export interface ChartCustomizationState {
  [chartId: string]: ChartCustomization
}
