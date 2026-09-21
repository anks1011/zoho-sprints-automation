"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { fetchStory, generatePlan, ApiError } from "@/lib/api-client";
import { StoryDetails } from "@/lib/types";

interface PageProps {
  params: Promise<{ storyId: string }>;
}

export default function StoryDetailPage({ params }: PageProps) {
  const router = useRouter();
  const resolvedParams = use(params);
  const storyId = resolvedParams.storyId;

  const [story, setStory] = useState<StoryDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generationError, setGenerationError] = useState<string | null>(null);

  const loadStory = () => {
    setLoading(true);
    setError(null);
    fetchStory(storyId)
      .then((data) => {
        setStory(data);
      })
      .catch((err) => {
        if (err instanceof ApiError) {
          setError(err.detail);
        } else {
          setError(err.message || "Failed to load story details");
        }
      })
      .finally(() => setLoading(false));
  };

  const handleGeneratePlan = async () => {
    if (!story) return;
    setGenerating(true);
    setGenerationError(null);
    try {
      const plan = await generatePlan(story.id);
      router.push(`/plans/${plan.plan_id}`);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.detail : (err as Error)?.message || "Failed to generate plan.";
      setGenerationError(msg);
      setGenerating(false);
    }
  };

  useEffect(() => {
    loadStory();
  }, [storyId]);

  if (loading) {
    return (
      <div className="page-container">
        <div style={{ display: "flex", gap: "10px", marginBottom: "20px" }}>
          <div className="skeleton" style={{ width: "120px", height: "24px" }} />
          <div className="skeleton" style={{ width: "80px", height: "24px" }} />
        </div>
        <div className="skeleton" style={{ width: "70%", height: "40px", marginBottom: "30px" }} />
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "24px" }}>
          <div className="skeleton" style={{ height: "350px", borderRadius: "var(--radius-lg)" }} />
          <div className="skeleton" style={{ height: "350px", borderRadius: "var(--radius-lg)" }} />
        </div>
      </div>
    );
  }

  if (error || !story) {
    return (
      <div className="page-container">
        <Link href="/" style={{ color: "var(--accent-primary)", fontSize: "14px", textDecoration: "none", marginBottom: "24px", display: "inline-block" }}>
          ← Back to Dashboard
        </Link>
        <div
          className="card"
          style={{
            border: "1px solid rgba(239, 68, 68, 0.4)",
            background: "rgba(239, 68, 68, 0.05)",
            textAlign: "center",
            padding: "48px 24px",
          }}
        >
          <div
            style={{
              width: "56px",
              height: "56px",
              borderRadius: "50%",
              background: "rgba(239, 68, 68, 0.15)",
              color: "var(--color-error)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              margin: "0 auto 16px",
            }}
          >
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <h2 style={{ fontSize: "20px", fontWeight: "700", marginBottom: "8px", color: "#ffffff" }}>
            Story Retrieval Failed
          </h2>
          <p style={{ color: "var(--text-secondary)", fontSize: "14px", maxWidth: "480px", margin: "0 auto 24px" }}>
            {error || `Story with ID '${storyId}' could not be located in the current Zoho workspace.`}
          </p>
          <div style={{ display: "flex", gap: "12px", justifyContent: "center" }}>
            <button onClick={loadStory} className="btn btn-secondary">
              Retry
            </button>
            <Link href="/" className="btn btn-primary">
              Lookup Another Story
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container">
      {/* Top Breadcrumb & Actions */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <Link href="/" style={{ color: "var(--text-muted)", fontSize: "14px", textDecoration: "none" }}>
            Stories
          </Link>
          <span style={{ color: "var(--text-muted)" }}>/</span>
          <span style={{ color: "var(--text-highlight)", fontSize: "14px", fontFamily: "var(--font-mono)" }}>
            {story.id}
          </span>
        </div>

        <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          <button onClick={loadStory} className="btn btn-secondary" title="Refresh from Zoho Sprints" disabled={generating}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
              <path d="M3 3v5h5" />
              <path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
              <path d="M16 21h5v-5" />
            </svg>
            Refresh
          </button>
          <button
            onClick={handleGeneratePlan}
            className="btn btn-primary"
            title="Generate AI Task Plan"
            disabled={generating}
            style={{ minWidth: "180px" }}
          >
            {generating ? (
              <>
                <span className="pulse-dot" style={{ backgroundColor: "#ffffff" }} />
                <span>Generating Tasks...</span>
              </>
            ) : (
              <>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
                </svg>
                <span>Generate Task Plan</span>
              </>
            )}
          </button>
        </div>
      </div>

      {generationError && (
        <div
          style={{
            background: "rgba(239, 68, 68, 0.12)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            color: "#fca5a5",
            padding: "14px 18px",
            borderRadius: "var(--radius-md)",
            marginBottom: "20px",
            fontSize: "14px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span>⚠️ {generationError}</span>
          <button
            onClick={() => setGenerationError(null)}
            style={{ background: "none", border: "none", color: "#fca5a5", cursor: "pointer", fontSize: "16px" }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Story Header Card */}
      <div
        className="card"
        style={{
          marginBottom: "28px",
          background: "linear-gradient(135deg, rgba(22, 32, 50, 0.8) 0%, rgba(16, 23, 38, 0.9) 100%)",
        }}
      >
        <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", marginBottom: "14px" }}>
          <span className="badge badge-info" style={{ fontFamily: "var(--font-mono)" }}>
            ID: {story.id}
          </span>
          <span className="badge badge-neutral">
            Type: {story.item_type_name || "Story"}
          </span>
          <span className="badge badge-warning">
            Priority: {story.priority_name || "None"}
          </span>
          <span className="badge badge-success">
            Status: {story.status || "Open / Backlog"}
          </span>
          {story.team_id && (
            <span className="badge badge-neutral">
              Team: {story.team_id}
            </span>
          )}
        </div>

        <h1 style={{ fontSize: "24px", fontWeight: "800", color: "#ffffff", lineHeight: "1.3", marginBottom: "12px" }}>
          {story.name}
        </h1>

        <div style={{ display: "flex", gap: "24px", fontSize: "13px", color: "var(--text-muted)" }}>
          <div>
            <span style={{ color: "var(--text-secondary)" }}>Project ID:</span> {story.project_id || "Auto-resolved"}
          </div>
          <div>
            <span style={{ color: "var(--text-secondary)" }}>Sprint / Backlog:</span> {story.sprint_id || "Auto-resolved"}
          </div>
          <div>
            <span style={{ color: "var(--text-secondary)" }}>Subtasks:</span> {story.subitems.length} items
          </div>
        </div>
      </div>

      {/* Main Grid: Description & Acceptance Criteria */}
      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: "24px", marginBottom: "32px" }}>
        {/* Story Description */}
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <h2 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-highlight)" }}>
              Story Description
            </h2>
            <span className="badge badge-neutral" style={{ fontSize: "11px" }}>Cleaned Text</span>
          </div>

          <div
            style={{
              fontSize: "14px",
              lineHeight: "1.7",
              color: "var(--text-secondary)",
              whiteSpace: "pre-wrap",
              background: "rgba(10, 14, 23, 0.4)",
              padding: "18px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-subtle)",
              maxHeight: "520px",
              overflowY: "auto",
              fontFamily: "var(--font-sans)",
            }}
          >
            {story.description || "No description provided in Zoho Sprints."}
          </div>
        </div>

        {/* Acceptance Criteria */}
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
            <h2 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-highlight)" }}>
              Acceptance Criteria
            </h2>
            <span className="badge badge-info" style={{ fontSize: "11px" }}>Parsed Scenarios</span>
          </div>

          <div
            style={{
              fontSize: "13.5px",
              lineHeight: "1.6",
              color: "var(--text-secondary)",
              whiteSpace: "pre-wrap",
              background: "rgba(10, 14, 23, 0.4)",
              padding: "18px",
              borderRadius: "var(--radius-md)",
              border: "1px solid var(--border-subtle)",
              maxHeight: "520px",
              overflowY: "auto",
            }}
          >
            {story.acceptance_criteria ? (
              story.acceptance_criteria
            ) : (
              <div style={{ textAlign: "center", padding: "32px 0", color: "var(--text-muted)" }}>
                No explicit acceptance criteria detected in story fields.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Subtasks / Existing Items Table */}
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <div>
            <h2 style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-highlight)", marginBottom: "4px" }}>
              Existing Subtasks ({story.subitems.length})
            </h2>
            <p style={{ fontSize: "12px", color: "var(--text-muted)" }}>
              Subtasks already created under this story in Zoho Sprints. Used for duplicate detection.
            </p>
          </div>
          <span className="badge badge-neutral">Auto-Sync</span>
        </div>

        {story.subitems.length === 0 ? (
          <div
            style={{
              textAlign: "center",
              padding: "36px 20px",
              background: "rgba(10, 14, 23, 0.3)",
              borderRadius: "var(--radius-md)",
              border: "1px dashed var(--border-card)",
            }}
          >
            <div style={{ color: "var(--text-muted)", fontSize: "14px", marginBottom: "8px" }}>
              No subtasks have been created under this story yet.
            </div>
            <div style={{ color: "var(--text-muted)", fontSize: "12px" }}>
              When task generation runs in Phase 2, proposed tasks will be compared against this list to prevent duplicates.
            </div>
          </div>
        ) : (
          <div className="table-container">
            <table className="table">
              <thead>
                <tr>
                  <th style={{ width: "180px" }}>Subtask ID</th>
                  <th>Task Title</th>
                  <th style={{ width: "120px" }}>Type</th>
                  <th style={{ width: "120px" }}>Priority</th>
                  <th style={{ width: "120px" }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {story.subitems.map((sub) => (
                  <tr key={sub.id}>
                    <td style={{ fontFamily: "var(--font-mono)", color: "var(--accent-primary)" }}>{sub.id}</td>
                    <td style={{ fontWeight: "500", color: "var(--text-primary)" }}>{sub.name}</td>
                    <td>
                      <span className="badge badge-neutral">{sub.item_type_name || "Task"}</span>
                    </td>
                    <td>
                      <span className="badge badge-warning">{sub.priority_name || "None"}</span>
                    </td>
                    <td>
                      <span className="badge badge-success">{sub.status || "Active"}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
