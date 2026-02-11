# Chart Customization

Beyond AI-driven refinements, users can manually fine-tune charts through the **Chart Customization Panel**.

## Key Features
- **Color Palettes**: Choose from Categorical (e.g., Tableau 10), Color-blind friendly (e.g., Viridis), or Sequential palettes.
- **Text & Labels**: Update chart titles, subtitles, and axis labels in-place.
- **Legend Control**: Change the position or hide the legend entirely.
- **Theme Presets**: Switch between presets like `quartz`, `vox`, `ggplot2`, and `powerbi`.

## Implementation Detail
The customization logic works by applying a **client-side override** to the generated Vega-Lite spec.
1.  User makes a change in the `ChartCustomizationPanel`.
2.  The `applyCustomization` utility merges the user settings into the `config` object of the spec.
3.  The change is instantly reflected in the preview.
4.  The updated configuration is persisted to the backend session via a debounced API call.

## Preservation during AI Refinement
If a user manually changes a chart color and then asks the AI to "add a title," the system is designed to preserve the manual color choice by merging the session-stored customizations back into the AI's newly generated spec.
