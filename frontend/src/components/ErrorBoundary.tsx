"use client";

import { Component, type ReactNode, type ErrorInfo } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * React Error Boundary that catches rendering errors and displays a friendly retry UI.
 * Wraps page sections to prevent full-page crashes.
 */
export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="fpl-card flex flex-col items-center justify-center py-12 text-center animate-fade-in">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-red-500/10 mb-4">
            <AlertTriangle className="h-7 w-7 text-red-400" />
          </div>
          <h3 className="text-lg font-semibold text-[var(--foreground)]">
            Something went wrong
          </h3>
          <p className="mt-2 text-sm text-[var(--muted-foreground)] max-w-md">
            {this.state.error?.message || "An unexpected error occurred while rendering this section."}
          </p>
          <button
            onClick={this.handleRetry}
            className="fpl-button-primary mt-4 gap-2"
          >
            <RefreshCw className="h-4 w-4" />
            Try Again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
