import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { LoadingSpinner } from '@/components/ui/loading-spinner';
import { Send } from 'lucide-react';

interface PromptInputProps {
    onSubmit: (prompt: string) => void;
    isLoading: boolean;
}

export const PromptInput: React.FC<PromptInputProps> = ({ onSubmit, isLoading }) => {
    const [prompt, setPrompt] = useState("");

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (prompt.trim() && !isLoading) {
            onSubmit(prompt);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e as any);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="relative w-full max-w-3xl mx-auto">
            <div className="relative rounded-xl border bg-background shadow-sm focus-within:ring-1 focus-within:ring-ring transition-all">
                <Textarea
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Describe the dashboard you want to create (e.g., 'Analyze sales performance by region for the last 6 months')..."
                    className="min-h-[80px] w-full resize-none border-0 bg-transparent py-4 pl-4 pr-14 focus-visible:ring-0 placeholder:text-muted-foreground/60"
                />
                <div className="absolute right-2 bottom-2">
                    <Button
                        type="submit"
                        size="icon"
                        disabled={!prompt.trim() || isLoading}
                        className={!prompt.trim() ? "opacity-50" : ""}
                    >
                        {isLoading ? <LoadingSpinner className="h-4 w-4" /> : <Send className="h-4 w-4" />}
                    </Button>
                </div>
            </div>
        </form>
    );
};
