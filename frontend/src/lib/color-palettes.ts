import type { ColorPalette } from '@/types/chart-customization'

export interface PaletteInfo {
  id: ColorPalette
  name: string
  colors: string[]
  type: 'categorical' | 'sequential' | 'diverging' | 'colorblind'
}

export const COLOR_PALETTES: PaletteInfo[] = [
  // Categorical palettes
  {
    id: 'category10',
    name: 'Category 10',
    colors: ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'],
    type: 'categorical',
  },
  {
    id: 'tableau10',
    name: 'Tableau 10',
    colors: ['#4e79a7', '#f28e2c', '#e15759', '#76b7b2', '#59a14f', '#edc949', '#af7aa1', '#ff9da7', '#9c755f', '#bab0ab'],
    type: 'categorical',
  },
  {
    id: 'pastel1',
    name: 'Pastel',
    colors: ['#fbb4ae', '#b3cde3', '#ccebc5', '#decbe4', '#fed9a6', '#ffffcc', '#e5d8bd', '#fddaec'],
    type: 'categorical',
  },
  {
    id: 'set2',
    name: 'Set 2',
    colors: ['#66c2a5', '#fc8d62', '#8da0cb', '#e78ac3', '#a6d854', '#ffd92f', '#e5c494', '#b3b3b3'],
    type: 'categorical',
  },
  {
    id: 'dark2',
    name: 'Dark 2',
    colors: ['#1b9e77', '#d95f02', '#7570b3', '#e7298a', '#66a61e', '#e6ab02', '#a6761d', '#666666'],
    type: 'categorical',
  },
  
  // Color-blind friendly
  {
    id: 'viridis',
    name: 'Viridis (Colorblind)',
    colors: ['#440154', '#482878', '#3e4a89', '#31688e', '#26828e', '#1f9e89', '#35b779', '#6ece58', '#b5de2b', '#fde725'],
    type: 'colorblind',
  },
  {
    id: 'cividis',
    name: 'Cividis (Colorblind)',
    colors: ['#002051', '#0d346b', '#425a79', '#637a8d', '#8299a1', '#a0b6b6', '#c1d2c8', '#e3eed8', '#fdfdce'],
    type: 'colorblind',
  },
  {
    id: 'plasma',
    name: 'Plasma',
    colors: ['#0d0887', '#46039f', '#7201a8', '#9c179e', '#bd3786', '#d8576b', '#ed7953', '#fb9f3a', '#fdca26', '#f0f921'],
    type: 'colorblind',
  },
  
  // Sequential
  {
    id: 'blues',
    name: 'Blues',
    colors: ['#f7fbff', '#deebf7', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#08519c', '#08306b'],
    type: 'sequential',
  },
  {
    id: 'greens',
    name: 'Greens',
    colors: ['#f7fcf5', '#e5f5e0', '#c7e9c0', '#a1d99b', '#74c476', '#41ab5d', '#238b45', '#006d2c', '#00441b'],
    type: 'sequential',
  },
  {
    id: 'oranges',
    name: 'Oranges',
    colors: ['#fff5eb', '#fee6ce', '#fdd0a2', '#fdae6b', '#fd8d3c', '#f16913', '#d94801', '#a63603', '#7f2704'],
    type: 'sequential',
  },
  {
    id: 'purples',
    name: 'Purples',
    colors: ['#fcfbfd', '#efedf5', '#dadaeb', '#bcbddc', '#9e9ac8', '#807dba', '#6a51a3', '#54278f', '#3f007d'],
    type: 'sequential',
  },
]

export function getPaletteColors(paletteId: ColorPalette): string[] {
  const palette = COLOR_PALETTES.find(p => p.id === paletteId)
  return palette?.colors || COLOR_PALETTES[0].colors
}

export function getColorblindPalettes(): PaletteInfo[] {
  return COLOR_PALETTES.filter(p => p.type === 'colorblind')
}
