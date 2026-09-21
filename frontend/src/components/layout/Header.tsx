"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchAuthStatus } from "@/lib/api-client";
import { AuthStatus } from "@/lib/types";

export function Header() {
  const router = useRouter();
  const [searchInput, setSearchInput] = useState("");
  const [authStatus, setAuthStatus] = useState<AuthStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAuthStatus()
      .then((status) => setAuthStatus(status))
      .catch(() => setAuthStatus(null))
      .finally(() => setLoading(false));
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = searchInput.trim();
    if (clean) {
      router.push(`/stories/${clean}`);
    }
  };

  return (
    <header className="topbar">
      <form onSubmit={handleSearch} style={{ display: "flex", alignItems: "center", gap: "10px", width: "420px" }}>
        <div style={{ position: "relative", width: "100%" }}>
          <input
            type="text"
            className="input"
            placeholder="Enter Story ID (e.g. 39713000007827664)..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            style={{ paddingLeft: "36px", height: "38px" }}
          />
          <svg
            style={{ position: "absolute", left: "12px", top: "11px", color: "var(--text-muted)" }}
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" />
          </svg>
        </div>
        <button type="submit" className="btn btn-secondary" style={{ padding: "8px 14px", height: "38px" }}>
          Lookup
        </button>
      </form>

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
