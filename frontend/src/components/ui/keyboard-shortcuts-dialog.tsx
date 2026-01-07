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
    { keys: ['Ctrl', '/'], description: 'Show Keyboard Shortcuts' },
]

interface KeyboardShortcutsDialogProps {
    open?: boolean
    onOpenChange?: (open: boolean) => void
}

export function KeyboardShortcutsDialog({ open, onOpenChange }: KeyboardShortcutsDialogProps) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
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
