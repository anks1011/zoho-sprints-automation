"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { listExecutions, resumeExecution, ApiError } from "@/lib/api-client";
import { ExecutionRecord } from "@/lib/types";
import { useToast } from "@/components/ui/Toast";

export default function ExecutionsPage() {
  const toast = useToast();

  const [executions, setExecutions] = useState<ExecutionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resumingId, setResumingId] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Filters
  const [searchStoryId, setSearchStoryId] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [dateFilter, setDateFilter] = useState("ALL");

  const loadData = () => {
    setLoading(true);
    setError(null);
    listExecutions()
      .then((data) => setExecutions(data))
      .catch((err) => {
        setError(err instanceof ApiError ? err.detail : err.message || "Failed to load execution history.");
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
      const msg = `Execution ${executionId} resumed: ${result.created_tasks}/${result.total_tasks} created.`;
      setActionSuccess(msg);
      toast.success(msg);
      loadData();
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.detail : (err as Error)?.message || "Failed to resume execution";
      setError(msg);
      toast.error(msg);
    } finally {
      setResumingId(null);
    }
  };

  // Filtered executions
  const filteredExecutions = useMemo(() => {
    return executions.filter((exec) => {
      // Search by Story ID or execution ID
      if (searchStoryId.trim()) {
        const q = searchStoryId.toLowerCase();
        const matchesStory = (exec.story_id || "").toLowerCase().includes(q);
        const matchesExec = exec.execution_id.toLowerCase().includes(q);
        const matchesPlan = (exec.plan_id || "").toLowerCase().includes(q);
        if (!matchesStory && !matchesExec && !matchesPlan) return false;
      }

      // Status filter
      if (statusFilter !== "ALL") {
        if (exec.status.toUpperCase() !== statusFilter.toUpperCase()) return false;
      }

      // Date filter
      if (dateFilter !== "ALL") {
        const todayStr = new Date().toISOString().split("T")[0];
        const recordDate = (exec.created_at || "").split("T")[0];
        if (dateFilter === "TODAY" && recordDate !== todayStr) return false;
      }

      return true;
    });
  }, [executions, searchStoryId, statusFilter, dateFilter]);

  const uniqueStatuses = useMemo(() => {
    const s = new Set<string>();
    executions.forEach((e) => s.add(e.status));
    return Array.from(s);
  }, [executions]);

  return (
    <div className="page-container">
      {/* Top Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "24px", flexWrap: "wrap", gap: "12px" }}>
        <div>
          <div style={{ fontSize: "12px", color: "var(--text-muted)", marginBottom: "4px", textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 700 }}>
            Audit & Runtime Logs
          </div>
          <h1 style={{ fontSize: "24px", fontWeight: "800", color: "#ffffff", letterSpacing: "-0.02em" }}>
            Activity & Execution Logs
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "14px" }}>
            Complete audit trail of all subtask creation runs, dry-runs, and retry attempts.
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <button onClick={loadData} className="btn btn-secondary" disabled={loading} style={{ fontSize: "12px", padding: "6px 12px" }}>
            {loading ? "Refreshing..." : "Refresh ↺"}
          </button>
          <Link href="/" className="btn btn-primary" style={{ fontSize: "12px", padding: "6px 14px" }}>
            + Create Tasks
          </Link>
        </div>
      </div>

      {actionSuccess && (
        <div
          style={{
            background: "rgba(16, 185, 129, 0.12)",
            border: "1px solid rgba(16, 185, 129, 0.3)",
            color: "#6ee7b7",
            padding: "12px 16px",
            borderRadius: "var(--radius-md)",
            marginBottom: "20px",
            fontSize: "13px",
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
            padding: "12px 16px",
            borderRadius: "var(--radius-md)",
            marginBottom: "20px",
            fontSize: "13px",
          }}
        >
          ⚠️ {error}
        </div>
      )}

      {/* Filter Toolbar */}
      <div
        className="card"
        style={{
          padding: "14px 18px",
          marginBottom: "20px",
          background: "rgba(16, 23, 38, 0.6)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px", flex: 1, minWidth: "220px" }}>
          <input
            type="text"
            className="input"
            placeholder="Search by Story ID or Execution ID..."
            value={searchStoryId}
            onChange={(e) => setSearchStoryId(e.target.value)}
            style={{ height: "36px", fontSize: "13px", maxWidth: "340px", fontFamily: "var(--font-mono)" }}
          />
          {searchStoryId && (
            <button
              onClick={() => setSearchStoryId("")}
              className="btn btn-secondary"
              style={{ height: "36px", padding: "0 8px", fontSize: "11px" }}
            >
              Clear
            </button>
          )}
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="input"
            style={{ height: "36px", fontSize: "12px", width: "auto" }}
          >
            <option value="ALL">All Statuses</option>
            {uniqueStatuses.map((st) => (
              <option key={st} value={st}>
                {st}
              </option>
            ))}
          </select>

          <select
            value={dateFilter}
            onChange={(e) => setDateFilter(e.target.value)}
            className="input"
            style={{ height: "36px", fontSize: "12px", width: "auto" }}
          >
            <option value="ALL">All Time</option>
            <option value="TODAY">Today Only</option>
          </select>

          <div style={{ fontSize: "12px", color: "var(--text-muted)", marginLeft: "4px" }}>
            Showing <strong style={{ color: "#ffffff" }}>{filteredExecutions.length}</strong> records
          </div>
        </div>
      </div>

      {/* Activity Table */}
      <div className="data-table-wrapper">
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: "120px" }}>Timestamp</th>
                <th style={{ width: "180px" }}>Story</th>
                <th style={{ width: "140px" }}>Sprint</th>
                <th style={{ width: "130px" }}>Developer</th>
                <th style={{ width: "90px" }}>Created</th>
                <th style={{ width: "80px" }}>Skipped</th>
                <th style={{ width: "80px" }}>Failed</th>
                <th style={{ width: "110px" }}>Status</th>
                <th style={{ width: "100px", textAlign: "right" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={9} style={{ padding: "40px", textAlign: "center" }}>
                    <div className="skeleton" style={{ height: "24px", width: "60%", margin: "0 auto 8px" }} />
                    <div className="skeleton" style={{ height: "24px", width: "40%", margin: "0 auto" }} />
                  </td>
                </tr>
              ) : filteredExecutions.length === 0 ? (
                <tr>
                  <td colSpan={9} style={{ padding: "48px 24px", textAlign: "center" }}>
                    <div style={{ fontSize: "36px", marginBottom: "8px" }}>📋</div>
                    <div style={{ fontSize: "15px", fontWeight: "700", color: "#ffffff", marginBottom: "4px" }}>
                      No Activity Records Found
                    </div>
                    <p style={{ color: "var(--text-muted)", fontSize: "13px", marginBottom: "16px" }}>
                      No execution logs matched your filter criteria.
                    </p>
                    <button
                      onClick={() => {
                        setSearchStoryId("");
                        setStatusFilter("ALL");
                        setDateFilter("ALL");
                      }}
                      className="btn btn-secondary"
                      style={{ fontSize: "12px" }}
                    >
                      Reset Filters
                    </button>
                  </td>
                </tr>
              ) : (
                filteredExecutions.map((exec) => {
                  const statusClass =
                    exec.status === "COMPLETED"
                      ? "badge-success"
                      : exec.status === "PARTIAL"
                      ? "badge-warning"
                      : "badge-error";

                  const isPartialOrFailed =
                    exec.status === "PARTIAL" || exec.failed_count > 0;

                  return (
                    <tr key={exec.execution_id} className="table-row">
                      <td style={{ fontSize: "12px", color: "var(--text-muted)", whiteSpace: "nowrap" }}>
                        <div>{new Date(exec.created_at).toLocaleDateString()}</div>
                        <div style={{ fontSize: "11px" }}>{new Date(exec.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</div>
                      </td>
                      <td>
                        <div style={{ fontWeight: 600, color: "#ffffff", fontSize: "13px" }}>
                          {exec.story_id ? (
                            <Link
                              href={`/stories/${exec.story_id}`}
                              style={{ color: "var(--accent-primary)", textDecoration: "none" }}
                            >
                              {exec.story_id} ↗
                            </Link>
                          ) : (
                            <span style={{ color: "var(--text-muted)" }}>Batch / Multi</span>
                          )}
                        </div>
                        <div style={{ fontSize: "11px", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                          {exec.execution_id}
                        </div>
                      </td>
                      <td style={{ fontSize: "12px", color: "var(--text-secondary)", fontFamily: "var(--font-mono)" }}>
                        {exec.sprint_id ? `Sprint ${exec.sprint_id.slice(-6)}` : "-"}
                      </td>
                      <td style={{ fontSize: "12px", color: "#ffffff", fontWeight: 500 }}>
                        Ankit Singh
                      </td>
                      <td style={{ fontWeight: 600, color: "var(--color-success)" }}>
                        {exec.created_count}
                      </td>
                      <td style={{ color: "var(--color-warning)" }}>
                        {exec.pending_count || 0}
                      </td>
                      <td style={{ color: exec.failed_count > 0 ? "var(--color-error)" : "var(--text-muted)", fontWeight: exec.failed_count > 0 ? 700 : 400 }}>
                        {exec.failed_count}
                      </td>
                      <td>
                        <span className={`badge ${statusClass}`} style={{ fontSize: "11px" }}>
                          {exec.status}
                        </span>
                      </td>
                      <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                        <div style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
                          {isPartialOrFailed && (
                            <button
                              onClick={() => handleResume(exec.execution_id)}
                              disabled={resumingId === exec.execution_id}
                              className="btn btn-secondary"
                              style={{
                                fontSize: "11px",
                                padding: "3px 8px",
                                color: "#f59e0b",
                                borderColor: "rgba(245, 158, 11, 0.4)",
                              }}
                              title="Resume failed/pending tasks"
                            >
                              {resumingId === exec.execution_id ? "..." : "Resume"}
                            </button>
                          )}
                          <Link
                            href={`/executions/${exec.execution_id}`}
                            className="btn btn-secondary"
                            style={{ fontSize: "11px", padding: "3px 8px" }}
                          >
                            Details →
                          </Link>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
