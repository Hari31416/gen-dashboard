import { cn } from '@/lib/utils'

interface ProgressBarProps {
    progress: number
    message?: string
    stage?: string
    showPercentage?: boolean
    className?: string
    animated?: boolean
}

export function ProgressBar({
    progress,
    message,
    stage,
    showPercentage = true,
    className,
    animated = true,
}: ProgressBarProps) {
    const clampedProgress = Math.min(100, Math.max(0, progress))

    return (
        <div className={cn('w-full space-y-2', className)}>
            {/* Stage and message */}
            <div className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                    {stage && (
                        <span className="font-medium text-primary capitalize">
                            {stage.replace('_', ' ')}
                        </span>
                    )}
                    {message && (
                        <span className="text-muted-foreground">{message}</span>
                    )}
                </div>
                {showPercentage && (
                    <span className="font-mono text-xs text-muted-foreground">
                        {clampedProgress}%
                    </span>
                )}
            </div>

            {/* Progress bar */}
            <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                <div
                    className={cn(
                        'h-full bg-primary rounded-full transition-all duration-300 ease-out',
                        animated && progress < 100 && 'animate-pulse'
                    )}
                    style={{ width: `${clampedProgress}%` }}
                />
            </div>
        </div>
    )
}
