# Implementation Plan: Frontend Enhancements

This document provides a step-by-step implementation guide for frontend UI/UX enhancements.

---

## Overview

**Goal**: Implement 6 frontend enhancements (all can be done in frontend only):

1. **Dark/Light Theme Toggle** - Switch between themes
2. **Keyboard Shortcuts** - Quick actions via keyboard
3. **Copy Chart SQL** - Copy SQL query for any chart
4. **Empty State Illustrations** - Visual feedback for empty states
5. **Download Data as CSV** - Export chart data
6. **PDF Export** - Export dashboard as PDF

---

## Current State

- **Dark theme CSS already exists** in `index.css` (lines 34-59)
- **HTML export already exists** in `ChartRenderer.tsx`
- Uses **shadcn/ui** components with Radix UI primitives
- No theme provider context exists yet
- Lucide React icons available

---

## Implementation Steps

### Step 1: Dark/Light Theme Toggle

#### 1.1 Create Theme Context

**File**: `frontend/src/contexts/ThemeContext.tsx` [NEW]

```tsx
import React, { createContext, useContext, useEffect, useState } from 'react'

type Theme = 'light' | 'dark' | 'system'

interface ThemeContextType {
  theme: Theme
  setTheme: (theme: Theme) => void
  resolvedTheme: 'light' | 'dark'
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof window !== 'undefined') {
      return (localStorage.getItem('theme') as Theme) || 'system'
    }
    return 'system'
  })

  const [resolvedTheme, setResolvedTheme] = useState<'light' | 'dark'>('light')

  useEffect(() => {
    const root = window.document.documentElement

    const applyTheme = () => {
      let effectiveTheme: 'light' | 'dark'
      
      if (theme === 'system') {
        effectiveTheme = window.matchMedia('(prefers-color-scheme: dark)').matches
          ? 'dark'
          : 'light'
      } else {
        effectiveTheme = theme
      }

      root.classList.remove('light', 'dark')
      root.classList.add(effectiveTheme)
      setResolvedTheme(effectiveTheme)
    }

    applyTheme()
    localStorage.setItem('theme', theme)

    // Listen for system theme changes
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    const handleChange = () => {
      if (theme === 'system') applyTheme()
    }
    mediaQuery.addEventListener('change', handleChange)

    return () => mediaQuery.removeEventListener('change', handleChange)
  }, [theme])

  return (
    <ThemeContext.Provider value={{ theme, setTheme, resolvedTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return context
}
```

#### 1.2 Create Theme Toggle Component

**File**: `frontend/src/components/ui/theme-toggle.tsx` [NEW]

```tsx
import { Moon, Sun, Monitor } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { useTheme } from '@/contexts/ThemeContext'

export function ThemeToggle() {
  const { theme, setTheme, resolvedTheme } = useTheme()

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon" className="h-9 w-9">
          {resolvedTheme === 'dark' ? (
            <Moon className="h-4 w-4" />
          ) : (
            <Sun className="h-4 w-4" />
          )}
          <span className="sr-only">Toggle theme</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-36 p-2" align="end">
        <div className="flex flex-col gap-1">
          <Button
            variant={theme === 'light' ? 'secondary' : 'ghost'}
            size="sm"
            className="justify-start gap-2"
            onClick={() => setTheme('light')}
          >
            <Sun className="h-4 w-4" />
            Light
          </Button>
          <Button
            variant={theme === 'dark' ? 'secondary' : 'ghost'}
            size="sm"
            className="justify-start gap-2"
            onClick={() => setTheme('dark')}
          >
            <Moon className="h-4 w-4" />
            Dark
          </Button>
          <Button
            variant={theme === 'system' ? 'secondary' : 'ghost'}
            size="sm"
            className="justify-start gap-2"
            onClick={() => setTheme('system')}
          >
            <Monitor className="h-4 w-4" />
            System
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}
```

#### 1.3 Update App.tsx

**File**: `frontend/src/App.tsx` [MODIFY]

Add ThemeProvider wrapper:

