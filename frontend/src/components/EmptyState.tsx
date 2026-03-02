import type { LucideIcon } from "lucide-react";
import { Inbox } from "lucide-react";

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
}

/**
 * Friendly empty-state component with icon, message, and optional action button.
 * Used when no data is available (no optimization results, no players found, etc.)
 */
export default function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
}: EmptyStateProps) {
  return (
    <div className="fpl-card flex flex-col items-center justify-center py-16 text-center animate-fade-in">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-[var(--muted)]/50 mb-4">
        <Icon className="h-8 w-8 text-[var(--muted-foreground)]" />
      </div>
      <h3 className="text-lg font-semibold text-[var(--foreground)]">{title}</h3>
      {description && (
        <p className="mt-2 text-sm text-[var(--muted-foreground)] max-w-md leading-relaxed">
          {description}
        </p>
      )}
      {action && (
        <button onClick={action.onClick} className="fpl-button-primary mt-5 gap-2">
          {action.label}
        </button>
      )}
    </div>
  );
}
