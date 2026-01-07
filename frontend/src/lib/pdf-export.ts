import { jsPDF } from 'jspdf'
import * as vega from 'vega'
import * as vegaLite from 'vega-lite'

interface ExportOptions {
  title?: string
  description?: string
  filename?: string
}

interface ChartSpec {
  spec: Record<string, unknown>
  chartId: string
  title?: string
  layout: { x: number; y: number; w: number; h: number }
}

interface DashboardExportData {
  title?: string
  description?: string
  charts: ChartSpec[]
  gridCols: number
  rowHeight: number
}

/**
 * Render a Vega-Lite spec to a canvas with embedded data
 */
async function renderChartToCanvas(
  spec: Record<string, unknown>,
  width: number,
  height: number
): Promise<HTMLCanvasElement> {
  // Clone and prepare the spec
  const chartSpec = JSON.parse(JSON.stringify(spec))
  delete chartSpec.chart_id

  // Set explicit dimensions
  chartSpec.width = width - 40 // Account for padding
  chartSpec.height = height - 60 // Account for title and padding
  chartSpec.autosize = { type: 'fit', contains: 'padding' }

  // If spec has URL data, we need to fetch it
  if (chartSpec.data?.url) {
    try {
      const token = localStorage.getItem('token')
      const response = await fetch(chartSpec.data.url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (response.ok) {
        const data = await response.json()
        chartSpec.data = { values: data }
      }
    } catch (e) {
      console.warn('Failed to fetch chart data:', e)
    }
  }

  // Compile Vega-Lite to Vega
  const vegaSpec = vegaLite.compile(chartSpec as vegaLite.TopLevelSpec).spec

  // Create a Vega view and render to canvas
  const view = new vega.View(vega.parse(vegaSpec), {
    renderer: 'none',
    background: '#ffffff',
  })

  await view.runAsync()
  const canvas = await view.toCanvas(3) // Scale factor 3 for better quality
  view.finalize()

  return canvas as unknown as HTMLCanvasElement
}

/**
 * Create a text card canvas (for metric/KPI cards)
 */
function createTextCardCanvas(
  title: string,
  value: string,
  width: number,
  height: number
): HTMLCanvasElement {
  const canvas = document.createElement('canvas')
  const scale = 3 // Higher scale for shaper text
  canvas.width = width * scale
  canvas.height = height * scale

  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Failed to get canvas context')

  ctx.scale(scale, scale)

  // Background
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, width, height)

  // Border
  ctx.strokeStyle = '#e5e7eb'
  ctx.lineWidth = 1
  ctx.strokeRect(0.5, 0.5, width - 1, height - 1)

  // Title
  ctx.fillStyle = '#6b7280'
  ctx.font = '16px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
  ctx.textAlign = 'center'
  ctx.fillText(title, width / 2, 40) // More top margin

  // Value
  ctx.fillStyle = '#111827'
  ctx.font = 'bold 36px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
  ctx.fillText(value, width / 2, height / 2 + 15)

  return canvas
}

/**
 * Export dashboard to PDF using Vega's native rendering
 * This bypasses html2canvas and renders each chart directly
 */