```tsx
import { ThemeProvider } from '@/contexts/ThemeContext'

function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          {/* ... existing content ... */}
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  )
}
```

#### 1.4 Add Theme Toggle to Header

**File**: `frontend/src/components/dashboard/DashboardView.tsx` [MODIFY]

Add the theme toggle to the header area (find the header section and add):

```tsx
import { ThemeToggle } from '@/components/ui/theme-toggle'

// In the header/toolbar area (around line 285-290), add:
<ThemeToggle />
```

#### 1.5 Update ChartRenderer for Dark Mode

**File**: `frontend/src/components/dashboard/ChartRenderer.tsx` [MODIFY]

Update vega-embed theme based on resolved theme. In `IndividualChart` component:

```tsx
import { useTheme } from '@/contexts/ThemeContext'

// Inside IndividualChart component:
const { resolvedTheme } = useTheme()

// Update the embed call (around line 84):
embed(containerRef.current, cleanSpec, {
  mode: 'vega-lite',
  actions: { export: true, source: false, compiled: false, editor: false },
  theme: resolvedTheme === 'dark' ? 'dark' : 'quartz',  // Changed
  renderer: 'canvas',
  ...loaderOptions,
})
```

---

### Step 2: Keyboard Shortcuts

#### 2.1 Create Keyboard Shortcuts Hook

**File**: `frontend/src/hooks/useKeyboardShortcuts.ts` [NEW]

```tsx
import { useEffect, useCallback } from 'react'

interface ShortcutConfig {
  key: string
  ctrl?: boolean
  meta?: boolean  // Cmd on Mac
  shift?: boolean
  alt?: boolean
  handler: () => void
  description: string
}

export function useKeyboardShortcuts(shortcuts: ShortcutConfig[]) {
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    // Don't trigger shortcuts when typing in inputs/textareas
    if (
      e.target instanceof HTMLInputElement ||
      e.target instanceof HTMLTextAreaElement
    ) {
      return
    }

    for (const shortcut of shortcuts) {
      const modMatch =
        (shortcut.ctrl === undefined || e.ctrlKey === shortcut.ctrl) &&
        (shortcut.meta === undefined || e.metaKey === shortcut.meta) &&
        (shortcut.shift === undefined || e.shiftKey === shortcut.shift) &&
        (shortcut.alt === undefined || e.altKey === shortcut.alt)

      if (e.key.toLowerCase() === shortcut.key.toLowerCase() && modMatch) {
        e.preventDefault()
        shortcut.handler()
        return
      }
    }
  }, [shortcuts])

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [handleKeyDown])
}

export const KEYBOARD_SHORTCUTS = {
  NEW_DASHBOARD: { key: 'n', ctrl: true, description: 'New Dashboard' },
  REFRESH: { key: 'r', ctrl: true, description: 'Refresh Data' },
  FOCUS_PROMPT: { key: '/', description: 'Focus Prompt Input' },
  TOGGLE_THEME: { key: 't', ctrl: true, description: 'Toggle Theme' },
  EXPORT_PDF: { key: 'p', ctrl: true, shift: true, description: 'Export PDF' },
  TOGGLE_HISTORY: { key: 'h', ctrl: true, description: 'Toggle History Panel' },
}
```

#### 2.2 Create Keyboard Shortcuts Help Dialog

**File**: `frontend/src/components/ui/keyboard-shortcuts-dialog.tsx` [NEW]

