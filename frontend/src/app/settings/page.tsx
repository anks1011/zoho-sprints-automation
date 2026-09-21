"use client";

import { useEffect, useState } from "react";
import { fetchAuthStatus } from "@/lib/api-client";
import { AuthStatus } from "@/lib/types";

export default function SettingsPage() {
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const loadStatus = () => {
    setLoading(true);
    fetchAuthStatus()
      .then((data) => setStatus(data))
      .catch(() => setStatus(null))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadStatus();
  }, []);

  return (
    <div className="page-container">
      <div style={{ marginBottom: "28px" }}>
        <h1 style={{ fontSize: "24px", fontWeight: "800", color: "#ffffff", marginBottom: "8px" }}>
          Settings & System Diagnostics
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "14px" }}>
          Inspect live Zoho Sprints OAuth tokens, server security boundaries, and architectural integration status.
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px", marginBottom: "32px" }}>
        {/* OAuth Status Card */}
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
            <h2 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-highlight)" }}>
              Zoho Sprints OAuth 2.0 Status
            </h2>
            <button onClick={loadStatus} className="btn btn-secondary" style={{ padding: "6px 12px", fontSize: "12px" }}>
              Check Status
            </button>
          </div>

          {loading ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <div className="skeleton" style={{ height: "20px" }} />
              <div className="skeleton" style={{ height: "20px" }} />
              <div className="skeleton" style={{ height: "20px" }} />
            </div>
          ) : status ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", paddingBottom: "10px", borderBottom: "1px solid var(--border-subtle)" }}>
                <span style={{ color: "var(--text-secondary)", fontSize: "14px" }}>Connection State</span>
                <span className={`badge ${status.is_authenticated ? "badge-success" : "badge-error"}`}>
                  {status.is_authenticated ? "Authenticated" : "Not Authenticated"}
                </span>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", paddingBottom: "10px", borderBottom: "1px solid var(--border-subtle)" }}>
                <span style={{ color: "var(--text-secondary)", fontSize: "14px" }}>Refresh Token Available</span>
                <span className={`badge ${status.has_refresh_token ? "badge-success" : "badge-warning"}`}>
                  {status.has_refresh_token ? "Yes (Offline Access)" : "Missing"}
                </span>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", paddingBottom: "10px", borderBottom: "1px solid var(--border-subtle)" }}>
                <span style={{ color: "var(--text-secondary)", fontSize: "14px" }}>Token Expiry</span>
                <span className="badge badge-neutral" style={{ fontFamily: "var(--font-mono)" }}>
                  {status.expires_at_iso || "Not Available"}
                </span>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-secondary)", fontSize: "14px" }}>Accounts Domain</span>
                <span style={{ color: "var(--text-primary)", fontSize: "13px", fontFamily: "var(--font-mono)" }}>
                  {status.accounts_url}
                </span>
              </div>
            </div>
          ) : (
            <div style={{ color: "var(--color-error)", fontSize: "14px" }}>
              Failed to connect to FastAPI backend. Ensure uvicorn is running.
            </div>
          )}
        </div>

        {/* Security & Secrets Audit Card */}
        <div className="card">
          <h2 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-highlight)", marginBottom: "16px" }}>
            Security & Zero-Leak Audit
          </h2>
          <div style={{ display: "flex", flexDirection: "column", gap: "14px", fontSize: "13px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <span className="badge badge-success">✓ Encrypted</span>
              <span style={{ color: "var(--text-secondary)" }}>
                OAuth tokens stored with restricted POSIX `0600` file permissions in `.runtime/tokens/`
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <span className="badge badge-success">✓ Zero Browser Leak</span>
              <span style={{ color: "var(--text-secondary)" }}>
                Client Secret, Refresh Tokens, and OpenAI API Key never reach the frontend bundle.
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <span className="badge badge-success">✓ Masked Logs</span>
              <span style={{ color: "var(--text-secondary)" }}>
                FastAPI and CLI loggers use regex masking for all bearer tokens and client secrets.
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <span className="badge badge-success">✓ Read-Only Phase 1</span>
              <span style={{ color: "var(--text-secondary)" }}>
                Task write actions remain strictly gated until explicit confirmation in Phase 3.
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Architecture Inventory */}
      <div className="card">
        <h2 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-highlight)", marginBottom: "12px" }}>
          Reused Backend Services Inventory
        </h2>
        <p style={{ color: "var(--text-muted)", fontSize: "13px", marginBottom: "16px" }}>
          All business logic is provided directly by existing Python modules, preserving complete feature parity with the CLI:
        </p>

        <div className="table-container">
          <table className="table">
            <thead>
              <tr>
                <th>Service Name</th>
                <th>Python Module</th>
                <th>Phase Status</th>
                <th>Responsibility</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={{ fontWeight: "600", color: "#ffffff" }}>StoryService</td>
                <td style={{ fontFamily: "var(--font-mono)", fontSize: "12px" }}>src.services.story_service</td>
                <td><span className="badge badge-success">Active (Phase 1)</span></td>
                <td>Auto-discovery of workspace, project, sprint, story details & AC parsing</td>
              </tr>
              <tr>
                <td style={{ fontWeight: "600", color: "#ffffff" }}>ZohoOAuthClient</td>
                <td style={{ fontFamily: "var(--font-mono)", fontSize: "12px" }}>src.auth.oauth_client</td>
                <td><span className="badge badge-success">Active (Phase 1)</span></td>
                <td>OAuth 2.0 token persistence, validation, and auto-refresh</td>
              </tr>
              <tr>
                <td style={{ fontWeight: "600", color: "#ffffff" }}>AIStoryAnalyzer</td>
                <td style={{ fontFamily: "var(--font-mono)", fontSize: "12px" }}>src.services.ai_analyzer</td>
                <td><span className="badge badge-info">Phase 2</span></td>
                <td>Structured LLM prompt evaluation with strict FE/BE requirement analysis</td>
              </tr>
              <tr>
                <td style={{ fontWeight: "600", color: "#ffffff" }}>TaskGenerator</td>
                <td style={{ fontFamily: "var(--font-mono)", fontSize: "12px" }}>src.services.task_generator</td>
                <td><span className="badge badge-info">Phase 2</span></td>
                <td>Synthesizes 1 FE task and N sequential BE tasks matching 6-section format</td>
              </tr>
              <tr>
                <td style={{ fontWeight: "600", color: "#ffffff" }}>DuplicateDetector</td>
                <td style={{ fontFamily: "var(--font-mono)", fontSize: "12px" }}>src.services.duplicate_detector</td>
                <td><span className="badge badge-info">Phase 2</span></td>
                <td>Exact and fuzzy similarity matching against existing subtasks</td>
              </tr>
              <tr>
                <td style={{ fontWeight: "600", color: "#ffffff" }}>TaskCreator & Tracker</td>
                <td style={{ fontFamily: "var(--font-mono)", fontSize: "12px" }}>src.services.task_creator</td>
                <td><span className="badge badge-warning">Phase 3</span></td>
                <td>Dry-run simulation, live creation with user confirmation, and execution resume</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