export async function exportDashboardToPDF(
  _containerElement: HTMLElement,
  options: ExportOptions = {},
  dashboardData?: DashboardExportData
): Promise<void> {
  const { filename = 'dashboard', title, description } = options

  if (!dashboardData) {
    console.error('Dashboard data is required for PDF export')
    throw new Error('Dashboard data is required for PDF export')
  }

  try {
    const { charts, gridCols, rowHeight } = dashboardData

    // Define page dimensions (A4 landscape in mm)
    const pageWidthMm = 297
    const pageHeightMm = 210
    const marginMm = 15 // Increased margin
    // Dynamic header height: 50mm if description exists, 30mm if just title, 15mm if neither
    const headerHeightMm = title ? (description ? 50 : 30) : 15

    // Calculate available space for charts
    const contentWidthMm = pageWidthMm - 2 * marginMm
    const contentHeightMm = pageHeightMm - headerHeightMm - marginMm

    // Calculate cell dimensions in mm
    const cellWidthMm = contentWidthMm / gridCols
    const cellHeightMm = rowHeight * 0.264583 // px to mm

    // Create PDF
    const pdf = new jsPDF({
      orientation: 'landscape',
      unit: 'mm',
      format: 'a4',
    })

    // Add header
    if (title) {
      pdf.setFontSize(22) // Larger title
      pdf.setTextColor(88, 28, 135) // Purple color
      pdf.text(title, marginMm, marginMm + 10)

      if (description) {
        pdf.setFontSize(12) // Larger description
        pdf.setTextColor(107, 114, 128) // Gray color
        pdf.text(description, marginMm, marginMm + 20)
      }
    }

    // Calculate total grid height needed
    let maxY = 0
    for (const chart of charts) {
      const bottomY = chart.layout.y + chart.layout.h
      if (bottomY > maxY) maxY = bottomY
    }
    const totalHeightMm = maxY * cellHeightMm

    // Check if we need multiple pages
    const availableHeightPerPage = contentHeightMm
    const totalPages = Math.ceil(totalHeightMm / availableHeightPerPage)

    console.log('PDF Export - Grid info:', {
      gridCols,
      rowHeight,
      chartCount: charts.length,
      maxY,
      totalHeightMm,
      totalPages,
    })

    // Render and place each chart
    for (let pageNum = 0; pageNum < totalPages; pageNum++) {
      if (pageNum > 0) {
        pdf.addPage()
      }

      const pageOffsetY = pageNum * availableHeightPerPage

      for (const chart of charts) {
        const { spec, layout, title: chartTitle } = chart

        // Calculate position in mm with even spacing (centering the card)
        const gap = 8 // 8mm total gap means 4mm padding on each side
        const xMm = marginMm + layout.x * cellWidthMm + (gap / 2)
        const yMm = headerHeightMm + layout.y * cellHeightMm - pageOffsetY + (gap / 2)
        const wMm = layout.w * cellWidthMm - gap
        const hMm = layout.h * cellHeightMm - gap

        // Skip if chart is on a different page
        if (yMm + hMm < 0 || yMm > contentHeightMm + headerHeightMm) {
          continue
        }

        // Convert mm to pixels for rendering (assuming 96 DPI for canvas)
        const wPx = Math.round(wMm * 3.78) // mm to px at 96 DPI
        const hPx = Math.round(hMm * 3.78)

        try {
          let canvas: HTMLCanvasElement

          // Check if this is a text/metric card (no mark type or text mark)
          const isTextCard =
            !spec.mark ||
            spec.mark === 'text' ||
            (typeof spec.mark === 'object' && (spec.mark as Record<string, unknown>).type === 'text')


          // Cast spec to any to access data.values which might not exist on Record<string, unknown>
          const chartSpec = spec as any

          if (isTextCard && chartSpec.data?.values) {
            // For text/metric cards, create a simple text canvas
            const values = chartSpec.data.values as Record<string, unknown>[]
            const value = values[0] ? String(Object.values(values[0])[0]) : ''
            canvas = createTextCardCanvas(chartTitle || '', value, wPx, hPx)
          } else {
            // Render the Vega chart to canvas
            canvas = await renderChartToCanvas(spec, wPx, hPx)
          }

          // Add the canvas image to PDF
          const imgData = canvas.toDataURL('image/png')
          pdf.addImage(imgData, 'PNG', xMm, Math.max(yMm, headerHeightMm), wMm, hMm)

          // Redundant title removed to prevent overlap with Vega-rendered titles
        } catch (e) {
          console.error(`Failed to render chart ${chart.chartId}:`, e)
          // Draw placeholder for failed chart
          pdf.setDrawColor(200)
          pdf.setFillColor(245, 245, 245)
          pdf.rect(xMm, Math.max(yMm, headerHeightMm), wMm, hMm, 'FD')
          pdf.setFontSize(10)
          pdf.setTextColor(150)
          pdf.text('Chart failed to render', xMm + wMm / 2, yMm + hMm / 2, { align: 'center' })
        }
      }
    }

    // Add footer with generation date
    pdf.setFontSize(8)
    pdf.setTextColor(150)
    pdf.text(`Generated on ${new Date().toLocaleString()}`, pageWidthMm - marginMm, pageHeightMm - 5, {
      align: 'right',
    })

    // Save
    pdf.save(`${filename.replace(/[^a-z0-9]/gi, '_')}.pdf`)
  } catch (error) {
    console.error('Failed to generate PDF:', error)
    throw error
  }
}

/**
 * Legacy export function for backward compatibility
 * Falls back to basic screenshot if no dashboard data provided
 */
export async function exportDashboardToPDFLegacy(
  containerElement: HTMLElement,
  options: ExportOptions = {}
): Promise<void> {
  const { filename = 'dashboard' } = options

  // Dynamic import of html2canvas for legacy mode
  const html2canvas = (await import('html2canvas')).default

  try {
    await new Promise((resolve) => setTimeout(resolve, 1500))

    const originalScrollPos = window.scrollY
    window.scrollTo(0, 0)

    const canvas = await html2canvas(containerElement, {
      scale: 2,
      useCORS: true,
      logging: false,
      imageTimeout: 0,
      backgroundColor: window.getComputedStyle(document.body).backgroundColor || '#ffffff',
    })

    window.scrollTo(0, originalScrollPos)

    const imgData = canvas.toDataURL('image/jpeg', 0.85)

    const pxToMm = 0.264583
    const imgWidthMm = canvas.width * pxToMm
    const imgHeightMm = canvas.height * pxToMm

    const pdf = new jsPDF({
      orientation: imgWidthMm > imgHeightMm ? 'landscape' : 'portrait',
      unit: 'mm',
      format: [imgWidthMm, imgHeightMm],
    })

    pdf.addImage(imgData, 'JPEG', 0, 0, imgWidthMm, imgHeightMm, undefined, 'FAST')

    pdf.save(`${filename.replace(/[^a-z0-9]/gi, '_')}.pdf`)
  } catch (error) {
    console.error('Failed to generate PDF:', error)
    throw error
  }
}
