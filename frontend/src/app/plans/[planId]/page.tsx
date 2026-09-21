"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import {
  getPlan,
  updatePlan,
  dryRunPlan,
  executePlan,
  resumeExecution,
  ApiError,
} from "@/lib/api-client";
import {
  CreationResult,
  DryRunResponse,
  GeneratedTask,
  PlanResponse,
  ValidationIssue,
} from "@/lib/types";

interface PageProps {
  params: Promise<{ planId: string }>;
}

function cleanPlainText(text: string | undefined | null): string {
  if (!text) return "";
  return text
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/__([^_]+)__/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/_([^_]+)_/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/^#{1,6}\s*/gm, "")
    .trim();
}

function formatNumberedList(text: string | string[] | undefined | null, fallback = "None identified."): string {
  if (!text) return fallback;
  if (Array.isArray(text)) {
    const cleaned = text
      .map((t) => cleanPlainText(t))
      .filter(Boolean)
      .map((l) => l.replace(/^(?:[-*+•]|\d+[.)])\s*/, "").trim())
      .filter(Boolean);
    if (!cleaned.length) return fallback;
    return cleaned.map((item, idx) => `${idx + 1}. ${item}`).join("\n");
  }
  const raw = cleanPlainText(text);
  if (!raw || raw.toLowerCase().replace(/\.$/, "") === "none" || raw.toLowerCase().replace(/\.$/, "") === "none identified") {
    return fallback;
  }
  const lines = raw
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
  const cleaned = lines
    .map((l) => l.replace(/^(?:[-*+•]|\d+[.)])\s*/, "").trim())
    .filter((l) => l && l.toLowerCase().replace(/\.$/, "") !== "none" && l.toLowerCase().replace(/\.$/, "") !== "none identified");
  if (!cleaned.length) return fallback;
  return cleaned.map((item, idx) => `${idx + 1}. ${item}`).join("\n");
}

function parseNumberedList(text: string | string[] | undefined | null, fallback = "None identified."): string[] {
  if (!text) return [fallback];
  if (Array.isArray(text)) {
    const cleaned = text
      .map((t) => cleanPlainText(t))
      .filter(Boolean)
      .map((l) => l.replace(/^(?:[-*+•]|\d+[.)])\s*/, "").trim())
      .filter((l) => l && l.toLowerCase().replace(/\.$/, "") !== "none" && l.toLowerCase().replace(/\.$/, "") !== "none identified");
    return cleaned.length > 0 ? cleaned : [fallback];
  }
  const raw = cleanPlainText(text);
  if (!raw) return [fallback];
  const lines = raw
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
  if (!lines.length) return [fallback];
  const cleaned = lines
    .map((l) => l.replace(/^(?:[-*+•]|\d+[.)])\s*/, "").trim())
    .filter((l) => l && l.toLowerCase().replace(/\.$/, "") !== "none" && l.toLowerCase().replace(/\.$/, "") !== "none identified");
  return cleaned.length > 0 ? cleaned : [fallback];
}

function buildTaskDescription(task: GeneratedTask): string {
  if (task.description && task.description.startsWith("Objective:") && !task.description.includes("## Objective")) {
    return task.description;
  }
  const obj = cleanPlainText(task.objective);
  const scope = formatNumberedList(task.scope, "1. Implement requirements according to story specification.");
  const exp = formatNumberedList(task.expected_behavior, "1. System behaves as defined in objective.");

  const depsRaw = cleanPlainText(task.dependencies);
  const cleanDepsCheck = depsRaw.replace(/^(?:[-*+•]|\d+[.)])\s*/, "").trim();
  let depsSection = "Dependencies:\nNone identified.";
  if (depsRaw && cleanDepsCheck.toLowerCase().replace(/\.$/, "") !== "none" && cleanDepsCheck.toLowerCase().replace(/\.$/, "") !== "none identified") {
    const depsFormatted = formatNumberedList(task.dependencies, "None identified.");
    if (depsFormatted === "None identified.") {
      depsSection = "Dependencies:\nNone identified.";
    } else if (depsFormatted.startsWith("1. ")) {
      depsSection = `Dependencies:\n\n${depsFormatted}`;
    } else {
      depsSection = `Dependencies:\n${depsFormatted}`;
    }
  }

  return `Objective:\n${obj}\n\nScope:\n\n${scope}\n\nExpected Behavior:\n\n${exp}\n\n${depsSection}`;
}