```tsx
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Keyboard } from 'lucide-react'

interface ShortcutItem {
  keys: string[]
  description: string
}

const shortcuts: ShortcutItem[] = [
  { keys: ['Ctrl', 'N'], description: 'New Dashboard' },
  { keys: ['Ctrl', 'R'], description: 'Refresh Data' },
  { keys: ['/'], description: 'Focus Prompt Input' },
  { keys: ['Ctrl', 'T'], description: 'Toggle Theme' },
  { keys: ['Ctrl', 'Shift', 'P'], description: 'Export as PDF' },
  { keys: ['Ctrl', 'H'], description: 'Toggle History Panel' },
  { keys: ['?'], description: 'Show Keyboard Shortcuts' },
]

export function KeyboardShortcutsDialog() {
  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="ghost" size="icon" className="h-9 w-9" title="Keyboard shortcuts">
          <Keyboard className="h-4 w-4" />
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Keyboard Shortcuts</DialogTitle>
          <DialogDescription>
            Quick actions to navigate the dashboard
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-2 py-4">
          {shortcuts.map((shortcut, i) => (
            <div key={i} className="flex items-center justify-between py-1">
              <span className="text-sm text-muted-foreground">
                {shortcut.description}
              </span>
              <div className="flex gap-1">
                {shortcut.keys.map((key, j) => (
                  <kbd
                    key={j}
                    className="px-2 py-1 text-xs font-semibold bg-muted rounded border"
                  >
                    {key}
                  </kbd>
                ))}
              </div>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}
```

#### 2.3 Integrate Shortcuts in DashboardView

**File**: `frontend/src/components/dashboard/DashboardView.tsx` [MODIFY]

```tsx
import { useKeyboardShortcuts, KEYBOARD_SHORTCUTS } from '@/hooks/useKeyboardShortcuts'
import { KeyboardShortcutsDialog } from '@/components/ui/keyboard-shortcuts-dialog'
import { useTheme } from '@/contexts/ThemeContext'

// Inside DashboardView component:
const promptInputRef = useRef<HTMLTextAreaElement>(null)
const { setTheme, resolvedTheme } = useTheme()
const [historyOpen, setHistoryOpen] = useState(false)

useKeyboardShortcuts([
  {
    ...KEYBOARD_SHORTCUTS.NEW_DASHBOARD,
    handler: handleNewDashboard,
  },
  {
    ...KEYBOARD_SHORTCUTS.REFRESH,
    handler: handleRefresh,
  },
  {
    ...KEYBOARD_SHORTCUTS.FOCUS_PROMPT,
    handler: () => promptInputRef.current?.focus(),
  },
  {
    ...KEYBOARD_SHORTCUTS.TOGGLE_THEME,
    handler: () => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark'),
  },
  {
    key: '?',
    handler: () => {}, // Dialog handles its own trigger
    description: 'Show shortcuts',
  },
])
```

---

### Step 3: Copy Chart SQL Button

**File**: `frontend/src/components/dashboard/ChartRenderer.tsx` [MODIFY]

Add a "Copy SQL" button next to each chart. In the chart actions area (around line 706):

```tsx
import { Copy } from 'lucide-react'

// Add state for SQL queries (get from dashboard.sql_queries)
// Find the button group area for each chart and add:

{!editMode && dashboard?.sql_queries && (
  <Button
    variant="ghost"
    size="icon"
    className="h-6 w-6 text-muted-foreground hover:text-primary"
    title="Copy SQL Query"
    onClick={async () => {
      const sqlEntry = dashboard.sql_queries.find(
        (q: { chart_id: string; sql: string }) => q.chart_id === chartId
      )
      if (sqlEntry) {
        await navigator.clipboard.writeText(sqlEntry.sql)
        // Optional: Show toast notification
        console.log('SQL copied to clipboard')
      }
    }}
  >
    <Copy className="h-3.5 w-3.5" />
  </Button>
)}
```

**Note**: Verify that `dashboard.sql_queries` structure matches `{ chart_id: string, sql: string }[]`.

---

### Step 4: Empty State Illustrations

#### 4.1 Create Empty State Component

**File**: `frontend/src/components/ui/empty-state.tsx` [NEW]

