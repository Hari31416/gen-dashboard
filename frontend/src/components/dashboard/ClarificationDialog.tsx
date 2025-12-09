import React, { useState } from 'react';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { HelpCircle } from 'lucide-react';

interface ClarificationDialogProps {
    isOpen: boolean;
    question: string;
    onSubmit: (response: string) => void;
    onClose: () => void;
}

export const ClarificationDialog: React.FC<ClarificationDialogProps> = ({
    isOpen,
    question,
    onSubmit,
    onClose,
}) => {
    const [input, setInput] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);

    const handleSubmit = () => {
        if (!input.trim()) return;
        setIsSubmitting(true);
        onSubmit(input.trim());
        setInput('');
        setIsSubmitting(false);
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
        }
    };

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <HelpCircle className="h-5 w-5 text-primary" />
                        Clarification Needed
                    </DialogTitle>
                    <DialogDescription className="text-base pt-2">
                        {question}
                    </DialogDescription>
                </DialogHeader>

                <div className="py-4">
                    <Textarea
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="Please provide more details..."
                        className="min-h-[100px] resize-none"
                        autoFocus
                    />
                </div>

                <DialogFooter className="gap-2 sm:gap-0">
                    <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
                        Cancel
                    </Button>
                    <Button 
                        onClick={handleSubmit} 
                        disabled={!input.trim() || isSubmitting}
                    >
                        Submit
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};