export default function PlanReviewPage({ params }: PageProps) {
  const resolvedParams = use(params);
  const planId = resolvedParams.planId;

  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [tasks, setTasks] = useState<GeneratedTask[]>([]);
  const [originalTasks, setOriginalTasks] = useState<GeneratedTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Task Viewer & Markdown preview state
  const [taskViewModes, setTaskViewModes] = useState<Record<string, "rendered" | "raw" | "edit">>({});
  const [copiedTaskId, setCopiedTaskId] = useState<string | null>(null);
  const [globalMode, setGlobalMode] = useState<"rendered" | "edit">("rendered");

  // Phase 3 Dry-Run & Execution State
  const [showDryRunModal, setShowDryRunModal] = useState(false);
  const [dryRunLoading, setDryRunLoading] = useState(false);
  const [dryRunData, setDryRunData] = useState<DryRunResponse | null>(null);
  const [dryRunError, setDryRunError] = useState<string | null>(null);

  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [confirmAcknowledged, setConfirmAcknowledged] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [resuming, setResuming] = useState(false);
  const [executionResult, setExecutionResult] = useState<CreationResult | null>(null);
  const [executionError, setExecutionError] = useState<string | null>(null);

  const hasUnsavedChanges = JSON.stringify(tasks) !== JSON.stringify(originalTasks);

  const loadPlanData = () => {
    setLoading(true);
    setError(null);
    getPlan(planId)
      .then((data) => {
        setPlan(data);
        setTasks(JSON.parse(JSON.stringify(data.tasks)));
        setOriginalTasks(JSON.parse(JSON.stringify(data.tasks)));
      })
      .catch((err) => {
        if (err instanceof ApiError) {
          setError(err.detail);
        } else {
          setError(err.message || "Failed to load plan");
        }
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadPlanData();
  }, [planId]);

  // Window unload guard for unsaved changes
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasUnsavedChanges) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [hasUnsavedChanges]);

  // Task Field Update Handler
  const handleTaskChange = (taskId: string, field: keyof GeneratedTask, value: any) => {
    setSaveSuccess(false);
    setTasks((prev) =>
      prev.map((t) => (t.id === taskId ? { ...t, [field]: value } : t))
    );
  };

  const handleDeleteTask = (taskId: string) => {
    if (tasks.length <= 1) {
      alert("A plan must contain at least one task.");
      return;
    }
    if (confirm("Are you sure you want to remove this task from the plan?")) {
      setSaveSuccess(false);
      setTasks((prev) => prev.filter((t) => t.id !== taskId));
    }
  };

  const handleReset = () => {
    if (confirm("Discard all unsaved changes and revert to the saved plan?")) {
      setTasks(JSON.parse(JSON.stringify(originalTasks)));
      setSaveSuccess(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSaveSuccess(false);

    // Client-side quick validation
    for (const t of tasks) {
      if (!t.title.trim()) {
        setError(`Task "${t.id}" title is required.`);
        setSaving(false);
        return;
      }
      if (!t.title.startsWith("FE - ") && !t.title.startsWith("BE - ")) {
        setError(`Task "${t.title}" must start with 'FE - ' or 'BE - '`);
        setSaving(false);
        return;
      }
      if (!t.objective.trim() || !t.scope.trim() || !t.expected_behavior.trim()) {
        setError(`Objective, Scope, and Expected behavior are required for task: "${t.title}"`);
        setSaving(false);
        return;
      }
    }

    const normalizedTasks = tasks.map((t) => ({
      ...t,
      objective: cleanPlainText(t.objective),
      scope: formatNumberedList(t.scope, "1. Implement requirements according to story specification."),
      expected_behavior: formatNumberedList(t.expected_behavior, "1. System behaves as defined in objective."),
      dependencies: formatNumberedList(t.dependencies, "None identified."),
    }));

    try {
      const updated = await updatePlan(planId, { tasks: normalizedTasks });
      setPlan(updated);
      setTasks(JSON.parse(JSON.stringify(updated.tasks)));
      setOriginalTasks(JSON.parse(JSON.stringify(updated.tasks)));
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 4000);
    } catch (err: any) {
      setError(err instanceof ApiError ? err.detail : err.message || "Failed to save plan changes");
    } finally {
      setSaving(false);
    }
  };

  // Phase 3: Dry-Run Handler
  const handleOpenDryRun = async () => {
    setShowDryRunModal(true);
    setDryRunLoading(true);
    setDryRunError(null);
    try {
      const data = await dryRunPlan(planId);
      setDryRunData(data);
    } catch (err: any) {
      setDryRunError(err instanceof ApiError ? err.detail : err.message || "Failed to generate dry-run preview");
    } finally {
      setDryRunLoading(false);
    }
  };

  // Phase 3: Live Subtask Execution Handler (Locked behind explicit confirmation)
  const handleExecute = async () => {
    if (!confirmAcknowledged) return;
    setShowConfirmModal(false);
    setExecuting(true);
    setExecutionError(null);
    setExecutionResult(null);

    try {
      const result = await executePlan(planId, { confirm: true, dry_run: false });
      setExecutionResult(result);
      if (result.status === "COMPLETED") {
        setSaveSuccess(true);
      }
    } catch (err: any) {
      setExecutionError(err instanceof ApiError ? err.detail : err.message || "Failed to create tasks in Zoho Sprints");
    } finally {
      setExecuting(false);
      setConfirmAcknowledged(false);
    }
  };

  // Phase 3: Resume Partial Execution Handler
  const handleResume = async (executionId: string) => {
    setResuming(true);
    setExecutionError(null);
    try {
      const result = await resumeExecution(executionId);
      setExecutionResult(result);
      if (result.status === "COMPLETED") {
        setSaveSuccess(true);
      }
    } catch (err: any) {
      setExecutionError(err instanceof ApiError ? err.detail : err.message || "Failed to resume execution");
    } finally {
      setResuming(false);
    }
  };

  if (loading) {
    return (
      <div className="page-container">
        <div className="skeleton" style={{ width: "240px", height: "30px", marginBottom: "20px" }} />
        <div className="skeleton" style={{ width: "100%", height: "80px", marginBottom: "30px" }} />
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          <div className="skeleton" style={{ height: "240px", borderRadius: "var(--radius-lg)" }} />
          <div className="skeleton" style={{ height: "240px", borderRadius: "var(--radius-lg)" }} />
        </div>
      </div>
    );
  }

  if (error && !plan) {
    return (
      <div className="page-container">
        <div className="card" style={{ textAlign: "center", padding: "48px 24px", border: "1px solid var(--color-error)" }}>
          <h2 style={{ fontSize: "20px", fontWeight: "700", marginBottom: "8px", color: "#ffffff" }}>
            Plan Not Found
          </h2>
          <p style={{ color: "var(--text-secondary)", fontSize: "14px", marginBottom: "24px" }}>{error}</p>
          <Link href="/" className="btn btn-primary">
            Return to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  if (!plan) return null;

  return (
    <div className="page-container">
      {/* Sticky Navigation & Action Bar */}
      <div
        style={{
          position: "sticky",
          top: "64px",
          zIndex: 15,
          background: "rgba(10, 14, 23, 0.85)",
          backdropFilter: "blur(12px)",
          borderBottom: "1px solid var(--border-subtle)",
          padding: "16px 0",
          marginBottom: "28px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "16px",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "4px" }}>
            <Link href={`/stories/${plan.story_id}`} style={{ color: "var(--accent-primary)", fontSize: "13px", textDecoration: "none" }}>
              ← Story {plan.story_id}
            </Link>
            <span style={{ color: "var(--text-muted)" }}>•</span>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--text-muted)" }}>
              {plan.plan_id}
            </span>
            {hasUnsavedChanges ? (
              <span className="badge badge-warning">● Unsaved Changes</span>
            ) : saveSuccess ? (
              <span className="badge badge-success">✓ Saved Locally</span>
            ) : (
              <span className="badge badge-neutral">Up to Date</span>
            )}
          </div>
          <h1 style={{ fontSize: "20px", fontWeight: "800", color: "#ffffff" }}>
            Task Review & Plan Editor
          </h1>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          {hasUnsavedChanges && (
            <button onClick={handleReset} className="btn btn-secondary" disabled={saving || executing}>
              Reset
            </button>
          )}

          <button
            onClick={handleSave}
            className="btn btn-primary"
            disabled={saving || executing || !hasUnsavedChanges}
            style={{ minWidth: "130px" }}
          >
            {saving ? "Saving..." : "Save Changes"}
          </button>

          {/* Phase 3: Dry-Run Preview Button */}
          <button
            onClick={handleOpenDryRun}
            className="btn btn-secondary"
            disabled={saving || executing}
            title="Inspect the exact simulated Zoho Sprints API requests without writing"
            style={{ display: "flex", alignItems: "center", gap: "6px" }}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
            <span>Dry-Run Preview</span>
          </button>

          {/* Phase 3: Create Tasks in Zoho Sprints Button (opens confirmation modal) */}
          <button
            onClick={() => {
              setConfirmAcknowledged(false);
              setShowConfirmModal(true);
            }}
            className="btn btn-primary"
            disabled={saving || executing || hasUnsavedChanges || (plan.validation ? !plan.validation.valid : false)}
            title={
              hasUnsavedChanges
                ? "Please save or reset changes before creating tasks"
                : plan.validation && !plan.validation.valid
                ? "Creation blocked: required Story owners are missing or invalid"
                : "Create subtasks in Zoho Sprints with explicit confirmation"
            }
            style={{
              background: plan.validation && !plan.validation.valid ? "rgba(100, 116, 139, 0.4)" : "linear-gradient(135deg, #10b981 0%, #059669 100%)",
              boxShadow: plan.validation && !plan.validation.valid ? "none" : "0 0 16px rgba(16, 185, 129, 0.35)",
              display: "flex",
              alignItems: "center",
              gap: "6px",
              cursor: plan.validation && !plan.validation.valid ? "not-allowed" : "pointer",
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="m5 12 5 5L20 7" />
            </svg>
            <span>{executing ? "Creating..." : "Create Tasks in Zoho"}</span>
          </button>
        </div>
      </div>

      {/* Phase 3: Live Execution Progress Banner */}
      {executing && (
        <div
          className="card"
          style={{
            marginBottom: "24px",
            background: "linear-gradient(135deg, rgba(99, 102, 241, 0.15) 0%, rgba(139, 92, 246, 0.1) 100%)",
            border: "1px solid rgba(99, 102, 241, 0.4)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <span className="pulse-dot" />
              <strong style={{ color: "#ffffff", fontSize: "15px" }}>Creating Subtasks in Zoho Sprints...</strong>
            </div>
            <span style={{ fontSize: "13px", color: "var(--text-muted)" }}>Please wait while tasks are registered</span>
          </div>
          <div className="progress-track">
            <div className="progress-fill" style={{ width: "70%", animation: "shimmer 1.5s infinite" }} />
          </div>
        </div>
      )}

      {/* Phase 3: Execution Error Banner */}
      {executionError && (
        <div
          style={{
            background: "rgba(239, 68, 68, 0.12)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            color: "#fca5a5",
            padding: "16px 20px",
            borderRadius: "var(--radius-md)",
            marginBottom: "24px",
            fontSize: "14px",
          }}
        >
          <strong>⚠️ Execution Error:</strong> {executionError}
        </div>
      )}

      {/* Phase 3: Execution Results Card */}
      {executionResult && (
        <div
          className="card"
          style={{
            marginBottom: "28px",
            background:
              executionResult.status === "COMPLETED"
                ? "linear-gradient(135deg, rgba(16, 185, 129, 0.12) 0%, rgba(10, 14, 23, 0.8) 100%)"
                : "linear-gradient(135deg, rgba(245, 158, 11, 0.12) 0%, rgba(10, 14, 23, 0.8) 100%)",
            border:
              executionResult.status === "COMPLETED"
                ? "1px solid rgba(16, 185, 129, 0.4)"
                : "1px solid rgba(245, 158, 11, 0.4)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px", flexWrap: "wrap", gap: "12px" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                {executionResult.status === "COMPLETED" ? (
                  <span className="badge badge-success">✓ COMPLETED</span>
                ) : executionResult.status === "PARTIAL" ? (
                  <span className="badge badge-warning">⚠️ PARTIAL EXECUTION</span>
                ) : (
                  <span className="badge badge-error">✗ FAILED</span>
                )}
                <span style={{ fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--text-muted)" }}>
                  {executionResult.execution_id}
                </span>
              </div>
              <h2 style={{ fontSize: "18px", fontWeight: "700", color: "#ffffff" }}>
                Task Creation Summary
              </h2>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              {(executionResult.status === "PARTIAL" || executionResult.failed_tasks > 0) && (
                <button
                  onClick={() => handleResume(executionResult.execution_id)}
                  className="btn btn-primary"
                  disabled={resuming}
                  style={{ background: "var(--color-warning)", color: "#000", fontWeight: "700" }}
                >
                  {resuming ? "Resuming..." : "Resume Execution ↺"}
                </button>
              )}
              <Link href="/executions" className="btn btn-secondary" style={{ fontSize: "13px" }}>
                View All Executions →
              </Link>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "12px", marginBottom: "16px" }}>
            <div style={{ background: "rgba(255, 255, 255, 0.03)", padding: "12px", borderRadius: "var(--radius-sm)", textAlign: "center" }}>
              <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>TOTAL TASKS</div>
              <div style={{ fontSize: "20px", fontWeight: "700", color: "#ffffff" }}>{executionResult.total_tasks}</div>
            </div>
            <div style={{ background: "rgba(16, 185, 129, 0.08)", padding: "12px", borderRadius: "var(--radius-sm)", textAlign: "center" }}>
              <div style={{ fontSize: "11px", color: "var(--color-success)" }}>CREATED</div>
              <div style={{ fontSize: "20px", fontWeight: "700", color: "var(--color-success)" }}>{executionResult.created_tasks}</div>
            </div>
            <div style={{ background: "rgba(255, 255, 255, 0.03)", padding: "12px", borderRadius: "var(--radius-sm)", textAlign: "center" }}>
              <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>SKIPPED</div>
              <div style={{ fontSize: "20px", fontWeight: "700", color: "var(--text-muted)" }}>{executionResult.skipped_tasks}</div>
            </div>
            <div style={{ background: "rgba(239, 68, 68, 0.08)", padding: "12px", borderRadius: "var(--radius-sm)", textAlign: "center" }}>
              <div style={{ fontSize: "11px", color: "var(--color-error)" }}>FAILED</div>
              <div style={{ fontSize: "20px", fontWeight: "700", color: "var(--color-error)" }}>{executionResult.failed_tasks}</div>
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {executionResult.tasks.map((t, idx) => (
              <div
                key={idx}
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  background: "rgba(0, 0, 0, 0.25)",
                  padding: "10px 14px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-subtle)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span className={`badge ${t.task_type === "FE" ? "badge-fe" : "badge-be"}`}>
                    {t.task_type}
                  </span>
                  <span style={{ fontSize: "13px", fontWeight: "500", color: "#ffffff" }}>{t.title}</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  {t.status === "CREATED" ? (
                    <>
                      <span className="badge badge-success" style={{ fontFamily: "var(--font-mono)" }}>
                        ✓ Created · ID: {t.zoho_task_id || "Success"}
                      </span>
                      {t.zoho_task_url && (
                        <a
                          href={t.zoho_task_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="btn btn-secondary"
                          style={{ padding: "4px 10px", fontSize: "11px", display: "inline-flex", alignItems: "center", gap: "4px", textDecoration: "none" }}
                          title="Open this subtask in Zoho Sprints"
                        >
                          <span>Open in Zoho</span>
                          <span style={{ fontSize: "12px" }}>↗</span>
                        </a>
                      )}
                    </>
                  ) : t.status === "FAILED" ? (
                    <span className="badge badge-error" title={t.error_message || "Failed"}>
                      ✗ Failed: {t.error_message || "Error"}
                    </span>
                  ) : (
                    <span className="badge badge-neutral">{t.status}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Global Error Banner */}
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

      {/* Inherited Story Owner Mapping Summary */}
      <div
        className="card"
        style={{
          marginBottom: "24px",
          background: "linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.85) 100%)",
          border: "1px solid var(--border-subtle)",
          padding: "18px 22px",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px", marginBottom: "14px" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ fontSize: "12px", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--accent-primary)" }}>
                Story Owner Inheritance
              </span>
              <span className="badge badge-neutral" style={{ fontSize: "11px" }}>Inherited from Story {plan.story_id}</span>
            </div>
            <p style={{ fontSize: "13px", color: "var(--text-secondary)", margin: "4px 0 0 0" }}>
              Task ownership is automatically mapped from the parent Story. No manual per-task owner assignment required.
            </p>
          </div>
          {plan.validation && !plan.validation.valid ? (
            <span className="badge badge-danger" style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              ⚠️ Owner Validation Error ({plan.validation.errors.length})
            </span>
          ) : plan.validation && plan.validation.warnings.length > 0 ? (
            <span className="badge badge-neutral" style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--text-secondary)" }}>
              ℹ️ Optional Owners Unassigned
            </span>
          ) : (
            <span className="badge badge-success" style={{ display: "flex", alignItems: "center", gap: "6px" }}>
              ✓ Owners Inherited
            </span>
          )}
        </div>

        {/* Missing Owner Error Banner (Only for genuine blocking errors) */}
        {plan.validation && !plan.validation.valid && (
          <div
            style={{
              padding: "12px 16px",
              background: "rgba(239, 68, 68, 0.12)",
              border: "1px solid rgba(239, 68, 68, 0.3)",
              borderRadius: "8px",
              marginBottom: "16px",
              color: "#fca5a5",
              fontSize: "13px",
            }}
          >
            <strong style={{ color: "#f87171" }}>Validation Error:</strong>
            <ul style={{ margin: "6px 0 0 18px", padding: 0 }}>
              {plan.validation.errors.map((err, i) => (
                <li key={i}>{err.message}</li>
              ))}
            </ul>
          </div>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "16px" }}>
          {/* Dev Owner Mapping Card */}
          <div
            style={{
              padding: "14px 18px",
              background: "rgba(15, 23, 42, 0.6)",
              borderRadius: "10px",
              border: "1px solid var(--border-subtle)",
              display: "flex",
              alignItems: "center",
              gap: "14px",
            }}
          >
            <div style={{ width: "42px", height: "42px", borderRadius: "8px", background: "rgba(99, 102, 241, 0.15)", border: "1px solid rgba(99, 102, 241, 0.3)", display: "flex", alignItems: "center", justifyContent: "center", color: "#818cf8", fontWeight: "700", fontSize: "13px" }}>
              DEV
            </div>
            <div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: "600" }}>
                Parent Story Dev Owner → All Task Assignees
              </div>
              <div style={{ fontSize: "14px", fontWeight: "700", color: plan.dev_owner ? "#ffffff" : "var(--text-muted)" }}>
                {plan.dev_owner ? (plan.dev_owner.display_name || plan.dev_owner.user_id) : "Unassigned (Optional)"}
              </div>
              {plan.dev_owner && (
                <div style={{ fontSize: "11px", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                  ID: {plan.dev_owner.user_id} {plan.dev_owner.email && `• ${plan.dev_owner.email}`}
                </div>
              )}
            </div>
          </div>

          {/* QA Owner Mapping Card */}
          <div
            style={{
              padding: "14px 18px",
              background: "rgba(15, 23, 42, 0.6)",
              borderRadius: "10px",
              border: "1px solid var(--border-subtle)",
              display: "flex",
              alignItems: "center",
              gap: "14px",
            }}
          >
            <div style={{ width: "42px", height: "42px", borderRadius: "8px", background: "rgba(245, 158, 11, 0.15)", border: "1px solid rgba(245, 158, 11, 0.3)", display: "flex", alignItems: "center", justifyContent: "center", color: "#fbbf24", fontWeight: "700", fontSize: "13px" }}>
              QA
            </div>
            <div>
              <div style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: "600" }}>
                Parent Story QA Owner → All Task QA Owners
              </div>
              <div style={{ fontSize: "14px", fontWeight: "700", color: plan.qa_owner ? "#ffffff" : "var(--text-muted)" }}>
                {plan.qa_owner ? (plan.qa_owner.display_name || plan.qa_owner.user_id) : "Unassigned (Optional)"}
              </div>
              {plan.qa_owner && (
                <div style={{ fontSize: "11px", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                  ID: {plan.qa_owner.user_id} {plan.qa_owner.email && `• ${plan.qa_owner.email}`}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Story Summary Card */}
      <div
        className="card"
        style={{
          marginBottom: "28px",
          background: "linear-gradient(135deg, rgba(22, 32, 50, 0.6) 0%, rgba(16, 23, 38, 0.8) 100%)",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "10px" }}>
          <div>
            <div style={{ fontSize: "12px", color: "var(--text-muted)", marginBottom: "4px" }}>
              PARENT USER STORY
            </div>
            <h2 style={{ fontSize: "17px", fontWeight: "700", color: "#ffffff" }}>
              {plan.story_title}
            </h2>
          </div>
          <div style={{ display: "flex", gap: "8px" }}>
            <span className="badge badge-info">
              {tasks.filter((t) => t.task_type === "FE").length} FE Task
            </span>
            <span className="badge badge-neutral" style={{ color: "#c084fc", borderColor: "rgba(192, 132, 252, 0.3)" }}>
              {tasks.filter((t) => t.task_type === "BE").length} BE Tasks
            </span>
          </div>
        </div>

        <p style={{ fontSize: "13.5px", color: "var(--text-secondary)", lineHeight: "1.6" }}>
          {plan.story_summary}
        </p>
      </div>

      {/* Duplicate Overlap Warnings */}
      {plan.duplicate_warnings && plan.duplicate_warnings.length > 0 && (
        <div
          style={{
            background: "rgba(245, 158, 11, 0.08)",
            border: "1px solid rgba(245, 158, 11, 0.3)",
            borderRadius: "var(--radius-lg)",
            padding: "20px",
            marginBottom: "28px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "var(--color-warning)", fontWeight: "700", marginBottom: "12px" }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
            <span>Existing Subtask Overlap Warnings ({plan.duplicate_warnings.length})</span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {plan.duplicate_warnings.map((d, i) => (
              <div
                key={i}
                style={{
                  background: "rgba(10, 14, 23, 0.5)",
                  padding: "12px 16px",
                  borderRadius: "var(--radius-md)",
                  border: "1px solid var(--border-subtle)",
                  fontSize: "13px",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: "10px",
                }}
              >
                <div>
                  <span style={{ color: "var(--text-highlight)", fontWeight: "600" }}>{d.generated_title}</span>
                  <span style={{ color: "var(--text-muted)", margin: "0 8px" }}>matches</span>
                  <span style={{ color: "var(--color-warning)", fontFamily: "var(--font-mono)" }}>
                    {d.existing_title} (ID: {d.existing_id})
                  </span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <span className="badge badge-warning">{d.match_type} ({Math.round(d.similarity_score * 100)}%)</span>
                  <span style={{ color: "var(--text-secondary)", fontSize: "12px" }}>{d.recommendation}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Task List Header & Global View Mode Toggle */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexWrap: "wrap", gap: "12px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <h2 style={{ fontSize: "18px", fontWeight: "700", color: "#ffffff" }}>
            Generated Tasks ({tasks.length})
          </h2>
          <span className="badge badge-neutral" style={{ fontSize: "11px" }}>
            Exact 4-Section Markdown: Objective · Scope · Expected Behavior · Dependencies
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>View:</span>
          <div style={{ display: "inline-flex", background: "rgba(255, 255, 255, 0.05)", padding: "3px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
            <button
              onClick={() => {
                setGlobalMode("rendered");
                setTaskViewModes({});
              }}
              style={{
                background: globalMode === "rendered" ? "var(--accent-primary)" : "transparent",
                color: globalMode === "rendered" ? "#ffffff" : "var(--text-secondary)",
                border: "none",
                padding: "4px 10px",
                borderRadius: "4px",
                fontSize: "12px",
                fontWeight: "600",
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              👁️ Formatted Markdown
            </button>
            <button
              onClick={() => {
                setGlobalMode("edit");
                const allEdit: Record<string, "rendered" | "raw" | "edit"> = {};
                tasks.forEach((t) => (allEdit[t.id] = "edit"));
                setTaskViewModes(allEdit);
              }}
              style={{
                background: globalMode === "edit" ? "var(--accent-primary)" : "transparent",
                color: globalMode === "edit" ? "#ffffff" : "var(--text-secondary)",
                border: "none",
                padding: "4px 10px",
                borderRadius: "4px",
                fontSize: "12px",
                fontWeight: "600",
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              ✏️ Edit Mode
            </button>
          </div>
        </div>
      </div>

      {/* Task List (Interactive Markdown Viewer & Cards) */}
      <div style={{ display: "flex", flexDirection: "column", gap: "28px" }}>
        {tasks.map((task, idx) => {
          const isFE = task.task_type === "FE";
          const borderHighlight = isFE ? "rgba(99, 102, 241, 0.4)" : "rgba(168, 85, 247, 0.4)";
          const matchingWarning = plan.duplicate_warnings?.find(
            (w) => w.generated_title.toLowerCase().trim() === task.title.toLowerCase().trim()
          );
          const currentMode = taskViewModes[task.id] || globalMode;
          const taskDescription = buildTaskDescription(task);

          return (
            <div
              key={task.id}
              className="card"
              style={{
                borderLeft: `4px solid ${isFE ? "var(--accent-primary)" : "var(--accent-secondary)"}`,
                position: "relative",
              }}
            >
              {/* Task Header */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexWrap: "wrap", gap: "10px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                  <span
                    className="badge"
                    style={{
                      background: isFE ? "rgba(99, 102, 241, 0.2)" : "rgba(168, 85, 247, 0.2)",
                      color: isFE ? "#818cf8" : "#c084fc",
                      border: `1px solid ${borderHighlight}`,
                      fontWeight: "700",
                    }}
                  >
                    {task.task_type}
                  </span>
                  <span style={{ fontSize: "12px", fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
                    {task.id}
                  </span>
                  {matchingWarning && (
                    <span className="badge badge-warning" style={{ fontSize: "11px" }}>
                      ⚠️ Duplicate match: {matchingWarning.match_type}
                    </span>
                  )}
                </div>

                {/* Header Action Controls */}
                <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                  {/* Mode Toggles */}
                  <div style={{ display: "inline-flex", background: "rgba(255, 255, 255, 0.04)", padding: "2px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
                    <button
                      onClick={() => setTaskViewModes((prev) => ({ ...prev, [task.id]: "rendered" }))}
                      className="btn"
                      style={{
                        padding: "3px 8px",
                        fontSize: "11px",
                        fontWeight: "600",
                        background: currentMode === "rendered" ? "rgba(99, 102, 241, 0.3)" : "transparent",
                        color: currentMode === "rendered" ? "#ffffff" : "var(--text-muted)",
                        border: "none",
                        borderRadius: "4px",
                      }}
                      title="View formatted structure"
                    >
                      👁️ Formatted
                    </button>
                    <button
                      onClick={() => setTaskViewModes((prev) => ({ ...prev, [task.id]: "raw" }))}
                      className="btn"
                      style={{
                        padding: "3px 8px",
                        fontSize: "11px",
                        fontWeight: "600",
                        background: currentMode === "raw" ? "rgba(99, 102, 241, 0.3)" : "transparent",
                        color: currentMode === "raw" ? "#ffffff" : "var(--text-muted)",
                        border: "none",
                        borderRadius: "4px",
                      }}
                      title="View plain text for Zoho Sprints"
                    >
                      📝 Plain Text
                    </button>
                    <button
                      onClick={() => setTaskViewModes((prev) => ({ ...prev, [task.id]: "edit" }))}
                      className="btn"
                      style={{
                        padding: "3px 8px",
                        fontSize: "11px",
                        fontWeight: "600",
                        background: currentMode === "edit" ? "rgba(99, 102, 241, 0.3)" : "transparent",
                        color: currentMode === "edit" ? "#ffffff" : "var(--text-muted)",
                        border: "none",
                        borderRadius: "4px",
                      }}
                      title="Edit task fields"
                    >
                      ✏️ Edit
                    </button>
                  </div>

                  {/* Copy Description Button */}
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(taskDescription);
                      setCopiedTaskId(task.id);
                      setTimeout(() => setCopiedTaskId(null), 2000);
                    }}
                    className="btn btn-secondary"
                    style={{ padding: "4px 10px", fontSize: "11px" }}
                    title="Copy task description to clipboard"
                  >
                    {copiedTaskId === task.id ? "✓ Copied!" : "📋 Copy Description"}
                  </button>

                  {/* Delete Button */}
                  <button
                    onClick={() => handleDeleteTask(task.id)}
                    className="btn btn-secondary"
                    style={{
                      padding: "4px 10px",
                      fontSize: "11px",
                      color: "var(--color-error)",
                      borderColor: "rgba(239, 68, 68, 0.2)",
                    }}
                    title="Remove this task from plan"
                  >
                    Delete
                  </button>
                </div>
              </div>

              {/* Inherited Ownership Info */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  padding: "8px 12px",
                  background: "rgba(255, 255, 255, 0.02)",
                  border: "1px solid rgba(255, 255, 255, 0.06)",
                  borderRadius: "var(--radius-sm)",
                  marginBottom: "16px",
                  flexWrap: "wrap",
                  fontSize: "12px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <span style={{ color: "var(--text-muted)" }}>Assignee:</span>
                  {(task.assignee || plan.dev_owner) ? (
                    <span className="badge" style={{ background: "rgba(16, 185, 129, 0.15)", color: "#34d399", border: "1px solid rgba(16, 185, 129, 0.3)" }}>
                      👤 {(task.assignee || plan.dev_owner)?.display_name} <span style={{ opacity: 0.7, fontSize: "10px" }}>(Parent Dev Owner)</span>
                    </span>
                  ) : (
                    <span className="badge badge-neutral" style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                      Unassigned
                    </span>
                  )}
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                  <span style={{ color: "var(--text-muted)" }}>QA Owner:</span>
                  {(task.qa_owner || plan.qa_owner) ? (
                    <span className="badge" style={{ background: "rgba(14, 165, 233, 0.15)", color: "#38bdf8", border: "1px solid rgba(14, 165, 233, 0.3)" }}>
                      🔍 {(task.qa_owner || plan.qa_owner)?.display_name} <span style={{ opacity: 0.7, fontSize: "10px" }}>(Parent QA Owner)</span>
                    </span>
                  ) : (
                    <span className="badge badge-neutral" style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                      Unassigned
                    </span>
                  )}
                </div>
              </div>

              {/* RENDER MODE 1: Formatted Viewer (6 clean sections with numbered lists) */}
              {currentMode === "rendered" && (
                <div>
                  <div style={{ fontSize: "16px", fontWeight: "700", color: isFE ? "#818cf8" : "#c084fc", marginBottom: "18px" }}>
                    {task.title}
                  </div>

                  {/* Section 1: Objective: */}
                  <div style={{ marginBottom: "16px" }}>
                    <h3 style={{ fontSize: "13px", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.05em", color: "#e2e8f0", marginBottom: "6px" }}>
                      Objective:
                    </h3>
                    <p style={{ fontSize: "13.5px", color: "var(--text-primary)", lineHeight: "1.6", background: "rgba(255, 255, 255, 0.02)", padding: "10px 14px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
                      {cleanPlainText(task.objective) || "No objective defined."}
                    </p>
                  </div>

                  {/* Section 2: Scope: */}
                  <div style={{ marginBottom: "16px" }}>
                    <h3 style={{ fontSize: "13px", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.05em", color: "#e2e8f0", marginBottom: "6px" }}>
                      Scope:
                    </h3>
                    <div style={{ background: "rgba(255, 255, 255, 0.02)", padding: "10px 14px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
                      <ol style={{ margin: 0, paddingLeft: "20px", display: "flex", flexDirection: "column", gap: "6px" }}>
                        {parseNumberedList(task.scope).map((item, bIdx) => (
                          <li key={bIdx} style={{ fontSize: "13px", color: "var(--text-primary)", lineHeight: "1.5" }}>
                            {item}
                          </li>
                        ))}
                      </ol>
                    </div>
                  </div>

                  {/* Section 3: Expected Behavior: */}
                  <div style={{ marginBottom: "16px" }}>
                    <h3 style={{ fontSize: "13px", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.05em", color: "#e2e8f0", marginBottom: "6px" }}>
                      Expected Behavior:
                    </h3>
                    <div style={{ background: "rgba(255, 255, 255, 0.02)", padding: "10px 14px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
                      <ol style={{ margin: 0, paddingLeft: "20px", display: "flex", flexDirection: "column", gap: "6px" }}>
                        {parseNumberedList(task.expected_behavior).map((item, bIdx) => (
                          <li key={bIdx} style={{ fontSize: "13px", color: "var(--text-primary)", lineHeight: "1.5" }}>
                            {item}
                          </li>
                        ))}
                      </ol>
                    </div>
                  </div>

                  {/* Section 4: Dependencies: */}
                  <div style={{ marginBottom: "16px" }}>
                    <h3 style={{ fontSize: "13px", fontWeight: "700", textTransform: "uppercase", letterSpacing: "0.05em", color: "#e2e8f0", marginBottom: "6px" }}>
                      Dependencies:
                    </h3>
                    <div style={{ background: "rgba(255, 255, 255, 0.02)", padding: "10px 14px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-subtle)" }}>
                      {parseNumberedList(task.dependencies, "None identified.").length === 1 && parseNumberedList(task.dependencies, "None identified.")[0] === "None identified." ? (
                        <p style={{ margin: 0, fontSize: "13px", color: "var(--text-muted)" }}>None identified.</p>
                      ) : (
                        <ol style={{ margin: 0, paddingLeft: "20px", display: "flex", flexDirection: "column", gap: "6px" }}>
                          {parseNumberedList(task.dependencies, "None identified.").map((item, bIdx) => (
                            <li key={bIdx} style={{ fontSize: "13px", color: "var(--text-primary)", lineHeight: "1.5" }}>
                              {item}
                            </li>
                          ))}
                        </ol>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* RENDER MODE 2: Raw Zoho Plain Text View */}
              {currentMode === "raw" && (
                <div>
                  <div style={{ fontSize: "16px", fontWeight: "700", color: isFE ? "#818cf8" : "#c084fc", marginBottom: "12px" }}>
                    {task.title}
                  </div>
                  <pre
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: "12.5px",
                      lineHeight: "1.6",
                      background: "rgba(10, 14, 23, 0.8)",
                      border: "1px solid var(--border-subtle)",
                      borderRadius: "var(--radius-md)",
                      padding: "16px",
                      color: "#e2e8f0",
                      whiteSpace: "pre-wrap",
                      wordBreak: "break-word",
                    }}
                  >
                    {taskDescription}
                  </pre>
                </div>
              )}

              {/* RENDER MODE 3: Edit Task Fields */}
              {currentMode === "edit" && (
                <div>
                  {/* Title Input */}
                  <div style={{ marginBottom: "20px" }}>
                    <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "var(--text-muted)", marginBottom: "6px" }}>
                      TASK TITLE
                    </label>
                    <input
                      type="text"
                      className="input"
                      value={task.title}
                      onChange={(e) => handleTaskChange(task.id, "title", e.target.value)}
                      style={{
                        fontWeight: "600",
                        fontSize: "15px",
                        color: isFE ? "#818cf8" : "#c084fc",
                        borderColor: "rgba(255, 255, 255, 0.15)",
                      }}
                    />
                  </div>

                  {/* 2-Column Grid for Objective & Scope */}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "16px" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "var(--text-muted)", marginBottom: "6px" }}>
                        OBJECTIVE (Concise paragraph)
                      </label>
                      <textarea
                        className="input"
                        rows={4}
                        value={task.objective}
                        onChange={(e) => handleTaskChange(task.id, "objective", e.target.value)}
                        placeholder="A clear and concise description of the task objective..."
                        style={{ resize: "vertical", fontSize: "13px", lineHeight: "1.5" }}
                      />
                    </div>

                    <div>
                      <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "var(--text-muted)", marginBottom: "6px" }}>
                        SCOPE (Numbered list)
                      </label>
                      <textarea
                        className="input"
                        rows={4}
                        value={task.scope}
                        onChange={(e) => handleTaskChange(task.id, "scope", e.target.value)}
                        placeholder="1. Implement work item 1&#10;2. Implement work item 2"
                        style={{ resize: "vertical", fontSize: "13px", lineHeight: "1.5" }}
                      />
                    </div>
                  </div>

                  {/* 2-Column Grid for Expected Behavior & Dependencies */}
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "16px" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "var(--text-muted)", marginBottom: "6px" }}>
                        EXPECTED BEHAVIOR (Numbered list)
                      </label>
                      <textarea
                        className="input"
                        rows={4}
                        value={task.expected_behavior}
                        onChange={(e) => handleTaskChange(task.id, "expected_behavior", e.target.value)}
                        placeholder="1. User action produces expected result&#10;2. Edge case handled correctly"
                        style={{ resize: "vertical", fontSize: "13px", lineHeight: "1.5" }}
                      />
                    </div>

                    <div>
                      <label style={{ display: "block", fontSize: "12px", fontWeight: "600", color: "var(--text-muted)", marginBottom: "6px" }}>
                        DEPENDENCIES
                      </label>
                      <textarea
                        className="input"
                        rows={4}
                        value={task.dependencies}
                        onChange={(e) => handleTaskChange(task.id, "dependencies", e.target.value)}
                        placeholder="None identified."
                        style={{ resize: "vertical", fontSize: "13px", lineHeight: "1.5" }}
                      />
                    </div>
                  </div>

                  <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "8px" }}>
                    <button
                      type="button"
                      onClick={() => setTaskViewModes((prev) => ({ ...prev, [task.id]: "rendered" }))}
                      className="btn btn-secondary"
                      style={{ fontSize: "12px", padding: "6px 12px" }}
                    >
                      Done Editing (Preview Zoho Format) →
                    </button>
                  </div>
                </div>
              )}

            </div>
          );
        })}
      </div>

      {/* Phase 3: Dry-Run Preview Modal */}
      {showDryRunModal && (
        <div className="modal-backdrop" onClick={() => setShowDryRunModal(false)}>
          <div className="modal-card modal-card-lg" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <span style={{ fontSize: "20px" }}>🔍</span>
                <div>
                  <h3 style={{ fontSize: "16px", fontWeight: "700", color: "#ffffff" }}>
                    Dry-Run Preview: Simulated Zoho Sprints API Calls
                  </h3>
                  <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                    Zero writes will be performed · Verification of intended HTTP requests
                  </div>
                </div>
              </div>
              <button
                onClick={() => setShowDryRunModal(false)}
                style={{ background: "transparent", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: "18px" }}
              >
                ✕
              </button>
            </div>

            <div className="modal-body">
              {dryRunLoading ? (
                <div style={{ padding: "40px", textAlign: "center" }}>
                  <div className="skeleton" style={{ width: "220px", height: "24px", margin: "0 auto 12px auto" }} />
                  <div className="skeleton" style={{ width: "320px", height: "16px", margin: "0 auto" }} />
                </div>
              ) : dryRunError ? (
                <div style={{ color: "var(--color-error)", padding: "16px" }}>
                  ⚠️ Error generating dry run: {dryRunError}
                </div>
              ) : dryRunData ? (
                <div>
                  <div
                    style={{
                      background: "rgba(99, 102, 241, 0.08)",
                      border: "1px solid rgba(99, 102, 241, 0.2)",
                      borderRadius: "var(--radius-md)",
                      padding: "12px 16px",
                      marginBottom: "20px",
                      fontSize: "13px",
                      color: "var(--text-secondary)",
                    }}
                  >
                    💡 The <strong>{dryRunData.total_operations}</strong> operations below simulate the exact API requests that will be dispatched to the Zoho Sprints endpoint upon confirmation.
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                    {dryRunData.operations.map((op, idx) => (
                      <div
                        key={idx}
                        style={{
                          background: "var(--bg-surface)",
                          border: "1px solid var(--border-subtle)",
                          borderRadius: "var(--radius-md)",
                          padding: "16px",
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px", flexWrap: "wrap", gap: "8px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                            <span className="badge badge-neutral" style={{ fontWeight: "700" }}>{op.method}</span>
                            <span style={{ fontWeight: "600", fontSize: "14px", color: "#ffffff" }}>{op.task_title}</span>
                          </div>
                          <div style={{ display: "flex", gap: "8px", fontSize: "11px", flexWrap: "wrap" }}>
                            <span className="badge" style={{ background: "rgba(16, 185, 129, 0.15)", color: "#34d399", border: "1px solid rgba(16, 185, 129, 0.3)" }}>
                              Assignee: {plan.dev_owner?.display_name || "Unassigned"}
                            </span>
                            <span className="badge" style={{ background: "rgba(14, 165, 233, 0.15)", color: "#38bdf8", border: "1px solid rgba(14, 165, 233, 0.3)" }}>
                              QA: {plan.qa_owner?.display_name || "Unassigned"}
                            </span>
                            <span className="badge badge-neutral">ItemType: {op.item_type_id}</span>
                            <span className="badge badge-neutral">Priority: {op.priority_id}</span>
                          </div>
                        </div>

                        <div style={{ fontFamily: "var(--font-mono)", fontSize: "11px", color: "var(--text-muted)", marginBottom: "8px", wordBreak: "break-all" }}>
                          Endpoint: {op.endpoint}
                        </div>

                        <div className="code-preview" style={{ maxHeight: "160px" }}>
                          {JSON.stringify(op.payload, null, 2)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>

            <div className="modal-footer">
              <button onClick={() => setShowDryRunModal(false)} className="btn btn-secondary">
                Close Preview
              </button>
              <button
                onClick={() => {
                  setShowDryRunModal(false);
                  setConfirmAcknowledged(false);
                  setShowConfirmModal(true);
                }}
                className="btn btn-primary"
                disabled={dryRunLoading || !!dryRunError || (plan.validation ? !plan.validation.valid : false)}
              >
                Proceed to Confirmation →
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Phase 3: Safety Confirmation Modal */}
      {showConfirmModal && (
        <div className="modal-backdrop" onClick={() => !executing && setShowConfirmModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <span style={{ fontSize: "22px" }}>⚠️</span>
                <div>
                  <h3 style={{ fontSize: "16px", fontWeight: "700", color: "#ffffff" }}>
                    Confirm Task Creation in Zoho Sprints
                  </h3>
                  <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                    Target Parent Story: {plan.story_id}
                  </div>
                </div>
              </div>
              {!executing && (
                <button
                  onClick={() => setShowConfirmModal(false)}
                  style={{ background: "transparent", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: "18px" }}
                >
                  ✕
                </button>
              )}
            </div>

            <div className="modal-body">
              <div
                style={{
                  background: "rgba(245, 158, 11, 0.1)",
                  border: "1px solid rgba(245, 158, 11, 0.3)",
                  borderRadius: "var(--radius-md)",
                  padding: "16px",
                  marginBottom: "20px",
                  color: "#fcd34d",
                  fontSize: "13px",
                  lineHeight: "1.6",
                }}
              >
                <strong>Attention:</strong> You are about to create <strong>{tasks.length} subtasks</strong> under the story:
                <div style={{ fontWeight: "700", color: "#ffffff", marginTop: "6px" }}>
                  "{plan.story_title}"
                </div>
                <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "4px" }}>
                  Team: {plan.team_id} • Project: {plan.project_id} • Sprint: {plan.sprint_id}
                </div>
              </div>

              {/* Inherited Ownership Summary Box */}
              <div
                style={{
                  background: "rgba(255, 255, 255, 0.03)",
                  border: "1px solid var(--border-card)",
                  borderRadius: "var(--radius-md)",
                  padding: "14px",
                  marginBottom: "20px",
                }}
              >
                <div style={{ fontSize: "11px", fontWeight: "700", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: "8px" }}>
                  Inherited Ownership Mapping
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", fontSize: "13px" }}>
                  <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                    <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>TASK ASSIGNEE (DEV OWNER)</span>
                    {plan.dev_owner ? (
                      <span style={{ color: "#34d399", fontWeight: "600" }}>
                        👤 {plan.dev_owner.display_name}
                        <span style={{ fontSize: "11px", opacity: 0.7, display: "block" }}>ID: {plan.dev_owner.user_id}</span>
                      </span>
                    ) : (
                      <span style={{ color: "var(--text-muted)", fontWeight: "500" }}>Unassigned (Optional)</span>
                    )}
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                    <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>TASK QA OWNER</span>
                    {plan.qa_owner ? (
                      <span style={{ color: "#38bdf8", fontWeight: "600" }}>
                        🔍 {plan.qa_owner.display_name}
                        <span style={{ fontSize: "11px", opacity: 0.7, display: "block" }}>ID: {plan.qa_owner.user_id}</span>
                      </span>
                    ) : (
                      <span style={{ color: "var(--text-muted)", fontWeight: "500" }}>Unassigned (Optional)</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Owner validation warning banner if invalid */}
              {plan.validation && !plan.validation.valid && (
                <div
                  style={{
                    background: "rgba(239, 68, 68, 0.15)",
                    border: "1px solid rgba(239, 68, 68, 0.4)",
                    borderRadius: "var(--radius-md)",
                    padding: "12px",
                    marginBottom: "20px",
                    color: "#fca5a5",
                    fontSize: "12px",
                  }}
                >
                  <strong style={{ display: "block", marginBottom: "4px" }}>🚫 Creation Blocked: Validation Errors Detected</strong>
                  <ul style={{ paddingLeft: "18px", margin: 0 }}>
                    {plan.validation.errors.map((err: ValidationIssue, i: number) => (
                      <li key={i}>{err.message}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div style={{ marginBottom: "20px" }}>
                <div style={{ fontSize: "12px", fontWeight: "700", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: "8px" }}>
                  Tasks to be created:
                </div>
                <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: "6px" }}>
                  {tasks.map((t) => (
                    <li
                      key={t.id}
                      style={{
                        fontSize: "13px",
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                        background: "rgba(255, 255, 255, 0.03)",
                        padding: "8px 12px",
                        borderRadius: "var(--radius-sm)",
                      }}
                    >
                      <span className={`badge ${t.task_type === "FE" ? "badge-fe" : "badge-be"}`}>
                        {t.task_type}
                      </span>
                      <span style={{ color: "#ffffff", fontWeight: "500" }}>{t.title}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <label
                style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "10px",
                  padding: "12px",
                  borderRadius: "var(--radius-md)",
                  background: "rgba(255, 255, 255, 0.04)",
                  border: "1px solid var(--border-card)",
                  cursor: "pointer",
                }}
              >
                <input
                  type="checkbox"
                  checked={confirmAcknowledged}
                  onChange={(e) => setConfirmAcknowledged(e.target.checked)}
                  style={{ marginTop: "3px", cursor: "pointer" }}
                />
                <span style={{ fontSize: "13px", color: "#ffffff", fontWeight: "500" }}>
                  I confirm that I want to create these {tasks.length} subtasks under Story {plan.story_id} in Zoho Sprints.
                </span>
              </label>
            </div>

            <div className="modal-footer">
              <button
                onClick={() => setShowConfirmModal(false)}
                className="btn btn-secondary"
                disabled={executing}
              >
                Cancel
              </button>
              <button
                onClick={handleExecute}
                className="btn btn-primary"
                disabled={!confirmAcknowledged || executing || (plan.validation ? !plan.validation.valid : false)}
                style={{
                  background: confirmAcknowledged && (!plan.validation || plan.validation.valid)
                    ? "linear-gradient(135deg, #10b981 0%, #059669 100%)"
                    : undefined,
                  minWidth: "150px",
                }}
              >
                {executing ? "Creating..." : "Confirm & Create Tasks"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