```tsx
import React from 'react'

interface EmptyStateProps {
  icon?: React.ReactNode
  title: string
  description?: string
  action?: React.ReactNode
  variant?: 'default' | 'chart' | 'history' | 'data'
}

// Simple SVG illustrations inline to avoid external dependencies
const illustrations = {
  default: (
    <svg className="w-24 h-24 text-muted-foreground/50" viewBox="0 0 100 100" fill="none">
      <circle cx="50" cy="50" r="40" stroke="currentColor" strokeWidth="2" strokeDasharray="8 4" />
      <path d="M35 50 L45 60 L65 40" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" opacity="0.5" />
    </svg>
  ),
  chart: (
    <svg className="w-24 h-24 text-muted-foreground/50" viewBox="0 0 100 100" fill="none">
      <rect x="15" y="60" width="15" height="25" rx="2" fill="currentColor" opacity="0.3" />
      <rect x="35" y="45" width="15" height="40" rx="2" fill="currentColor" opacity="0.4" />
      <rect x="55" y="30" width="15" height="55" rx="2" fill="currentColor" opacity="0.5" />
      <rect x="75" y="50" width="15" height="35" rx="2" fill="currentColor" opacity="0.3" />
      <line x1="10" y1="88" x2="95" y2="88" stroke="currentColor" strokeWidth="2" opacity="0.5" />
    </svg>
  ),
  history: (
    <svg className="w-24 h-24 text-muted-foreground/50" viewBox="0 0 100 100" fill="none">
      <circle cx="50" cy="50" r="35" stroke="currentColor" strokeWidth="2" opacity="0.5" />
      <path d="M50 25 V50 L65 60" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
      <path d="M20 50 A30 30 0 0 1 50 20" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <polygon points="18,45 22,55 12,55" fill="currentColor" opacity="0.5" />
    </svg>
  ),
  data: (
    <svg className="w-24 h-24 text-muted-foreground/50" viewBox="0 0 100 100" fill="none">
      <ellipse cx="50" cy="30" rx="35" ry="12" stroke="currentColor" strokeWidth="2" />
      <path d="M15 30 V70 C15 76.627 30.67 82 50 82 C69.33 82 85 76.627 85 70 V30" stroke="currentColor" strokeWidth="2" />
      <ellipse cx="50" cy="50" rx="35" ry="12" stroke="currentColor" strokeWidth="2" opacity="0.5" />
      <ellipse cx="50" cy="70" rx="35" ry="12" stroke="currentColor" strokeWidth="2" opacity="0.3" />
    </svg>
  ),
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  variant = 'default',
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
      <div className="mb-4">
        {icon || illustrations[variant]}
      </div>
      <h3 className="text-lg font-medium text-foreground mb-1">{title}</h3>
      {description && (
        <p className="text-sm text-muted-foreground max-w-sm mb-4">{description}</p>
      )}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}
```

#### 4.2 Replace Empty State in ChartRenderer

**File**: `frontend/src/components/dashboard/ChartRenderer.tsx` [MODIFY]

Update the empty state section (around line 522-529):

```tsx
import { EmptyState } from '@/components/ui/empty-state'

// Replace existing empty state:
if (!dashboard) {
  return (
    <EmptyState
      variant="chart"
      title="No dashboard generated yet"
      description="Enter a prompt above to start analyzing your data, or load a dashboard from history."
    />
  )
}
```

#### 4.3 Add Empty State to History Panel

**File**: `frontend/src/components/dashboard/SavedDashboards.tsx` [MODIFY]

Add empty state when no sessions exist.

---

### Step 5: Download Data as CSV

**File**: `frontend/src/components/dashboard/ChartRenderer.tsx` [MODIFY]

Add CSV download button for each chart (near the Copy SQL button):

```tsx
import { Download } from 'lucide-react'

// Utility function to convert data to CSV
const downloadCSV = async (chartId: string, title?: string) => {
  const token = localStorage.getItem('token')
  const dataUrl = spec.data?.url
  
  if (!dataUrl) return
  
  try {
    const response = await fetch(dataUrl, {
      headers: token ? { 'Authorization': `Bearer ${token}` } : {},
    })
    const data = await response.json()
    
    if (!data || !Array.isArray(data) || data.length === 0) return
    
    // Convert to CSV
    const headers = Object.keys(data[0])
    const csvRows = [
      headers.join(','),
      ...data.map((row: Record<string, unknown>) =>
        headers.map(h => {
          const val = row[h]
          // Escape quotes and wrap in quotes if contains comma
          const str = String(val ?? '')
          return str.includes(',') || str.includes('"')
            ? `"${str.replace(/"/g, '""')}"`
            : str
        }).join(',')
      ),
    ]
    const csvContent = csvRows.join('\n')
    
    // Download
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${title?.replace(/[^a-z0-9]/gi, '_') || chartId}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  } catch (error) {
    console.error('Failed to download CSV:', error)
  }
}

