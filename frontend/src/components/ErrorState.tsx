import { AlertCircle, RefreshCw } from "lucide-react";

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  compact?: boolean;
}

/**
 * Reusable error display component with optional retry button.
 * Used in data-fetching sections when API calls fail.
 */
export default function ErrorState({
  title = "Something went wrong",
  message = "Could not load data. Make sure the backend is running and accessible.",
  onRetry,
  compact = false,
}: ErrorStateProps) {
  if (compact) {
    return (
      <div className="flex items-center gap-3 rounded-lg border border-red-500/20 bg-red-500/5 px-4 py-3 animate-fade-in">
        <AlertCircle className="h-4 w-4 shrink-0 text-red-400" />
        <p className="text-sm text-red-400 flex-1">{message}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="text-xs font-medium text-red-400 hover:text-red-300 transition-colors flex items-center gap-1"
          >
            <RefreshCw className="h-3 w-3" />
            Retry
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="fpl-card flex flex-col items-center justify-center py-12 text-center animate-fade-in">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-red-500/10 mb-4">
        <AlertCircle className="h-7 w-7 text-red-400" />
      </div>
      <h3 className="text-lg font-semibold text-[var(--foreground)]">{title}</h3>
      <p className="mt-2 text-sm text-[var(--muted-foreground)] max-w-md">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="fpl-button-primary mt-4 gap-2">
          <RefreshCw className="h-4 w-4" />
          Try Again
        </button>
      )}
    </div>
  );
}
