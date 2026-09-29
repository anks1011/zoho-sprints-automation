"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { fetchAuthStatus } from "@/lib/api-client";
import { AuthStatus } from "@/lib/types";

export function Sidebar() {
  const pathname = usePathname();
  const [authStatus, setAuthStatus] = useState<AuthStatus | null>(null);

  useEffect(() => {
    fetchAuthStatus()
      .then((status) => setAuthStatus(status))
      .catch(() => setAuthStatus(null));
  }, []);

  const navItems = [
    {
      label: "Dashboard",
      href: "/",
      exact: true,
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect width="7" height="9" x="3" y="3" rx="1" />
          <rect width="7" height="5" x="14" y="3" rx="1" />
          <rect width="7" height="9" x="14" y="12" rx="1" />
          <rect width="7" height="5" x="3" y="16" rx="1" />
        </svg>
      ),
    },
    {
      label: "Stories",
      href: "/stories",
      exact: false,
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z" />
          <path d="M6 6h10" />
          <path d="M6 10h10" />
          <path d="M6 14h6" />
        </svg>
      ),
    },
    {
      label: "Task Creation",
      href: "/bulk",
      exact: false,
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
          <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
          <path d="m9 14 2 2 4-4" />
        </svg>
      ),
    },
    {
      label: "Activity",
      href: "/executions",
      exact: false,
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
      ),
    },
    {
      label: "Settings",
      href: "/settings",
      exact: false,
      icon: (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
          <circle cx="12" cy="12" r="3" />
        </svg>
      ),
    },
  ];

  return (
    <aside className="sidebar">
      {/* Brand Header */}
      <Link href="/" className="sidebar-logo">
        <div className="sidebar-logo-icon">ZS</div>
        <div>
          <div className="sidebar-logo-text" style={{ fontSize: "14px", fontWeight: "700", letterSpacing: "-0.01em" }}>
            Task Automation
          </div>
          <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
            Developer Tooling
          </div>
        </div>
      </Link>

      {/* Navigation links */}
      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const isActive = item.exact
            ? pathname === item.href
            : pathname === item.href || pathname?.startsWith(item.href + "/");

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`nav-item ${isActive ? "active" : ""}`}
            >
              {item.icon}
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Logged in Developer Info */}
      <div
        style={{
          padding: "16px 14px",
          borderTop: "1px solid var(--border-subtle)",
          background: "rgba(0, 0, 0, 0.15)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div
            style={{
              width: "34px",
              height: "34px",
              borderRadius: "50%",
              background: "linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "12px",
              fontWeight: "700",
              color: "#ffffff",
              flexShrink: 0,
              position: "relative",
              border: "1px solid rgba(255, 255, 255, 0.15)",
            }}
          >
            AS
            <span
              style={{
                position: "absolute",
                bottom: "-1px",
                right: "-1px",
                width: "9px",
                height: "9px",
                borderRadius: "50%",
                background: authStatus?.is_authenticated ? "var(--color-success)" : "#f59e0b",
                border: "2px solid var(--bg-secondary)",
              }}
            />
          </div>

          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontSize: "13px",
                fontWeight: "600",
                color: "#ffffff",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              Ankit Singh
            </div>
            <div
              style={{
                fontSize: "11px",
                color: "var(--text-muted)",
                fontFamily: "var(--font-mono)",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
              title="Developer Owner ID: 39713000000188256"
            >
              Owner: 39713000000188256
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