// Add button in chart actions area:
{!editMode && (
  <Button
    variant="ghost"
    size="icon"
    className="h-6 w-6 text-muted-foreground hover:text-primary"
    title="Download data as CSV"
    onClick={() => downloadCSV(chartId, spec.title)}
  >
    <Download className="h-3.5 w-3.5" />
  </Button>
)}
```

---

### Step 6: PDF Export

#### 6.1 Install Dependencies

```bash
cd frontend
pnpm add html2canvas jspdf
pnpm add -D @types/jspdf
```

#### 6.2 Create PDF Export Utility

**File**: `frontend/src/lib/pdf-export.ts` [NEW]

```tsx
import html2canvas from 'html2canvas'
import { jsPDF } from 'jspdf'

interface ExportOptions {
  title?: string
  description?: string
  filename?: string
}

export async function exportDashboardToPDF(
  containerElement: HTMLElement,
  options: ExportOptions = {}
): Promise<void> {
  const { title = 'Dashboard', description, filename = 'dashboard' } = options

  // Create PDF with A4 dimensions
  const pdf = new jsPDF({
    orientation: 'landscape',
    unit: 'mm',
    format: 'a4',
  })

  const pageWidth = pdf.internal.pageSize.getWidth()
  const pageHeight = pdf.internal.pageSize.getHeight()
  const margin = 15

  // Add title
  pdf.setFontSize(20)
  pdf.setTextColor(51, 51, 51)
  pdf.text(title, margin, margin + 5)

  // Add description if provided
  let yOffset = margin + 12
  if (description) {
    pdf.setFontSize(11)
    pdf.setTextColor(102, 102, 102)
    pdf.text(description, margin, yOffset)
    yOffset += 8
  }

  // Add timestamp
  pdf.setFontSize(9)
  pdf.setTextColor(153, 153, 153)
  pdf.text(`Generated: ${new Date().toLocaleString()}`, margin, yOffset)
  yOffset += 10

  // Capture the chart container
  try {
    const canvas = await html2canvas(containerElement, {
      scale: 2,
      useCORS: true,
      logging: false,
      backgroundColor: '#ffffff',
    })

    const imgData = canvas.toDataURL('image/png')
    const imgWidth = pageWidth - 2 * margin
    const imgHeight = (canvas.height * imgWidth) / canvas.width

    // Check if image fits on current page
    const availableHeight = pageHeight - yOffset - margin
    if (imgHeight > availableHeight) {
      // Scale down to fit
      const scaleFactor = availableHeight / imgHeight
      pdf.addImage(
        imgData,
        'PNG',
        margin,
        yOffset,
        imgWidth * scaleFactor,
        imgHeight * scaleFactor
      )
    } else {
      pdf.addImage(imgData, 'PNG', margin, yOffset, imgWidth, imgHeight)
    }

    // Save the PDF
    pdf.save(`${filename.replace(/[^a-z0-9]/gi, '_')}.pdf`)
  } catch (error) {
    console.error('Failed to generate PDF:', error)
    throw error
  }
}
```

#### 6.3 Add PDF Export Button

**File**: `frontend/src/components/dashboard/ChartRenderer.tsx` [MODIFY]

Add PDF export button next to HTML export (around line 605):

```tsx
import { FileText } from 'lucide-react'
import { exportDashboardToPDF } from '@/lib/pdf-export'

// Add ref to the chart content container
const chartContentRef = useRef<HTMLDivElement>(null)

// Add PDF export handler:
const handleExportPDF = async () => {
  if (!chartContentRef.current || !dashboard) return
  
  try {
    await exportDashboardToPDF(chartContentRef.current, {
      title: dashboard.title,
      description: dashboard.description,
      filename: dashboard.title || 'dashboard',
    })
  } catch (error) {
    console.error('PDF export failed:', error)
  }
}

