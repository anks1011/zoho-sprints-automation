"use client";

import React, { createContext, useContext, useState, useCallback } from "react";

export type ToastType = "success" | "error" | "warning" | "info";

export interface ToastMessage {
  id: string;
  type: ToastType;
  message: string;
}

interface ToastContextType {
  toast: (message: string, type?: ToastType) => void;
  success: (message: string) => void;
  error: (message: string) => void;
  warning: (message: string) => void;
  info: (message: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const addToast = useCallback(
    (message: string, type: ToastType = "info") => {
      const id = Math.random().toString(36).substring(2, 9);
      setToasts((prev) => [...prev, { id, type, message }]);
      setTimeout(() => {
        removeToast(id);
      }, 4000);
    },
    [removeToast]
  );

  const contextValue: ToastContextType = {
    toast: addToast,
    success: (msg: string) => addToast(msg, "success"),
    error: (msg: string) => addToast(msg, "error"),
    warning: (msg: string) => addToast(msg, "warning"),
    info: (msg: string) => addToast(msg, "info"),
  };

  const getBorderAndBg = (type: ToastType) => {
    switch (type) {
      case "success":
        return {
          bg: "rgba(16, 185, 129, 0.12)",
          border: "rgba(16, 185, 129, 0.3)",
          color: "#6ee7b7",
          icon: "✓",
        };
      case "error":
        return {
          bg: "rgba(239, 68, 68, 0.12)",
          border: "rgba(239, 68, 68, 0.3)",
          color: "#fca5a5",
          icon: "✕",
        };
      case "warning":
        return {
          bg: "rgba(245, 158, 11, 0.12)",
          border: "rgba(245, 158, 11, 0.3)",
          color: "#fde047",
          icon: "⚠",
        };
      default:
        return {
          bg: "rgba(99, 102, 241, 0.12)",
          border: "rgba(99, 102, 241, 0.3)",
          color: "#a5b4fc",
          icon: "ℹ",
        };
    }
  };

  return (
    <ToastContext.Provider value={contextValue}>
      {children}
      {/* Toast container floating at bottom right */}
      <div
        style={{
          position: "fixed",
          bottom: "24px",
          right: "24px",
          zIndex: 9999,
          display: "flex",
          flexDirection: "column",
          gap: "8px",
          pointerEvents: "none",
        }}
      >
        {toasts.map((t) => {
          const cfg = getBorderAndBg(t.type);
          return (
            <div
              key={t.id}
              style={{
                pointerEvents: "auto",
                background: "#0d131f",
                backgroundColor: cfg.bg,
                border: `1px solid ${cfg.border}`,
                color: cfg.color,
                padding: "10px 16px",
                borderRadius: "8px",
                fontSize: "13px",
                fontWeight: 500,
                display: "flex",
                alignItems: "center",
                gap: "10px",
                boxShadow: "0 8px 24px rgba(0, 0, 0, 0.5)",
                backdropFilter: "blur(8px)",
                maxWidth: "400px",
                animation: "toastIn 0.2s ease-out forwards",
              }}
            >
              <span style={{ fontWeight: 700, fontSize: "14px" }}>{cfg.icon}</span>
              <span style={{ flex: 1 }}>{t.message}</span>
              <button
                onClick={() => removeToast(t.id)}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "inherit",
                  cursor: "pointer",
                  opacity: 0.6,
                  padding: "0 4px",
                  fontSize: "12px",
                }}
                title="Dismiss"
              >
                ✕
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return ctx;
}
