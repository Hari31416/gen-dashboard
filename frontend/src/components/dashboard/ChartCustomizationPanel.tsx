import React, { useState } from 'react'
import { Palette, Type, Settings2, LayoutGrid, Paintbrush, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
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
import { COLOR_PALETTES } from '@/lib/color-palettes'
import type {
  ChartCustomization,
  ColorPalette,
  LegendPosition,
  ChartTheme
} from '@/types/chart-customization'

interface ChartCustomizationPanelProps {
  chartId: string
  currentTitle?: string
  customization: ChartCustomization
  onCustomizationChange: (customization: ChartCustomization) => void
}

const LEGEND_POSITIONS: { value: LegendPosition; label: string }[] = [
  { value: 'right', label: 'Right' },
  { value: 'left', label: 'Left' },
  { value: 'top', label: 'Top' },
  { value: 'bottom', label: 'Bottom' },
  { value: 'top-left', label: 'Top Left' },
  { value: 'top-right', label: 'Top Right' },
  { value: 'bottom-left', label: 'Bottom Left' },
  { value: 'bottom-right', label: 'Bottom Right' },
  { value: 'none', label: 'Hidden' },
]

const THEMES: { value: ChartTheme; label: string }[] = [
  { value: 'default', label: 'Default' },
  { value: 'quartz', label: 'Quartz' },
  { value: 'dark', label: 'Dark' },
  { value: 'vox', label: 'Vox' },
  { value: 'fivethirtyeight', label: 'FiveThirtyEight' },
  { value: 'latimes', label: 'LA Times' },
  { value: 'ggplot2', label: 'ggplot2' },
  { value: 'googlecharts', label: 'Google Charts' },
]

export const ChartCustomizationPanel: React.FC<ChartCustomizationPanelProps> = ({
  chartId: _chartId, // Keeping chartId in props for potential future use or keying
  currentTitle,
  customization,
  onCustomizationChange,
}) => {
  const [activeTab, setActiveTab] = useState<'colors' | 'text' | 'axes' | 'legend' | 'theme'>('colors')

  const updateCustomization = (updates: Partial<ChartCustomization>) => {
    onCustomizationChange({ ...customization, ...updates })
  }

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6 text-muted-foreground hover:text-primary"
          title="Customize chart"
        >
          <Paintbrush className="h-3.5 w-3.5" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-0" align="end">
        {/* Tab navigation */}
        <div className="flex border-b">
          {[
            { id: 'colors', icon: Palette, label: 'Colors' },
            { id: 'text', icon: Type, label: 'Text' },
            { id: 'axes', icon: Settings2, label: 'Axes' },
            { id: 'legend', icon: LayoutGrid, label: 'Legend' },
            { id: 'theme', icon: Paintbrush, label: 'Theme' },
          ].map(({ id, icon: Icon, label }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id as typeof activeTab)}
              className={`flex-1 flex flex-col items-center gap-1 py-2 text-xs border-b-2 transition-colors ${activeTab === id
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
                }`}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          ))}
        </div>

        <div className="p-4 space-y-4 max-h-[400px] overflow-y-auto">
          {/* Colors Tab */}
          {activeTab === 'colors' && (
            <div className="space-y-4">
              {/* Single color for charts without color encoding */}
              <div className="space-y-2">
                <Label className="text-xs text-muted-foreground uppercase tracking-wide">
                  Chart Color (single-color charts)
                </Label>
                <div className="flex gap-2">
                  <Input
                    type="color"
                    value={customization.markColor ?? '#4e79a7'}
                    onChange={(e) => updateCustomization({ markColor: e.target.value })}
                    className="w-12 h-8 p-1 cursor-pointer"
                  />
                  <Input
                    value={customization.markColor ?? ''}
                    onChange={(e) => updateCustomization({ markColor: e.target.value || undefined })}
                    placeholder="Default"
                    className="flex-1 h-8"
                  />
                  {customization.markColor && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-8 px-2"
                      onClick={() => updateCustomization({ markColor: undefined })}
                    >
                      Clear
                    </Button>
                  )}
                </div>
              </div>

              {/* Color palettes for multi-color charts */}
              <div className="pt-2 border-t">
                <Label className="text-xs text-muted-foreground uppercase tracking-wide mb-2 block">
                  Color Palette (multi-series charts)
                </Label>
                <ColorPaletteSelector
                  selected={customization.colorPalette}
                  onSelect={(palette) => updateCustomization({ colorPalette: palette })}
                />
              </div>
            </div>
          )}

          {/* Text Tab */}
          {activeTab === 'text' && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="title">Chart Title</Label>
                <Input
                  id="title"
                  value={customization.title ?? currentTitle ?? ''}
                  onChange={(e) => updateCustomization({ title: e.target.value })}
                  placeholder="Enter chart title..."
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="titleSize">Title Font Size</Label>
                <Select
                  value={String(customization.titleFontSize ?? 14)}
                  onValueChange={(v) => updateCustomization({ titleFontSize: Number(v) })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {[10, 12, 14, 16, 18, 20, 24, 28, 32].map((size) => (
                      <SelectItem key={size} value={String(size)}>
                        {size}px
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}

          {/* Axes Tab */}
          {activeTab === 'axes' && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label className="text-sm font-medium">X-Axis</Label>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <Label className="text-xs text-muted-foreground">Title</Label>
                    <Input
                      value={customization.xAxis?.title ?? ''}
                      onChange={(e) => updateCustomization({
                        xAxis: { ...customization.xAxis, title: e.target.value }
                      })}
                      placeholder="X-Axis title"
                      className="h-8 text-sm"
                    />
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Label Angle</Label>
                    <Select
                      value={String(customization.xAxis?.labelAngle ?? 0)}
                      onValueChange={(v) => updateCustomization({
                        xAxis: { ...customization.xAxis, labelAngle: Number(v) }
                      })}
                    >
                      <SelectTrigger className="h-8">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {[0, -45, -90, 45, 90].map((angle) => (
                          <SelectItem key={angle} value={String(angle)}>
                            {angle}°
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <Label className="text-sm font-medium">Y-Axis</Label>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <Label className="text-xs text-muted-foreground">Title</Label>
                    <Input
                      value={customization.yAxis?.title ?? ''}
                      onChange={(e) => updateCustomization({
                        yAxis: { ...customization.yAxis, title: e.target.value }
                      })}
                      placeholder="Y-Axis title"
                      className="h-8 text-sm"
                    />
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Format</Label>
                    <Select
                      value={customization.yAxis?.format || '__auto__'}
                      onValueChange={(v) => updateCustomization({
                        yAxis: { ...customization.yAxis, format: v === '__auto__' ? undefined : v }
                      })}
                    >
                      <SelectTrigger className="h-8">
                        <SelectValue placeholder="Auto" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__auto__">Auto</SelectItem>
                        <SelectItem value=",.0f">1,234</SelectItem>
                        <SelectItem value=",.2f">1,234.56</SelectItem>
                        <SelectItem value=".0%">12%</SelectItem>
                        <SelectItem value=".1%">12.3%</SelectItem>
                        <SelectItem value="$,.0f">$1,234</SelectItem>
                        <SelectItem value="$,.2f">$1,234.56</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Legend Tab */}
          {activeTab === 'legend' && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Legend Position</Label>
                <Select
                  value={customization.legendPosition ?? 'right'}
                  onValueChange={(v) => updateCustomization({ legendPosition: v as LegendPosition })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {LEGEND_POSITIONS.map(({ value, label }) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Legend Title</Label>
                <Input
                  value={customization.legendTitle ?? ''}
                  onChange={(e) => updateCustomization({ legendTitle: e.target.value })}
                  placeholder="Optional legend title..."
                />
              </div>
            </div>
          )}

          {/* Theme Tab */}
          {activeTab === 'theme' && (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Chart Theme</Label>
                <Select
                  value={customization.theme ?? 'quartz'}
                  onValueChange={(v) => updateCustomization({ theme: v as ChartTheme })}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {THEMES.map(({ value, label }) => (
                      <SelectItem key={value} value={value}>
                        {label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Background Color</Label>
                <div className="flex gap-2">
                  <Input
                    type="color"
                    value={customization.backgroundColor ?? '#ffffff'}
                    onChange={(e) => updateCustomization({ backgroundColor: e.target.value })}
                    className="w-12 h-8 p-1 cursor-pointer"
                  />
                  <Input
                    value={customization.backgroundColor ?? ''}
                    onChange={(e) => updateCustomization({ backgroundColor: e.target.value })}
                    placeholder="transparent"
                    className="flex-1"
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}

// Color palette selector sub-component
const ColorPaletteSelector: React.FC<{
  selected?: ColorPalette
  onSelect: (palette: ColorPalette) => void
}> = ({ selected, onSelect }) => {
  const groupedPalettes = {
    'Categorical': COLOR_PALETTES.filter(p => p.type === 'categorical'),
    'Colorblind Friendly': COLOR_PALETTES.filter(p => p.type === 'colorblind'),
    'Sequential': COLOR_PALETTES.filter(p => p.type === 'sequential'),
  }

  return (
    <div className="space-y-4">
      {Object.entries(groupedPalettes).map(([group, palettes]) => (
        <div key={group} className="space-y-2">
          <Label className="text-xs text-muted-foreground uppercase tracking-wide">
            {group}
          </Label>
          <div className="grid grid-cols-2 gap-2">
            {palettes.map((palette) => (
              <button
                key={palette.id}
                onClick={() => onSelect(palette.id)}
                className={`p-2 rounded border text-left transition-colors ${selected === palette.id
                  ? 'border-primary bg-primary/5'
                  : 'border-muted hover:border-primary/50'
                  }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium truncate">{palette.name}</span>
                  {selected === palette.id && <Check className="h-3 w-3 text-primary" />}
                </div>
                <div className="flex gap-0.5">
                  {palette.colors.slice(0, 6).map((color, i) => (
                    <div
                      key={i}
                      className="h-3 flex-1 rounded-sm"
                      style={{ backgroundColor: color }}
                    />
                  ))}
                </div>
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