// Add button next to HTML export:
<Button
  variant="outline"
  size="sm"
  onClick={handleExportPDF}
  className="gap-2"
>
  <FileText className="h-4 w-4" /> Export PDF
</Button>

// Wrap CardContent's inner content with ref:
<CardContent className="p-4 bg-card overflow-hidden" ref={containerRef}>
  <div ref={chartContentRef}>
    {/* existing GridLayout content */}
  </div>
</CardContent>
```

---

## File Change Summary

| File | Action | Description |
|------|--------|-------------|
| `frontend/src/contexts/ThemeContext.tsx` | NEW | Theme provider and hook |
| `frontend/src/components/ui/theme-toggle.tsx` | NEW | Theme toggle dropdown |
| `frontend/src/hooks/useKeyboardShortcuts.ts` | NEW | Keyboard shortcuts hook |
| `frontend/src/components/ui/keyboard-shortcuts-dialog.tsx` | NEW | Shortcuts help dialog |
| `frontend/src/components/ui/empty-state.tsx` | NEW | Empty state with illustrations |
| `frontend/src/lib/pdf-export.ts` | NEW | PDF export utility |
| `frontend/src/App.tsx` | MODIFY | Add ThemeProvider |
| `frontend/src/components/dashboard/DashboardView.tsx` | MODIFY | Add theme toggle, shortcuts |
| `frontend/src/components/dashboard/ChartRenderer.tsx` | MODIFY | Copy SQL, CSV download, PDF export, empty state, dark mode |
| `frontend/package.json` | MODIFY | Add html2canvas, jspdf |

---

## Verification Plan

### Install Dependencies

```bash
cd frontend
pnpm add html2canvas jspdf
pnpm add -D @types/jspdf
```

### Build Verification

```bash
cd frontend
pnpm build
```

This should complete without TypeScript errors.

### Manual Testing Checklist

1. **Dark/Light Theme Toggle**:
   - [ ] Click theme toggle button in header
   - [ ] Select "Dark" - verify UI switches to dark mode
   - [ ] Select "Light" - verify UI switches to light mode  
   - [ ] Select "System" - verify follows OS preference
   - [ ] Refresh page - theme preference persists
   - [ ] Verify charts also switch theme (quartz vs dark)

2. **Keyboard Shortcuts**:
   - [ ] Press `/` - prompt input gets focus
   - [ ] Press `Ctrl+R` - dashboard refreshes (if active)
   - [ ] Press `Ctrl+T` - theme toggles
   - [ ] Press `?` - shortcuts dialog opens
   - [ ] Type in prompt input - shortcuts don't trigger

3. **Copy Chart SQL**:
   - [ ] Generate a dashboard with charts
   - [ ] Click copy SQL button on a chart
   - [ ] Paste in text editor - verify SQL query appears

4. **Empty State Illustrations**:
   - [ ] Load app with no dashboard - see chart illustration
   - [ ] Open history panel with no history - see history illustration

5. **Download CSV**:
   - [ ] Generate a dashboard with charts
   - [ ] Click CSV download button on a chart
   - [ ] Open downloaded file - verify data in CSV format

6. **PDF Export**:
   - [ ] Generate a dashboard with charts
   - [ ] Click "Export PDF" button
   - [ ] Open PDF - verify title, description, charts visible
   - [ ] Verify layout fits on page properly

---

## Implementation Order

1. **Step 1.1-1.3**: Theme context and provider (foundation)
2. **Step 1.4-1.5**: Theme toggle and chart theme integration
3. **Step 2**: Keyboard shortcuts
4. **Step 3**: Copy SQL button
5. **Step 4**: Empty state illustrations
6. **Step 5**: CSV download
7. **Step 6**: PDF export (requires npm install)

---

## Notes for Implementation Agent

- All code is TypeScript with strict mode
- Use single quotes, no semicolons (per user preferences)
- Run `pnpm build` after changes to verify no TS errors
- Test each feature incrementally
- html2canvas and jspdf are popular, well-maintained libraries
