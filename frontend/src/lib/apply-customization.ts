import type { ChartCustomization, ChartTheme } from '@/types/chart-customization'
import { getPaletteColors } from './color-palettes'

/**
 * Apply customization to a Vega-Lite spec without mutating the original.
 */
export function applyCustomization(
  spec: Record<string, unknown>,
  customization: ChartCustomization
): Record<string, unknown> {
  console.log('applyCustomization called with:', customization);
  const newSpec = JSON.parse(JSON.stringify(spec)) as Record<string, unknown>

  // Apply title customization
  if (customization.title !== undefined) {
    newSpec.title = customization.title || undefined
  }

  // Build config object
  const config: Record<string, unknown> = (newSpec.config as Record<string, unknown>) || {}

  // Apply color palette
  if (customization.colorPalette || customization.customColors) {
    const colors = customization.customColors || getPaletteColors(customization.colorPalette!)
    config.range = {
      ...(config.range as object || {}),
      category: colors,
    }
  }

  // Apply axis customization
  if (customization.xAxis) {
    const encoding = newSpec.encoding as Record<string, unknown> || {}
    const xEncoding = encoding.x as Record<string, unknown> || {}

    if (customization.xAxis.title !== undefined) {
      xEncoding.title = customization.xAxis.title || null
    }

    encoding.x = {
      ...xEncoding,
      axis: {
        ...(xEncoding.axis as object || {}),
        labelAngle: customization.xAxis.labelAngle,
        labelFontSize: customization.xAxis.labelFontSize,
        titleFontSize: customization.xAxis.titleFontSize,
        grid: customization.xAxis.grid,
        domain: customization.xAxis.domain,
        tickCount: customization.xAxis.tickCount,
        format: customization.xAxis.format,
      },
    }

    newSpec.encoding = encoding
  }

  if (customization.yAxis) {
    const encoding = newSpec.encoding as Record<string, unknown> || {}
    const yEncoding = encoding.y as Record<string, unknown> || {}

    if (customization.yAxis.title !== undefined) {
      yEncoding.title = customization.yAxis.title || null
    }

    encoding.y = {
      ...yEncoding,
      axis: {
        ...(yEncoding.axis as object || {}),
        labelAngle: customization.yAxis.labelAngle,
        labelFontSize: customization.yAxis.labelFontSize,
        titleFontSize: customization.yAxis.titleFontSize,
        grid: customization.yAxis.grid,
        domain: customization.yAxis.domain,
        tickCount: customization.yAxis.tickCount,
        format: customization.yAxis.format,
      },
    }

    newSpec.encoding = encoding
  }

  // Apply legend customization
  if (customization.legendPosition !== undefined) {
    const encoding = newSpec.encoding as Record<string, unknown> || {}

    // Apply to color encoding (most common legend trigger)
    const colorEncoding = encoding.color as Record<string, unknown>
    if (colorEncoding) {
      if (customization.legendPosition === 'none') {
        colorEncoding.legend = null
      } else {
        const legendOrient = getLegendOrient(customization.legendPosition)
        colorEncoding.legend = {
          ...(colorEncoding.legend as object || {}),
          orient: legendOrient,
          title: customization.legendTitle || undefined,
        }
      }
      encoding.color = colorEncoding
      newSpec.encoding = encoding
    }
  }

  // Apply background color
  if (customization.backgroundColor) {
    config.background = customization.backgroundColor
  }

  // Apply title font size to config
  if (customization.titleFontSize) {
    config.title = {
      ...(config.title as object || {}),
      fontSize: customization.titleFontSize,
    }
  }

  // Apply mark color for single-color charts (charts without color encoding)
  if (customization.markColor) {
    const mark = newSpec.mark
    if (typeof mark === 'string') {
      // Convert simple mark to object form
      newSpec.mark = { type: mark, color: customization.markColor }
    } else if (mark && typeof mark === 'object') {
      // Add color to existing mark object
      (mark as Record<string, unknown>).color = customization.markColor
    }
  }

  newSpec.config = config

  return newSpec
}

function getLegendOrient(position: string): string {
  const mapping: Record<string, string> = {
    'right': 'right',
    'left': 'left',
    'top': 'top',
    'bottom': 'bottom',
    'top-left': 'top-left',
    'top-right': 'top-right',
    'bottom-left': 'bottom-left',
    'bottom-right': 'bottom-right',
  }
  return mapping[position] || 'right'
}

/**
 * Get vega-embed theme name from our theme setting.
 */
export function getVegaTheme(theme?: ChartTheme): string {
  if (!theme || theme === 'default') return 'quartz'
  return theme
}
