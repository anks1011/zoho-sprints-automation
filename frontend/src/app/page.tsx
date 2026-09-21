"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

export default function DashboardPage() {
  const router = useRouter();
  const [storyId, setStoryId] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const clean = storyId.trim();
    if (clean) {
      router.push(`/stories/${clean}`);
    }
  };

  return (
    <div className="page-container">
      {/* Hero Section */}
      <div
        style={{
          background: "linear-gradient(135deg, rgba(99, 102, 241, 0.12) 0%, rgba(168, 85, 247, 0.05) 100%)",
          border: "1px solid var(--border-card)",
          borderRadius: "var(--radius-lg)",
          padding: "40px",
          marginBottom: "32px",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div style={{ maxWidth: "700px" }}>
          <div className="badge badge-info" style={{ marginBottom: "16px" }}>
            Phase 1 · Read-Only Story Inspection
          </div>
          <h1 style={{ fontSize: "32px", fontWeight: "800", letterSpacing: "-0.03em", marginBottom: "12px" }}>
            Zoho Sprints AI Story-to-Tasks Automation
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "16px", lineHeight: "1.6", marginBottom: "28px" }}>
            Seamlessly fetch parent stories from Zoho Sprints, review acceptance criteria, inspect existing subtasks,
            and preview production-ready AI task plans with strict FE/BE boundaries.
          </p>

          <form onSubmit={handleSubmit} style={{ display: "flex", gap: "12px", maxWidth: "560px" }}>
            <input
              type="text"
              className="input"
              placeholder="Enter Zoho Sprints Story ID (e.g. 39713000007827664)..."
              value={storyId}
              onChange={(e) => setStoryId(e.target.value)}
              style={{ fontSize: "15px" }}
            />
            <button type="submit" className="btn btn-primary" style={{ whiteSpace: "nowrap" }}>
              Inspect Story →
            </button>
          </form>
        </div>
      </div>

      {/* Featured / Active Story Card */}
      <div style={{ marginBottom: "36px" }}>
        <h2 style={{ fontSize: "18px", fontWeight: "700", marginBottom: "16px", color: "var(--text-highlight)" }}>
          Active Stories in Sprint / Backlog
        </h2>
        <div
          className="card"
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            background: "rgba(22, 32, 50, 0.6)",
            border: "1px solid rgba(99, 102, 241, 0.3)",
          }}
        >
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
              <span className="badge badge-info" style={{ fontFamily: "var(--font-mono)" }}>
                ID: 39713000007827664
              </span>
              <span className="badge badge-neutral">Pre-Admissions</span>
              <span className="badge badge-warning">Priority: None</span>
            </div>
            <h3 style={{ fontSize: "16px", fontWeight: "600", color: "#ffffff", marginBottom: "4px" }}>
              Pre-Admissions Bulk CSV Import | Story 2 | Download the Sample CSV Template
            </h3>
            <p style={{ color: "var(--text-muted)", fontSize: "13px" }}>
              Project: Nexeo Planned Tasks (39713000006643091) · Sprint: 39713000007785711
            </p>
          </div>

          <Link href="/stories/39713000007827664" className="btn btn-primary">
            View Story Details →
          </Link>
        </div>
      </div>

      {/* Architecture Highlights Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: "20px" }}>
        <div className="card">
          <div
            style={{
              width: "40px",
              height: "40px",
              borderRadius: "10px",
              background: "rgba(99, 102, 241, 0.15)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              marginBottom: "16px",
              color: "var(--accent-primary)",
            }}
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
              <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
              <line x1="12" y1="22.08" x2="12" y2="12" />
            </svg>
          </div>
          <h4 style={{ fontSize: "15px", fontWeight: "700", marginBottom: "6px" }}>Reused Python Services</h4>
          <p style={{ color: "var(--text-secondary)", fontSize: "13px", lineHeight: "1.5" }}>
            Directly invokes existing `StoryService`, `AIStoryAnalyzer`, and `TaskGenerator` without any duplicated frontend business logic.
          </p>
        </div>

        <div className="card">
          <div
            style={{
              width: "40px",
              height: "40px",
              borderRadius: "10px",
              background: "rgba(16, 185, 129, 0.15)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              marginBottom: "16px",
              color: "var(--color-success)",
            }}
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
          </div>
          <h4 style={{ fontSize: "15px", fontWeight: "700", marginBottom: "6px" }}>Zero Secret Leakage</h4>
          <p style={{ color: "var(--text-secondary)", fontSize: "13px", lineHeight: "1.5" }}>
            Zoho client credentials, OAuth refresh tokens, and OpenAI keys stay securely on the server. The client only sees sanitized metadata.
          </p>
        </div>

        <div className="card">
          <div
            style={{
              width: "40px",
              height: "40px",
              borderRadius: "10px",
              background: "rgba(245, 158, 11, 0.15)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              marginBottom: "16px",
              color: "var(--color-warning)",
            }}
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <h4 style={{ fontSize: "15px", fontWeight: "700", marginBottom: "6px" }}>Dry-Run & Confirmation</h4>
          <p style={{ color: "var(--text-secondary)", fontSize: "13px", lineHeight: "1.5" }}>
            All task generation is strictly preview-first. Writes to Zoho Sprints require explicit user confirmation and provide full resume support.
          </p>
        </div>
      </div>
    </div>
  );
}
