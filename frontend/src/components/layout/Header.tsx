"use client";

import { useEffect, useState } from "react";
import { fetchAuthStatus } from "@/lib/api-client";
import { AuthStatus } from "@/lib/types";
import { SprintStoryNavbarPicker } from "./SprintStoryNavbarPicker";

export function Header() {
  const [authStatus, setAuthStatus] = useState<AuthStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAuthStatus()
      .then((status) => setAuthStatus(status))
      .catch(() => setAuthStatus(null))
      .finally(() => setLoading(false));
  }, []);

  return (
    <header className="topbar">
      <SprintStoryNavbarPicker />

      <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
        {loading ? (
          <div className="skeleton" style={{ width: "140px", height: "28px", borderRadius: "9999px" }} />
        ) : authStatus?.is_authenticated ? (
          <div className="badge badge-success" title={authStatus.message}>
            <span className="pulse-dot" />
            <span>Zoho OAuth Active</span>
          </div>
        ) : (
          <div className="badge badge-error" title={authStatus?.message || "Not connected"}>
            <span>Offline / Not Authorized</span>
          </div>
        )}

        <div className="badge badge-neutral" style={{ fontFamily: "var(--font-mono)" }}>
          nopaperforms
        </div>
      </div>
    </header>
  );
}
