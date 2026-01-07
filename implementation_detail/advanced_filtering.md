# Implementation Plan: Advanced Filtering & Drill-Down

This document provides a step-by-step implementation guide for advanced filtering and drill-down capabilities.

---

## Overview

**Goal**: Enhance filtering capabilities with 5 features:
1. **Date Range Pickers** - Calendar-based date selection
2. **Multi-Select Filters** - Select multiple values for categorical fields
3. **Search Filters** - Type-ahead search for high-cardinality fields
4. **Filter Persistence** - Remember filter states across sessions
5. **Cross-Chart Filtering** - Click on one chart to filter all related charts

---

## Current State

| Component | Status |
|-----------|--------|
| `FilterPanel.tsx` | Displays active filters as badges, supports removal |
| `DashboardView.tsx` | Manages `filterState`, calls `/dashboard/filter` API |
| `ChartRenderer.tsx` | Cross-chart click filtering already implemented (lines 94-137) |
| `/dashboard/filter` API | Backend endpoint exists for applying filters |
| Filter persistence | Not implemented (commented code at line 258-259) |

**What works today**: Basic filter display/removal, cross-chart click triggers `handleFilterChange`.

---

## Implementation Steps

### Step 1: Install Date Picker Dependencies

```bash
cd frontend
pnpm add react-day-picker date-fns
```

---

### Step 2: Create UI Components

#### 2.1 Date Range Picker Component

**File**: `frontend/src/components/ui/date-range-picker.tsx` [NEW]

```tsx
import * as React from 'react'
import { format } from 'date-fns'
import { Calendar as CalendarIcon } from 'lucide-react'
import { DateRange, DayPicker } from 'react-day-picker'
import 'react-day-picker/dist/style.css'

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'

interface DateRangePickerProps {
  value?: DateRange
  onChange: (range: DateRange | undefined) => void
  placeholder?: string
  className?: string
}

export function DateRangePicker({
  value,
  onChange,
  placeholder = 'Pick a date range',
  className,
}: DateRangePickerProps) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className={cn(
            'w-full justify-start text-left font-normal',
            !value && 'text-muted-foreground',
            className
          )}
        >
          <CalendarIcon className="mr-2 h-4 w-4" />
          {value?.from ? (
            value.to ? (
              <>
                {format(value.from, 'LLL dd, y')} - {format(value.to, 'LLL dd, y')}
              </>
            ) : (
              format(value.from, 'LLL dd, y')
            )
          ) : (
            <span>{placeholder}</span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <DayPicker
          mode="range"
          defaultMonth={value?.from}
          selected={value}
          onSelect={onChange}
          numberOfMonths={2}
          className="p-3"
        />
      </PopoverContent>
    </Popover>
  )
}
```

#### 2.2 Multi-Select Filter Component

**File**: `frontend/src/components/ui/multi-select.tsx` [NEW]

