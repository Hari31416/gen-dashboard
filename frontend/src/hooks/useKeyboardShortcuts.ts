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
  SHOW_SHORTCUTS: { key: '/', ctrl: true, description: 'Show Keyboard Shortcuts' },
}
