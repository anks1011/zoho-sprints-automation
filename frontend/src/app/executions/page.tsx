"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { listExecutions, resumeExecution, ApiError } from "@/lib/api-client";
import { ExecutionRecord } from "@/lib/types";

export default function ExecutionsPage() {
  const [executions, setExecutions] = useState<ExecutionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resumingId, setResumingId] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const loadData = () => {
    setLoading(true);
    setError(null);
    listExecutions()
      .then((data) => setExecutions(data))
      .catch((err) => {
        setError(err instanceof ApiError ? err.detail : err.message || "Failed to load execution history");
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleResume = async (executionId: string) => {
    setResumingId(executionId);
    setError(null);
    setActionSuccess(null);
    try {
      const result = await resumeExecution(executionId);
      setActionSuccess(`Execution ${executionId} resumed: ${result.created_tasks}/${result.total_tasks} created.`);
      loadData();
    } catch (err: any) {
      setError(err instanceof ApiError ? err.detail : err.message || "Failed to resume execution");
    } finally {
      setResumingId(null);
    }
  };

  return (
    <div className="page-container">
      {/* Top Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "28px" }}>
        <div>
          <div style={{ fontSize: "12px", color: "var(--text-muted)", marginBottom: "4px" }}>
            AUDIT & RUNTIME LOGS
          </div>
          <h1 style={{ fontSize: "24px", fontWeight: "800", color: "#ffffff" }}>
            Task Execution History
          </h1>
        </div>
        <button onClick={loadData} className="btn btn-secondary" disabled={loading}>
          {loading ? "Refreshing..." : "Refresh Logs ↺"}
        </button>
      </div>

      {actionSuccess && (
        <div
          style={{
            background: "rgba(16, 185, 129, 0.12)",
            border: "1px solid rgba(16, 185, 129, 0.3)",
            color: "#6ee7b7",
            padding: "14px 18px",
            borderRadius: "var(--radius-md)",
            marginBottom: "24px",
            fontSize: "14px",
          }}
        >
          ✓ {actionSuccess}
        </div>
      )}

      {error && (
        <div
          style={{
            background: "rgba(239, 68, 68, 0.12)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            color: "#fca5a5",
            padding: "14px 18px",
            borderRadius: "var(--radius-md)",
            marginBottom: "24px",
            fontSize: "14px",
          }}
        >
          ⚠️ {error}
        </div>
      )}

      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div className="skeleton" style={{ height: "120px", borderRadius: "var(--radius-lg)" }} />
          <div className="skeleton" style={{ height: "120px", borderRadius: "var(--radius-lg)" }} />
        </div>
      ) : executions.length === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: "48px 24px" }}>
          <div style={{ fontSize: "40px", marginBottom: "12px" }}>📋</div>
          <h2 style={{ fontSize: "18px", fontWeight: "700", color: "#ffffff", marginBottom: "8px" }}>
            No Executions Recorded Yet
          </h2>
          <p style={{ color: "var(--text-secondary)", fontSize: "14px", marginBottom: "20px" }}>
            Execute a task plan from a Story to create subtasks in Zoho Sprints and view the record here.
          </p>
          <Link href="/" className="btn btn-primary">
            Start From Dashboard
          </Link>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          {executions.map((exec) => {
            const isPartialOrFailed = exec.status === "PARTIAL" || exec.failed_count > 0;
            return (
              <div key={exec.execution_id} className="card">
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px", flexWrap: "wrap", gap: "12px" }}>
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
                      <span
                        className={`badge ${
                          exec.status === "COMPLETED"
                            ? "badge-success"
                            : exec.status === "PARTIAL"
                            ? "badge-warning"
                            : "badge-error"
                        }`}
                      >
                        {exec.status}
                      </span>
                      <span style={{ fontFamily: "var(--font-mono)", fontSize: "13px", color: "#ffffff", fontWeight: "600" }}>
                        {exec.execution_id}
                      </span>
                      <span style={{ color: "var(--text-muted)" }}>•</span>
                      <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                        {new Date(exec.created_at).toLocaleString()}
                      </span>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: "14px", fontSize: "13px" }}>
                      <span>
                        Parent Story:{" "}
                        <Link href={`/stories/${exec.story_id}`} style={{ color: "var(--accent-primary)", textDecoration: "none" }}>
                          {exec.story_id}
                        </Link>
                      </span>
                      <span style={{ color: "var(--text-muted)" }}>•</span>
                      <span>
                        Plan:{" "}
                        <Link href={`/plans/${exec.plan_id}`} style={{ color: "var(--accent-primary)", textDecoration: "none" }}>
                          {exec.plan_id}
                        </Link>
                      </span>
                    </div>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    {isPartialOrFailed && (
                      <button
                        onClick={() => handleResume(exec.execution_id)}
                        className="btn btn-primary"
                        disabled={resumingId === exec.execution_id}
                        style={{ background: "var(--color-warning)", color: "#000", fontWeight: "700" }}
                      >
                        {resumingId === exec.execution_id ? "Resuming..." : "Resume Execution ↺"}
                      </button>
                    )}
                    <Link href={`/plans/${exec.plan_id}`} className="btn btn-secondary">
                      View Plan
                    </Link>
                  </div>
                </div>

                {/* Metrics Pill Grid */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "12px", marginBottom: "16px" }}>
                  <div style={{ background: "rgba(255, 255, 255, 0.03)", padding: "10px", borderRadius: "var(--radius-sm)", textAlign: "center" }}>
                    <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>TOTAL TASKS</div>
                    <div style={{ fontSize: "16px", fontWeight: "700", color: "#ffffff" }}>{exec.tasks.length}</div>
                  </div>
                  <div style={{ background: "rgba(16, 185, 129, 0.08)", padding: "10px", borderRadius: "var(--radius-sm)", textAlign: "center" }}>
                    <div style={{ fontSize: "11px", color: "var(--color-success)" }}>CREATED</div>
                    <div style={{ fontSize: "16px", fontWeight: "700", color: "var(--color-success)" }}>{exec.created_count}</div>
                  </div>
                  <div style={{ background: "rgba(239, 68, 68, 0.08)", padding: "10px", borderRadius: "var(--radius-sm)", textAlign: "center" }}>
                    <div style={{ fontSize: "11px", color: "var(--color-error)" }}>FAILED</div>
                    <div style={{ fontSize: "16px", fontWeight: "700", color: "var(--color-error)" }}>{exec.failed_count}</div>
                  </div>
                  <div style={{ background: "rgba(255, 255, 255, 0.03)", padding: "10px", borderRadius: "var(--radius-sm)", textAlign: "center" }}>
                    <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>PENDING</div>
                    <div style={{ fontSize: "16px", fontWeight: "700", color: "var(--text-muted)" }}>{exec.pending_count}</div>
                  </div>
                </div>

                {/* Subtask Status List */}
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {exec.tasks.map((task, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        background: "rgba(0, 0, 0, 0.25)",
                        padding: "8px 12px",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border-subtle)",
                        fontSize: "13px",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <span className={`badge ${task.task_type === "FE" ? "badge-fe" : "badge-be"}`}>
                          {task.task_type}
                        </span>
                        <span style={{ color: "#ffffff", fontWeight: "500" }}>{task.title}</span>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        {task.status === "CREATED" ? (
                          <>
                            <span className="badge badge-success" style={{ fontFamily: "var(--font-mono)", fontSize: "11px" }}>
                              ✓ ID: {task.zoho_task_id || "Created"}
                            </span>
                            {task.zoho_task_url && (
                              <a
                                href={task.zoho_task_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="btn btn-secondary"
                                style={{ padding: "3px 8px", fontSize: "11px", display: "inline-flex", alignItems: "center", gap: "3px", textDecoration: "none" }}
                                title="Open this subtask in Zoho Sprints"
                              >
                                <span>Open</span>
                                <span style={{ fontSize: "11px" }}>↗</span>
                              </a>
                            )}
                          </>
                        ) : task.status === "FAILED" ? (
                          <span className="badge badge-error" style={{ fontSize: "11px" }} title={task.error_message || ""}>
                            ✗ Failed: {task.error_message || "Error"}
                          </span>
                        ) : (
                          <span className="badge badge-neutral" style={{ fontSize: "11px" }}>{task.status}</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
