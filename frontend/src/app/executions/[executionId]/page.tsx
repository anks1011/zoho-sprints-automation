"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { getExecution, resumeExecution, ApiError } from "@/lib/api-client";
import { ExecutionRecord, CreationResult } from "@/lib/types";

interface PageProps {
  params: Promise<{ executionId: string }>;
}

export default function ExecutionDetailPage({ params }: PageProps) {
  const resolvedParams = use(params);
  const executionId = resolvedParams.executionId;

  const [record, setRecord] = useState<ExecutionRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resuming, setResuming] = useState(false);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [showRawJson, setShowRawJson] = useState(false);

  const loadData = () => {
    setLoading(true);
    setError(null);
    getExecution(executionId)
      .then((data) => setRecord(data))
      .catch((err) => {
        setError(
          err instanceof ApiError
            ? err.detail
            : (err as Error)?.message || "Failed to load execution details."
        );
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
  }, [executionId]);

  const handleCopyId = () => {
    navigator.clipboard.writeText(executionId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleResume = async () => {
    if (!record) return;
    setResuming(true);
    setError(null);
    setActionSuccess(null);
    try {
      const res: CreationResult = await resumeExecution(executionId);
      setActionSuccess(
        `Resume completed: ${res.created_tasks} created, ${res.failed_tasks} failed out of ${res.total_tasks} tasks.`
      );
      loadData();
    } catch (err: unknown) {
      setError(
        err instanceof ApiError
          ? err.detail
          : (err as Error)?.message || "Failed to resume execution."
      );
    } finally {
      setResuming(false);
    }
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status.toUpperCase()) {
      case "COMPLETED":
        return "badge badge-success";
      case "PARTIAL":
        return "badge badge-warning";
      case "FAILED":
        return "badge badge-error";
      case "DRY_RUN":
        return "badge badge-neutral";
      default:
        return "badge badge-neutral";
    }
  };

  const isPartialOrFailed =
    record && (record.status === "PARTIAL" || record.failed_count > 0);

  return (
    <div className="page-container">
      {/* Navigation Breadcrumb */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "24px",
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <Link
            href="/executions"
            className="btn btn-secondary"
            style={{ fontSize: "12px", padding: "6px 12px" }}
          >
            ← All Executions
          </Link>
          <span style={{ color: "var(--text-muted)", fontSize: "13px" }}>/</span>
          <span style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
            Execution Detail
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          {record?.plan_id && (
            <Link
              href={`/plans/${record.plan_id}`}
              className="btn btn-secondary"
              style={{ fontSize: "12px", padding: "6px 12px" }}
            >
              View Plan ({record.plan_id}) →
            </Link>
          )}
          {record?.story_id && (
            <Link
              href={`/stories/${record.story_id}`}
              className="btn btn-secondary"
              style={{ fontSize: "12px", padding: "6px 12px" }}
            >
              View Story ({record.story_id}) →
            </Link>
          )}
          <button
            onClick={loadData}
            disabled={loading}
            className="btn btn-secondary"
            style={{ fontSize: "12px", padding: "6px 12px" }}
          >
            {loading ? "Refreshing..." : "Refresh ↺"}
          </button>
        </div>
      </div>

      {/* Success banner */}
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

      {/* Error banner */}
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

      {/* Loading Skeleton */}
      {loading && !record && (
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div className="skeleton" style={{ height: "140px", borderRadius: "var(--radius-lg)" }} />
          <div className="skeleton" style={{ height: "260px", borderRadius: "var(--radius-lg)" }} />
        </div>
      )}

      {/* Execution Detail Content */}
      {record && (
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          {/* Main Summary Header Card */}
          <div className="card">
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                flexWrap: "wrap",
                gap: "16px",
                marginBottom: "20px",
              }}
            >
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
                  <span className={getStatusBadgeClass(record.status)}>{record.status}</span>
                  <h1
                    style={{
                      fontSize: "20px",
                      fontWeight: "700",
                      color: "#ffffff",
                      fontFamily: "var(--font-mono)",
                    }}
                  >
                    {record.execution_id}
                  </h1>
                  <button
                    onClick={handleCopyId}
                    className="btn btn-secondary"
                    style={{ fontSize: "11px", padding: "2px 8px" }}
                    title="Copy Execution ID"
                  >
                    {copied ? "✓ Copied" : "Copy"}
                  </button>
                </div>
                <div style={{ fontSize: "13px", color: "var(--text-muted)" }}>
                  Initiated on {new Date(record.created_at).toLocaleString()} • Last updated{" "}
                  {new Date(record.updated_at).toLocaleString()}
                </div>
              </div>

              {isPartialOrFailed && (
                <button
                  onClick={handleResume}
                  disabled={resuming}
                  className="btn btn-primary"
                  style={{
                    backgroundColor: "var(--color-primary)",
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  {resuming ? "Resuming..." : "⚡ Resume Failed / Pending Tasks"}
                </button>
              )}
            </div>

            {/* Context Meta Grid */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                gap: "12px",
                padding: "16px",
                background: "rgba(255, 255, 255, 0.02)",
                borderRadius: "var(--radius-md)",
                border: "1px solid var(--border-color)",
              }}
            >
              <div>
                <div style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase" }}>
                  Story ID
                </div>
                <div style={{ fontSize: "13px", fontWeight: "600", color: "#ffffff", marginTop: "2px" }}>
                  {record.story_id ? (
                    <Link
                      href={`/stories/${record.story_id}`}
                      style={{ color: "var(--color-primary)", textDecoration: "none" }}
                    >
                      {record.story_id} ↗
                    </Link>
                  ) : (
                    "-"
                  )}
                </div>
              </div>

              <div>
                <div style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase" }}>
                  Plan ID
                </div>
                <div style={{ fontSize: "13px", fontWeight: "600", color: "#ffffff", marginTop: "2px" }}>
                  {record.plan_id ? (
                    <Link
                      href={`/plans/${record.plan_id}`}
                      style={{ color: "var(--color-primary)", textDecoration: "none" }}
                    >
                      {record.plan_id} ↗
                    </Link>
                  ) : (
                    "-"
                  )}
                </div>
              </div>

              <div>
                <div style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase" }}>
                  Project ID
                </div>
                <div
                  style={{
                    fontSize: "13px",
                    fontFamily: "var(--font-mono)",
                    color: "var(--text-secondary)",
                    marginTop: "2px",
                  }}
                >
                  {record.project_id || "-"}
                </div>
              </div>

              <div>
                <div style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase" }}>
                  Sprint ID
                </div>
                <div
                  style={{
                    fontSize: "13px",
                    fontFamily: "var(--font-mono)",
                    color: "var(--text-secondary)",
                    marginTop: "2px",
                  }}
                >
                  {record.sprint_id || "-"}
                </div>
              </div>
            </div>
          </div>

          {/* Metric KPI Cards */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              gap: "16px",
            }}
          >
            <div className="card" style={{ padding: "16px" }}>
              <div style={{ fontSize: "12px", color: "var(--text-muted)", marginBottom: "4px" }}>
                Total Tasks
              </div>
              <div style={{ fontSize: "28px", fontWeight: "800", color: "#ffffff" }}>
                {record.tasks.length}
              </div>
            </div>

            <div
              className="card"
              style={{
                padding: "16px",
                borderColor: "rgba(16, 185, 129, 0.3)",
                background: "rgba(16, 185, 129, 0.04)",
              }}
            >
              <div style={{ fontSize: "12px", color: "#6ee7b7", marginBottom: "4px" }}>
                Created in Zoho
              </div>
              <div style={{ fontSize: "28px", fontWeight: "800", color: "var(--color-success)" }}>
                {record.created_count}
              </div>
            </div>

            <div
              className="card"
              style={{
                padding: "16px",
                borderColor:
                  record.failed_count > 0 ? "rgba(239, 68, 68, 0.4)" : "var(--border-color)",
                background:
                  record.failed_count > 0 ? "rgba(239, 68, 68, 0.06)" : "transparent",
              }}
            >
              <div
                style={{
                  fontSize: "12px",
                  color: record.failed_count > 0 ? "#fca5a5" : "var(--text-muted)",
                  marginBottom: "4px",
                }}
              >
                Failed
              </div>
              <div
                style={{
                  fontSize: "28px",
                  fontWeight: "800",
                  color: record.failed_count > 0 ? "var(--color-error)" : "var(--text-muted)",
                }}
              >
                {record.failed_count}
              </div>
            </div>

            <div className="card" style={{ padding: "16px" }}>
              <div style={{ fontSize: "12px", color: "var(--text-muted)", marginBottom: "4px" }}>
                Pending / Skipped
              </div>
              <div style={{ fontSize: "28px", fontWeight: "800", color: "var(--color-warning)" }}>
                {record.pending_count}
              </div>
            </div>
          </div>

          {/* Subtasks Execution Table Card */}
          <div className="card">
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "16px",
              }}
            >
              <h2 style={{ fontSize: "16px", fontWeight: "700", color: "#ffffff" }}>
                Subtask Creation Audit ({record.tasks.length})
              </h2>
              <button
                onClick={() => setShowRawJson(!showRawJson)}
                className="btn btn-secondary"
                style={{ fontSize: "11px", padding: "4px 10px" }}
              >
                {showRawJson ? "Hide Raw JSON" : "View Raw JSON"}
              </button>
            </div>

            {showRawJson && (
              <pre
                style={{
                  background: "#080c14",
                  padding: "16px",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border-color)",
                  fontSize: "12px",
                  color: "#93c5fd",
                  overflowX: "auto",
                  maxHeight: "350px",
                  marginBottom: "20px",
                }}
              >
                {JSON.stringify(record, null, 2)}
              </pre>
            )}

            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border-color)", textAlign: "left" }}>
                    <th style={{ padding: "12px 10px", color: "var(--text-muted)", width: "60px" }}>
                      Type
                    </th>
                    <th style={{ padding: "12px 10px", color: "var(--text-muted)" }}>
                      Task Title
                    </th>
                    <th style={{ padding: "12px 10px", color: "var(--text-muted)", width: "110px" }}>
                      Status
                    </th>
                    <th style={{ padding: "12px 10px", color: "var(--text-muted)", width: "180px" }}>
                      Zoho Task ID
                    </th>
                    <th style={{ padding: "12px 10px", color: "var(--text-muted)", width: "180px" }}>
                      Attempted At
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {record.tasks.map((task, idx) => {
                    const isCreated = task.status === "CREATED";
                    const isFailed = task.status === "FAILED";
                    return (
                      <tr
                        key={idx}
                        style={{
                          borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                          background: isFailed ? "rgba(239, 68, 68, 0.04)" : "transparent",
                        }}
                      >
                        <td style={{ padding: "12px 10px" }}>
                          <span
                            className={task.task_type === "FE" ? "badge badge-fe" : "badge badge-be"}
                            style={{ fontSize: "11px" }}
                          >
                            {task.task_type}
                          </span>
                        </td>
                        <td style={{ padding: "12px 10px" }}>
                          <div style={{ fontWeight: "600", color: "#ffffff" }}>
                            {task.title}
                          </div>
                          {task.error_message && (
                            <div
                              style={{
                                color: "#fca5a5",
                                fontSize: "12px",
                                marginTop: "4px",
                                padding: "4px 8px",
                                background: "rgba(239, 68, 68, 0.1)",
                                borderRadius: "4px",
                                borderLeft: "2px solid var(--color-error)",
                              }}
                            >
                              Error: {task.error_message}
                            </div>
                          )}
                        </td>
                        <td style={{ padding: "12px 10px" }}>
                          <span
                            className={
                              isCreated
                                ? "badge badge-success"
                                : isFailed
                                ? "badge badge-error"
                                : "badge badge-warning"
                            }
                            style={{ fontSize: "11px" }}
                          >
                            {task.status}
                          </span>
                        </td>
                        <td style={{ padding: "12px 10px", fontFamily: "var(--font-mono)" }}>
                          {task.zoho_task_url ? (
                            <a
                              href={task.zoho_task_url}
                              target="_blank"
                              rel="noreferrer"
                              style={{ color: "var(--color-primary)", textDecoration: "none" }}
                            >
                              {task.zoho_task_id || "View in Zoho"} ↗
                            </a>
                          ) : (
                            <span style={{ color: isCreated ? "#ffffff" : "var(--text-muted)" }}>
                              {task.zoho_task_id || "-"}
                            </span>
                          )}
                        </td>
                        <td
                          style={{
                            padding: "12px 10px",
                            color: "var(--text-muted)",
                            fontSize: "12px",
                          }}
                        >
                          {task.attempted_at ? new Date(task.attempted_at).toLocaleString() : "-"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
