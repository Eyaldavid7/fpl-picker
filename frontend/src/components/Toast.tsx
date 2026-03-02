"use client";

import { useState, useEffect, useCallback, createContext, useContext, type ReactNode } from "react";
import { CheckCircle2, XCircle, AlertCircle, Info, X } from "lucide-react";

// ---------- Types ----------

type ToastType = "success" | "error" | "warning" | "info";

interface Toast {
  id: string;
  type: ToastType;
  message: string;
  duration?: number;
}

interface ToastContextValue {
  addToast: (type: ToastType, message: string, duration?: number) => void;
  removeToast: (id: string) => void;
}

// ---------- Context ----------

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within <ToastProvider>");
  }
  return ctx;
}

// ---------- Provider ----------

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback(
    (type: ToastType, message: string, duration = 4000) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      setToasts((prev) => [...prev, { id, type, message, duration }]);
    },
    []
  );

  return (
    <ToastContext.Provider value={{ addToast, removeToast }}>
      {children}
      {/* Toast container */}
      <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 max-w-sm w-full pointer-events-none">
        {toasts.map((toast) => (
          <ToastItem key={toast.id} toast={toast} onDismiss={removeToast} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

// ---------- Toast Item ----------

const typeConfig: Record<ToastType, { icon: typeof CheckCircle2; containerClass: string }> = {
  success: {
    icon: CheckCircle2,
    containerClass: "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
  },
  error: {
    icon: XCircle,
    containerClass: "border-red-500/30 bg-red-500/10 text-red-300",
  },
  warning: {
    icon: AlertCircle,
    containerClass: "border-amber-500/30 bg-amber-500/10 text-amber-300",
  },
  info: {
    icon: Info,
    containerClass: "border-blue-500/30 bg-blue-500/10 text-blue-300",
  },
};

function ToastItem({
  toast,
  onDismiss,
}: {
  toast: Toast;
  onDismiss: (id: string) => void;
}) {
  const [exiting, setExiting] = useState(false);
  const cfg = typeConfig[toast.type];
  const Icon = cfg.icon;

  useEffect(() => {
    if (!toast.duration) return;
    const exitTimer = setTimeout(() => setExiting(true), toast.duration - 300);
    const removeTimer = setTimeout(() => onDismiss(toast.id), toast.duration);
    return () => {
      clearTimeout(exitTimer);
      clearTimeout(removeTimer);
    };
  }, [toast.id, toast.duration, onDismiss]);

  return (
    <div
      className={`pointer-events-auto flex items-start gap-3 rounded-lg border p-4 shadow-xl backdrop-blur-sm transition-all duration-300 ${
        cfg.containerClass
      } ${exiting ? "opacity-0 translate-x-4" : "opacity-100 translate-x-0 animate-toast-in"}`}
    >
      <Icon className="h-5 w-5 shrink-0 mt-0.5" />
      <p className="flex-1 text-sm font-medium">{toast.message}</p>
      <button
        onClick={() => {
          setExiting(true);
          setTimeout(() => onDismiss(toast.id), 300);
        }}
        className="shrink-0 opacity-60 hover:opacity-100 transition-opacity"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