```tsx
import * as React from 'react'
import { Check, ChevronsUpDown, X } from 'lucide-react'

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { Badge } from '@/components/ui/badge'

interface MultiSelectProps {
  options: string[]
  value: string[]
  onChange: (value: string[]) => void
  placeholder?: string
  searchPlaceholder?: string
  className?: string
  maxDisplay?: number
}

export function MultiSelect({
  options,
  value,
  onChange,
  placeholder = 'Select items...',
  searchPlaceholder = 'Search...',
  className,
  maxDisplay = 3,
}: MultiSelectProps) {
  const [open, setOpen] = React.useState(false)
  const [search, setSearch] = React.useState('')

  const filteredOptions = React.useMemo(() => {
    if (!search) return options
    return options.filter((opt) =>
      opt.toLowerCase().includes(search.toLowerCase())
    )
  }, [options, search])

  const toggleOption = (option: string) => {
    if (value.includes(option)) {
      onChange(value.filter((v) => v !== option))
    } else {
      onChange([...value, option])
    }
  }

  const removeOption = (option: string, e: React.MouseEvent) => {
    e.stopPropagation()
    onChange(value.filter((v) => v !== option))
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={cn('w-full justify-between', className)}
        >
          <div className="flex flex-wrap gap-1 truncate">
            {value.length === 0 ? (
              <span className="text-muted-foreground">{placeholder}</span>
            ) : value.length <= maxDisplay ? (
              value.map((v) => (
                <Badge key={v} variant="secondary" className="mr-1">
                  {v}
                  <button
                    className="ml-1 ring-offset-background rounded-full outline-none"
                    onMouseDown={(e) => removeOption(v, e)}
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))
            ) : (
              <span>{value.length} selected</span>
            )}
          </div>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-full p-0" align="start">
        <div className="p-2 border-b">
          <input
            className="w-full px-2 py-1 text-sm border rounded outline-none focus:ring-1 ring-primary"
            placeholder={searchPlaceholder}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="max-h-60 overflow-auto p-1">
          {filteredOptions.length === 0 ? (
            <div className="py-6 text-center text-sm text-muted-foreground">
              No options found.
            </div>
          ) : (
            filteredOptions.map((option) => (
              <div
                key={option}
                className={cn(
                  'flex items-center px-2 py-1.5 text-sm rounded cursor-pointer hover:bg-accent',
                  value.includes(option) && 'bg-accent'
                )}
                onClick={() => toggleOption(option)}
              >
                <div
                  className={cn(
                    'mr-2 flex h-4 w-4 items-center justify-center rounded-sm border',
                    value.includes(option)
                      ? 'bg-primary border-primary text-primary-foreground'
                      : 'border-muted'
                  )}
                >
                  {value.includes(option) && <Check className="h-3 w-3" />}
                </div>
                {option}
              </div>
            ))
          )}
        </div>
        {value.length > 0 && (
          <div className="p-2 border-t">
            <Button
              variant="ghost"
              size="sm"
              className="w-full"
              onClick={() => onChange([])}
            >
              Clear all
            </Button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  )
}
```

#### 2.3 Search Filter Component (Type-Ahead)

**File**: `frontend/src/components/ui/search-filter.tsx` [NEW]

```tsx
import * as React from 'react'
import { Search, X } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

interface SearchFilterProps {
  value: string
  onChange: (value: string) => void
  suggestions?: string[]
  placeholder?: string
  className?: string
  debounceMs?: number
}

export function SearchFilter({
  value,
  onChange,
  suggestions = [],
  placeholder = 'Search...',
  className,
  debounceMs = 300,
}: SearchFilterProps) {
  const [inputValue, setInputValue] = React.useState(value)
  const [showSuggestions, setShowSuggestions] = React.useState(false)
  const inputRef = React.useRef<HTMLInputElement>(null)
  const debounceRef = React.useRef<ReturnType<typeof setTimeout>>()

  // Debounce the onChange callback
  React.useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }
    debounceRef.current = setTimeout(() => {
      if (inputValue !== value) {
        onChange(inputValue)
      }
    }, debounceMs)

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current)
      }
    }
  }, [inputValue, value, onChange, debounceMs])

  const filteredSuggestions = React.useMemo(() => {
    if (!inputValue || inputValue.length < 2) return []
    return suggestions
      .filter((s) => s.toLowerCase().includes(inputValue.toLowerCase()))
      .slice(0, 10)
  }, [suggestions, inputValue])

  const handleSelect = (suggestion: string) => {
    setInputValue(suggestion)
    onChange(suggestion)
    setShowSuggestions(false)
  }

  const handleClear = () => {
    setInputValue('')
    onChange('')
    inputRef.current?.focus()
  }

  return (
    <div className={cn('relative', className)}>
      <div className="relative">
        <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          ref={inputRef}
          value={inputValue}
          onChange={(e) => {
            setInputValue(e.target.value)
            setShowSuggestions(true)
          }}
          onFocus={() => setShowSuggestions(true)}
          onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
          placeholder={placeholder}
          className="pl-8 pr-8"
        />
        {inputValue && (
          <button
            onClick={handleClear}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {showSuggestions && filteredSuggestions.length > 0 && (
        <div className="absolute z-50 w-full mt-1 bg-popover border rounded-md shadow-lg max-h-60 overflow-auto">
          {filteredSuggestions.map((suggestion) => (
            <div
              key={suggestion}
              className="px-3 py-2 text-sm cursor-pointer hover:bg-accent"
              onMouseDown={() => handleSelect(suggestion)}
            >
              {suggestion}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

---

### Step 3: Create Advanced Filter Panel

**File**: `frontend/src/components/dashboard/AdvancedFilterPanel.tsx` [NEW]

This replaces or extends the existing FilterPanel with advanced capabilities.

```tsx
import React, { useState, useEffect } from 'react'
import { Filter, Plus, ChevronDown, ChevronUp, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { DateRangePicker } from '@/components/ui/date-range-picker'
import { MultiSelect } from '@/components/ui/multi-select'
import { SearchFilter } from '@/components/ui/search-filter'
import type { DateRange } from 'react-day-picker'

interface FilterField {
  name: string
  type: 'text' | 'number' | 'date' | 'categorical'
  values?: string[]  // For categorical fields
  isHighCardinality?: boolean  // For search filter
}

interface AdvancedFilterPanelProps {
  filters: Record<string, FilterValue>
  availableFields: FilterField[]
  onFilterChange: (filters: Record<string, FilterValue>) => void
  onRemoveFilter: (key: string) => void
  onClearAll: () => void
  className?: string
}

type FilterValue = string | string[] | DateRange | number | { min?: number; max?: number }

export const AdvancedFilterPanel: React.FC<AdvancedFilterPanelProps> = ({
  filters,
  availableFields,
  onFilterChange,
  onRemoveFilter,
  onClearAll,
  className,
}) => {
  const [isExpanded, setIsExpanded] = useState(false)
  const [addingFilter, setAddingFilter] = useState(false)
  const [selectedField, setSelectedField] = useState<string>('')

  const hasFilters = Object.keys(filters).length > 0
  const usedFields = new Set(Object.keys(filters))
  const unusedFields = availableFields.filter((f) => !usedFields.has(f.name))

  const handleAddFilter = (fieldName: string) => {
    const field = availableFields.find((f) => f.name === fieldName)
    if (!field) return

    // Initialize with appropriate default value
    let defaultValue: FilterValue
    switch (field.type) {
      case 'categorical':
        defaultValue = []
        break
      case 'date':
        defaultValue = { from: undefined, to: undefined } as DateRange
        break
      default:
        defaultValue = ''
    }

    onFilterChange({ ...filters, [fieldName]: defaultValue })
    setAddingFilter(false)
    setSelectedField('')
  }

  const updateFilter = (fieldName: string, value: FilterValue) => {
    onFilterChange({ ...filters, [fieldName]: value })
  }

  const renderFilterInput = (field: FilterField) => {
    const currentValue = filters[field.name]

    switch (field.type) {
      case 'date':
        return (
          <DateRangePicker
            value={currentValue as DateRange}
            onChange={(range) => updateFilter(field.name, range || {})}
            className="w-64"
          />
        )

      case 'categorical':
        if (field.isHighCardinality) {
          return (
            <SearchFilter
              value={Array.isArray(currentValue) ? currentValue[0] || '' : String(currentValue || '')}
              onChange={(v) => updateFilter(field.name, v ? [v] : [])}
              suggestions={field.values || []}
              placeholder={`Search ${field.name}...`}
              className="w-64"
            />
          )
        }
        return (
          <MultiSelect
            options={field.values || []}
            value={Array.isArray(currentValue) ? currentValue : []}
            onChange={(v) => updateFilter(field.name, v)}
            placeholder={`Select ${field.name}...`}
            className="w-64"
          />
        )

      default:
        return (
          <SearchFilter
            value={String(currentValue || '')}
            onChange={(v) => updateFilter(field.name, v)}
            placeholder={`Filter ${field.name}...`}
            className="w-48"
          />
        )
    }
  }

  const formatFilterValue = (value: FilterValue): string => {
    if (Array.isArray(value)) {
      return value.length > 2 ? `${value.length} selected` : value.join(', ')
    }
    if (typeof value === 'object' && value !== null) {
      const range = value as DateRange
      if (range.from && range.to) {
        return `${range.from.toLocaleDateString()} - ${range.to.toLocaleDateString()}`
      }
      if (range.from) return `From ${range.from.toLocaleDateString()}`
    }
    return String(value)
  }

  return (
    <Card className={`w-full border-muted/40 shadow-sm ${className}`}>
      <CardHeader className="flex flex-row items-center justify-between py-3 px-4">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-primary" />
          <CardTitle className="text-sm font-medium">Filters</CardTitle>
          {hasFilters && (
            <Badge variant="secondary" className="ml-2">
              {Object.keys(filters).length}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          {hasFilters && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onClearAll}
              className="h-8 px-2 text-xs text-muted-foreground hover:text-destructive"
            >
              Clear All
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            className="h-8 px-2"
          >
            {isExpanded ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </Button>
        </div>
      </CardHeader>

      <CardContent className="px-4 pb-3 pt-0">
        {/* Active filter badges */}
        <div className="flex flex-wrap gap-2 mb-2">
          {Object.entries(filters).map(([key, value]) => {
            const displayValue = formatFilterValue(value)
            if (!displayValue) return null

            return (
              <Badge
                key={key}
                variant="secondary"
                className="flex items-center gap-1.5 py-1 px-2.5 text-sm font-normal border-primary/20 bg-primary/5 hover:bg-primary/10"
              >
                <span className="font-medium text-foreground/80">{key}:</span>
                <span className="text-foreground font-semibold truncate max-w-32">
                  {displayValue}
                </span>
                <button
                  onClick={() => onRemoveFilter(key)}
                  className="ml-1 rounded-full p-0.5 hover:bg-black/10"
                >
                  <X className="h-3 w-3 text-muted-foreground" />
                </button>
              </Badge>
            )
          })}

          {/* Add filter button */}
          <Popover open={addingFilter} onOpenChange={setAddingFilter}>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                size="sm"
                className="h-7 border-dashed text-xs text-muted-foreground gap-1"
                disabled={unusedFields.length === 0}
              >
                <Plus className="h-3 w-3" />
                Add Filter
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-56 p-2" align="start">
              <Select value={selectedField} onValueChange={handleAddFilter}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Select field..." />
                </SelectTrigger>
                <SelectContent>
                  {unusedFields.map((field) => (
                    <SelectItem key={field.name} value={field.name}>
                      {field.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </PopoverContent>
          </Popover>
        </div>

        {/* Expanded filter inputs */}
        {isExpanded && hasFilters && (
          <div className="mt-4 space-y-3 pt-3 border-t">
            {Object.keys(filters).map((fieldName) => {
              const field = availableFields.find((f) => f.name === fieldName)
              if (!field) return null

              return (
                <div key={fieldName} className="flex items-center gap-3">
                  <label className="text-sm font-medium w-24 truncate">
                    {fieldName}
                  </label>
                  {renderFilterInput(field)}
                </div>
              )
            })}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
```

---

### Step 4: Filter Persistence Hook

**File**: `frontend/src/hooks/useFilterPersistence.ts` [NEW]

```tsx
import { useEffect, useCallback } from 'react'

const STORAGE_KEY_PREFIX = 'dashboard_filters_'

interface FilterPersistenceOptions {
  sessionId: string | null
  enabled?: boolean
}

export function useFilterPersistence<T extends Record<string, unknown>>(
  filters: T,
  setFilters: (filters: T) => void,
  options: FilterPersistenceOptions
) {
  const { sessionId, enabled = true } = options
  const storageKey = sessionId ? `${STORAGE_KEY_PREFIX}${sessionId}` : null

  // Load filters from localStorage on mount
  useEffect(() => {
    if (!enabled || !storageKey) return

    try {
      const stored = localStorage.getItem(storageKey)
      if (stored) {
        const parsed = JSON.parse(stored)
        // Restore date objects from ISO strings
        const restored = restoreDates(parsed)
        setFilters(restored as T)
      }
    } catch (error) {
      console.warn('Failed to load persisted filters:', error)
    }
  }, [storageKey, enabled, setFilters])

  // Save filters to localStorage on change
  useEffect(() => {
    if (!enabled || !storageKey) return

    try {
      if (Object.keys(filters).length > 0) {
        // Serialize dates to ISO strings
        const serialized = serializeDates(filters)
        localStorage.setItem(storageKey, JSON.stringify(serialized))
      } else {
        localStorage.removeItem(storageKey)
      }
    } catch (error) {
      console.warn('Failed to persist filters:', error)
    }
  }, [filters, storageKey, enabled])

  // Clear persisted filters
  const clearPersisted = useCallback(() => {
    if (storageKey) {
      localStorage.removeItem(storageKey)
    }
  }, [storageKey])

  return { clearPersisted }
}

// Helper to serialize Date objects
function serializeDates(obj: unknown): unknown {
  if (obj instanceof Date) {
    return { __type: 'Date', value: obj.toISOString() }
  }
  if (Array.isArray(obj)) {
    return obj.map(serializeDates)
  }
  if (obj && typeof obj === 'object') {
    return Object.fromEntries(
      Object.entries(obj).map(([k, v]) => [k, serializeDates(v)])
    )
  }
  return obj
}

// Helper to restore Date objects
function restoreDates(obj: unknown): unknown {
  if (obj && typeof obj === 'object') {
    const asRecord = obj as Record<string, unknown>
    if (asRecord.__type === 'Date' && typeof asRecord.value === 'string') {
      return new Date(asRecord.value)
    }
    if (Array.isArray(obj)) {
      return obj.map(restoreDates)
    }
    return Object.fromEntries(
      Object.entries(asRecord).map(([k, v]) => [k, restoreDates(v)])
    )
  }
  return obj
}
```

---

### Step 5: Update DashboardView with Advanced Filtering

**File**: `frontend/src/components/dashboard/DashboardView.tsx` [MODIFY]

Key changes:
1. Replace `FilterPanel` with `AdvancedFilterPanel`
2. Add filter persistence hook
3. Extract available filter fields from dashboard schema

```tsx
// Add imports
import { AdvancedFilterPanel } from './AdvancedFilterPanel'
import { useFilterPersistence } from '@/hooks/useFilterPersistence'
import type { DateRange } from 'react-day-picker'

// Inside DashboardView component:

// Replace filterState type to support advanced values
type FilterValue = string | string[] | DateRange | number
const [filterState, setFilterState] = useState<Record<string, FilterValue>>({})

// Add filter persistence
const { clearPersisted } = useFilterPersistence(
  filterState,
  setFilterState,
  { sessionId, enabled: !!sessionId }
)

// Extract available filter fields from dashboard metadata
const availableFilterFields = React.useMemo(() => {
  if (!dashboard?.individual_specs) return []
  
  const fieldsMap = new Map<string, { type: 'text' | 'date' | 'categorical', values: Set<string> }>()
  
  for (const spec of dashboard.individual_specs) {
    const encoding = spec.encoding || {}
    
    // Extract fields and their types from encodings
    for (const [channel, enc] of Object.entries(encoding)) {
      if (!enc || typeof enc !== 'object') continue
      const encObj = enc as Record<string, unknown>
      const field = encObj.field as string
      const type = encObj.type as string
      
      if (!field || channel === 'tooltip') continue
      
      let fieldType: 'text' | 'date' | 'categorical' = 'text'
      if (type === 'temporal') fieldType = 'date'
      else if (type === 'nominal' || type === 'ordinal') fieldType = 'categorical'
      
      if (!fieldsMap.has(field)) {
        fieldsMap.set(field, { type: fieldType, values: new Set() })
      }
    }
  }
  
  return Array.from(fieldsMap.entries()).map(([name, { type, values }]) => ({
    name,
    type,
    values: Array.from(values),
    isHighCardinality: values.size > 50,
  }))
}, [dashboard?.individual_specs])

// Update handleNewDashboard to clear persisted filters
const handleNewDashboard = () => {
  setSessionId(null)
  setDashboard(null)
  setFilterState({})
  clearPersisted()
}

// Replace FilterPanel usage in JSX:
{Object.keys(filterState).length > 0 && (
  <AdvancedFilterPanel
    filters={filterState}
    availableFields={availableFilterFields}
    onFilterChange={handleFilterChange}
    onRemoveFilter={handleRemoveFilter}
    onClearAll={handleClearFilters}
    className="mb-4"
  />
)}
```

---

### Step 6: Enhance Cross-Chart Filtering

The current implementation in `ChartRenderer.tsx` already supports cross-chart filtering via the `onFilterChange` callback. To enhance it:

**File**: `frontend/src/components/dashboard/ChartRenderer.tsx` [MODIFY]

Add visual feedback for which chart is triggering filters (around line 95-137):

```tsx
// Add state for active filter source
const [activeFilterSource, setActiveFilterSource] = useState<string | null>(null)

// Modify click handler:
result.view.addEventListener('click', (_event: any, item: any) => {
  if (item && item.datum) {
    // ... existing filter extraction logic ...
    
    if (Object.keys(filters).length > 0) {
      setActiveFilterSource(chartId)  // Track source
      console.log('Drill-down from chart:', chartId, 'filters:', filters)
      onFilterChange(filters)
      
      // Clear highlight after animation
      setTimeout(() => setActiveFilterSource(null), 1000)
    }
  }
})

// Add visual indicator in chart wrapper:
<div
  key={chartId}
  className={cn(
    'bg-card rounded-lg border shadow-sm',
    editMode && 'cursor-move ring-2 ring-primary/20',
    activeFilterSource === chartId && 'ring-2 ring-green-500 animate-pulse'
  )}
  style={{ overflow: 'hidden' }}
>
```

---

### Step 7: Backend Filter Enhancement (Optional)

If date range filters need special handling on the backend:

**File**: `backend/routes/dashboard.py` [MODIFY]

Update the filter endpoint to handle date ranges:

```python
# In the filter handling logic, add date range parsing:

def parse_filter_value(key: str, value: Any) -> Any:
    """Parse filter values, handling special types like date ranges."""
    if isinstance(value, dict):
        # Date range format: { "from": "ISO_DATE", "to": "ISO_DATE" }
        if "from" in value or "to" in value:
            from_date = value.get("from")
            to_date = value.get("to")
            return {"type": "date_range", "from": from_date, "to": to_date}
    if isinstance(value, list):
        return {"type": "multi_select", "values": value}
    return value
```

---

## File Change Summary

| File | Action | Description |
|------|--------|-------------|
| `frontend/src/components/ui/date-range-picker.tsx` | NEW | Calendar date range selector |
| `frontend/src/components/ui/multi-select.tsx` | NEW | Multi-value selection with search |
| `frontend/src/components/ui/search-filter.tsx` | NEW | Type-ahead search input |
| `frontend/src/components/dashboard/AdvancedFilterPanel.tsx` | NEW | Enhanced filter panel |
| `frontend/src/hooks/useFilterPersistence.ts` | NEW | localStorage persistence hook |
| `frontend/src/components/dashboard/DashboardView.tsx` | MODIFY | Integrate advanced filters |
| `frontend/src/components/dashboard/ChartRenderer.tsx` | MODIFY | Visual feedback for cross-chart filtering |
| `frontend/package.json` | MODIFY | Add react-day-picker, date-fns |

---

## Verification Plan

### Install Dependencies

```bash
cd frontend
pnpm add react-day-picker date-fns
pnpm build
```

### Manual Testing Checklist

1. **Date Range Picker**:
   - [ ] Click "Add Filter" and select a date field
   - [ ] Calendar popup appears with two-month view
   - [ ] Select start and end dates - range displays correctly
   - [ ] Filter badge shows date range
   - [ ] Charts update to reflect date filter

2. **Multi-Select Filters**:
   - [ ] Add filter for a categorical field
   - [ ] Multi-select dropdown appears with search
   - [ ] Select multiple values - all show as selected
   - [ ] Clear individual values or "Clear all"
   - [ ] Charts update with multi-value filter

3. **Search Filters**:
   - [ ] Type in search filter with high-cardinality field
   - [ ] Type-ahead suggestions appear after 2 characters
   - [ ] Select suggestion - filter applied
   - [ ] Clear button works

4. **Filter Persistence**:
   - [ ] Apply filters to a dashboard
   - [ ] Refresh the page
   - [ ] Filters are restored from localStorage
   - [ ] Create new dashboard - filters cleared
   - [ ] Load different session - correct filters loaded

5. **Cross-Chart Filtering**:
   - [ ] Click on a bar/point in any chart
   - [ ] Source chart briefly highlights (green ring)
   - [ ] Filter badge appears with clicked value
   - [ ] All other charts update to reflect filter
   - [ ] Remove filter - charts return to original state

---

## Implementation Order

1. Install dependencies (`react-day-picker`, `date-fns`)
2. Create UI components (date picker, multi-select, search filter)
3. Create `AdvancedFilterPanel.tsx`
4. Create `useFilterPersistence.ts` hook
5. Update `DashboardView.tsx` to use new components
6. Enhance `ChartRenderer.tsx` cross-chart visual feedback
7. Test all features

---

## Notes for Implementation Agent

- This is mostly frontend work
- Backend may need minor changes for date range SQL generation
- react-day-picker is a lightweight, accessible date picker
- Filter persistence uses localStorage (no backend changes needed)
- Cross-chart filtering already works - just adding visual polish
- Test with actual dashboard data to verify filter field extraction
