"use client";

import { useEffect, useState, useMemo, useRef } from "react";
import Link from "next/link";
import {
  fetchSprintStories,
  bulkGeneratePlans,
  bulkExecutePlans,
  listExecutions,
  fetchDashboardMetrics,
  ApiError,
} from "@/lib/api-client";
import {
  SprintStoryItem,
  SprintStoriesResponse,
  ExecutionRecord,
  BulkPlanItem,
  BulkExecuteItem,
  DashboardMetrics,
} from "@/lib/types";
import { useToast } from "@/components/ui/Toast";

export default function DashboardPage() {
  const toast = useToast();

  // Metrics & Activity state
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [metricsError, setMetricsError] = useState<string | null>(null);
  const [loadingMetrics, setLoadingMetrics] = useState(true);
  const [executions, setExecutions] = useState<ExecutionRecord[]>([]);
  const [loadingExecutions, setLoadingExecutions] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string>("Just now");

  // Story & Sprint Workflow State
  const [storyIdInput, setStoryIdInput] = useState("39713000007827664");
  const [sprintLoading, setSprintLoading] = useState(false);
  const [sprintError, setSprintError] = useState<string | null>(null);
  const [sprintData, setSprintData] = useState<SprintStoriesResponse | null>(null);
  const [filterAssignedToMe, setFilterAssignedToMe] = useState(true);

  // Table Filters & Selection
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [taskFilter, setTaskFilter] = useState<"ALL" | "NO_TASKS" | "HAS_TASKS">("ALL");
  const [selectedStoryIds, setSelectedStoryIds] = useState<Set<string>>(new Set());

  // Task Creation & Confirmation Flow
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [skipExistingTasks, setSkipExistingTasks] = useState(true);
  const [isDryRun, setIsDryRun] = useState(false);

  // Execution Progress state
  const [executing, setExecuting] = useState(false);
  const [executionProgress, setExecutionProgress] = useState<{
    stage: string;
    completed: number;
    total: number;
    currentStoryTitle: string;
  } | null>(null);
  const [storyProgressList, setStoryProgressList] = useState<
    Array<{ storyId: string; title: string; status: "pending" | "processing" | "done" | "error"; countText: string }>
  >([]);
  const [executionResultSummary, setExecutionResultSummary] = useState<{
    successfulTasks: number;
    skippedTasks: number;
    failedTasks: number;
    totalStories: number;
  } | null>(null);

  const storyInputRef = useRef<HTMLInputElement | null>(null);

  // Load real KPI metrics from dedicated backend endpoint
  const loadMetrics = async (sid?: string) => {
    setLoadingMetrics(true);
    setMetricsError(null);
    try {
      const data = await fetchDashboardMetrics(sid || storyIdInput);
      setMetrics(data);
      setLastUpdated(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    } catch (err: unknown) {
      setMetricsError((err as Error)?.message || "Unable to load");
    } finally {
      setLoadingMetrics(false);
    }
  };

  // Load execution history for Recent Activity
  const loadExecutions = async () => {
    setLoadingExecutions(true);
    try {
      const data = await listExecutions();
      setExecutions(data);
    } catch {
      // Fallback
    } finally {
      setLoadingExecutions(false);
    }
  };

  const handleRefreshAll = () => {
    loadMetrics();
    loadExecutions();
    if (storyIdInput) {
      handleFetchSprint(storyIdInput, filterAssignedToMe);
    }
  };

  useEffect(() => {
    loadMetrics();
    loadExecutions();
    // Auto-fetch default sprint on mount
    handleFetchSprint("39713000007827664", true);
  }, []);

  // Fetch sprint stories
  const handleFetchSprint = async (sidToFetch: string, devOnly: boolean) => {
    const cleanId = sidToFetch.trim();
    if (!cleanId) return;

    loadMetrics(cleanId);
    setSprintLoading(true);
    setSprintError(null);
    setExecutionResultSummary(null);

    try {
      const resp = await fetchSprintStories(cleanId, devOnly);
      setSprintData(resp);
      setSelectedStoryIds(new Set());
      toast.success(`Loaded ${resp.sprint_name || "Sprint"}: ${resp.matched_stories_count} Stories`);
    } catch (err: unknown) {
      const msg =
        err instanceof ApiError
          ? err.detail
          : (err as Error)?.message || "Unable to retrieve Stories for this Sprint.";
      setSprintError(msg);
      toast.error(msg);
    } finally {
      setSprintLoading(false);
    }
  };

  const handleToggleDevFilter = (devOnly: boolean) => {
    setFilterAssignedToMe(devOnly);
    if (storyIdInput.trim()) {
      handleFetchSprint(storyIdInput, devOnly);
    }
  };

  // Filtered stories in data table
  const displayedStories = useMemo(() => {
    if (!sprintData?.stories) return [];
    return sprintData.stories.filter((story) => {
      // Search term
      if (searchTerm.trim()) {
        const q = searchTerm.toLowerCase();
        const matchesName = story.name.toLowerCase().includes(q);
        const matchesId = story.story_id.toLowerCase().includes(q);
        const matchesOwner = story.dev_owner_name?.toLowerCase().includes(q) || false;
        if (!matchesName && !matchesId && !matchesOwner) return false;
      }

      // Status filter
      if (statusFilter !== "ALL") {
        if ((story.status || "").toUpperCase() !== statusFilter.toUpperCase()) return false;
      }

      // Task count filter
      const taskCount = story.existing_tasks_count || 0;
      if (taskFilter === "NO_TASKS" && taskCount > 0) return false;
      if (taskFilter === "HAS_TASKS" && taskCount === 0) return false;

      return true;
    });
  }, [sprintData, searchTerm, statusFilter, taskFilter]);

  // Selection helpers
  const handleToggleSelectOne = (storyId: string) => {
    const updated = new Set(selectedStoryIds);
    if (updated.has(storyId)) {
      updated.delete(storyId);
    } else {
      updated.add(storyId);
    }
    setSelectedStoryIds(updated);
  };

  const handleSelectAllDisplayed = () => {
    const updated = new Set(selectedStoryIds);
    displayedStories.forEach((s) => updated.add(s.story_id));
    setSelectedStoryIds(updated);
  };

  const handleClearSelection = () => {
    setSelectedStoryIds(new Set());
  };

  const isAllDisplayedSelected =
    displayedStories.length > 0 && displayedStories.every((s) => selectedStoryIds.has(s.story_id));
  const isSomeDisplayedSelected =
    displayedStories.some((s) => selectedStoryIds.has(s.story_id)) && !isAllDisplayedSelected;

  // Selected stories list for confirmation modal
  const selectedStoriesList = useMemo(() => {
    if (!sprintData?.stories) return [];
    return sprintData.stories.filter((s) => selectedStoryIds.has(s.story_id));
  }, [sprintData, selectedStoryIds]);

  // Estimated tasks: ~6-8 tasks per story
  const estimatedTasksCount = selectedStoriesList.length * 6;

  const storiesWithExistingTasks = selectedStoriesList.filter(
    (s) => (s.existing_tasks_count || 0) > 0 || s.has_existing_tasks
  );

  // Execute task creation flow
  const handleStartTaskCreation = async () => {
    if (selectedStoriesList.length === 0) return;
    setShowConfirmModal(false);
    setExecuting(true);
    setExecutionResultSummary(null);

    const initialProgress = selectedStoriesList.map((s) => ({
      storyId: s.story_id,
      title: s.name,
      status: "pending" as const,
      countText: "0/6",
    }));
    setStoryProgressList(initialProgress);

    let totalCreated = 0;
    let totalSkipped = 0;
    let totalFailed = 0;

    const targetList = [...selectedStoriesList];

    for (let i = 0; i < targetList.length; i++) {
      const story = targetList[i];

      // If user chose to skip already processed stories
      if (skipExistingTasks && ((story.existing_tasks_count || 0) > 0 || story.has_existing_tasks)) {
        totalSkipped += 1;
        setStoryProgressList((prev) =>
          prev.map((item) =>
            item.storyId === story.story_id
              ? { ...item, status: "done", countText: "Skipped (Tasks Exist)" }
              : item
          )
        );
        continue;
      }

      // Update progress state
      setExecutionProgress({
        stage: `Processing ${story.name}`,
        completed: i,
        total: targetList.length,
        currentStoryTitle: story.name,
      });

      setStoryProgressList((prev) =>
        prev.map((item) =>
          item.storyId === story.story_id ? { ...item, status: "processing", countText: "Generating..." } : item
        )
      );

      try {
        // 1. Generate Plan
        const planResp = await bulkGeneratePlans([story.story_id]);
        const planItem = planResp.results?.[0];

        if (!planItem || !planItem.success || !planItem.plan?.plan_id) {
          throw new Error(planItem?.error || "AI Task Plan generation failed.");
        }

        const planId = planItem.plan.plan_id;
        const taskCount = planItem.plan.tasks.length;

        setStoryProgressList((prev) =>
          prev.map((item) =>
            item.storyId === story.story_id
              ? { ...item, countText: isDryRun ? `Simulating ${taskCount}` : `Creating ${taskCount}...` }
              : item
          )
        );

        // 2. Execute Plan
        const execResp = await bulkExecutePlans([planId], isDryRun, true);
        const execItem = execResp.results?.[0];

        if (execItem?.success && execItem.result) {
          totalCreated += execItem.result.created_tasks;
          totalSkipped += execItem.result.skipped_tasks;
          totalFailed += execItem.result.failed_tasks;

          setStoryProgressList((prev) =>
            prev.map((item) =>
              item.storyId === story.story_id
                ? {
                    ...item,
                    status: "done",
                    countText: `${execItem.result?.created_tasks || taskCount}/${taskCount}`,
                  }
                : item
            )
          );
        } else {
          totalFailed += 1;
          setStoryProgressList((prev) =>
            prev.map((item) =>
              item.storyId === story.story_id
                ? { ...item, status: "error", countText: "Execution error" }
                : item
            )
          );
        }
      } catch (err: unknown) {
        totalFailed += 1;
        setStoryProgressList((prev) =>
          prev.map((item) =>
            item.storyId === story.story_id
              ? {
                  ...item,
                  status: "error",
                  countText: (err as Error)?.message || "Failed",
                }
              : item
          )
        );
      }
    }

    setExecutionProgress(null);
    setExecuting(false);
    setExecutionResultSummary({
      successfulTasks: totalCreated,
      skippedTasks: totalSkipped,
      failedTasks: totalFailed,
      totalStories: targetList.length,
    });

    toast.success(
      `Task Creation Complete: ${totalCreated} created, ${totalSkipped} skipped, ${totalFailed} failed.`
    );
    loadExecutions();
    loadMetrics();
  };

  // Helper to render KPI numeric value with skeleton / error handling
  const renderMetricValue = (val: number | undefined | null) => {
    if (loadingMetrics) {
      return <div className="skeleton" style={{ height: "30px", width: "56px", borderRadius: "4px" }} />;
    }
    if (metricsError || val === undefined || val === null) {
      return <span style={{ color: "var(--text-muted)" }}>—</span>;
    }
    return <span>{val}</span>;
  };

  // Helper to render KPI subtext with error handling
  const renderMetricSubtext = (text: string) => {
    if (metricsError) {
      return (
        <div className="metric-subtext" style={{ color: "var(--color-error)" }}>
          Unable to load
        </div>
      );
    }
    return <div className="metric-subtext">{text}</div>;
  };

  // Unique statuses in sprint for dropdown filter
  const uniqueStatuses = useMemo(() => {
    if (!sprintData?.stories) return [];
    const set = new Set<string>();
    sprintData.stories.forEach((s) => {
      if (s.status) set.add(s.status);
    });
    return Array.from(set);
  }, [sprintData]);

  return (
    <div className="page-container" style={{ paddingBottom: "100px" }}>
      {/* 1. Header Section */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: "28px",
          flexWrap: "wrap",
          gap: "16px",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "4px" }}>
            <h1
              style={{
                fontSize: "24px",
                fontWeight: "800",
                letterSpacing: "-0.02em",
                color: "#ffffff",
              }}
            >
              Task Automation
            </h1>
            <span
              className="badge"
              style={{
                background: "rgba(99, 102, 241, 0.12)",
                color: "#a5b4fc",
                border: "1px solid rgba(99, 102, 241, 0.25)",
                fontSize: "11px",
              }}
            >
              PROD
            </span>
          </div>
          <p style={{ color: "var(--text-secondary)", fontSize: "14px" }}>
            Monitor Stories, task creation, and automation activity.
          </p>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>
            Updated {lastUpdated}
          </div>
          <button
            onClick={() => {
              loadExecutions();
              if (storyIdInput) handleFetchSprint(storyIdInput, filterAssignedToMe);
            }}
            className="btn btn-secondary"
            style={{ fontSize: "12px", padding: "6px 12px" }}
            title="Refresh dashboard data"
          >
            Refresh ↺
          </button>
          <button
            onClick={() => {
              if (storyInputRef.current) {
                storyInputRef.current.focus();
                storyInputRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
              }
            }}
            className="btn btn-primary"
            style={{ fontSize: "13px", padding: "8px 16px" }}
          >
            Create Tasks +
          </button>
        </div>
      </div>

      {/* 2. KPI / Metrics Section - Real Numeric Counts */}
      <div className="metric-grid-3x2">
        {/* Card 1: Stories Processed Today */}
        <div className="metric-card" id="kpi-stories-processed-today">
          <div className="metric-label">Stories Processed Today</div>
          <div className="metric-value">
            {renderMetricValue(metrics?.storiesProcessedToday)}
          </div>
          {renderMetricSubtext("Stories processed today")}
        </div>

        {/* Card 2: Tasks Created Today */}
        <div className="metric-card" id="kpi-tasks-created-today">
          <div className="metric-label">Tasks Created Today</div>
          <div className="metric-value" style={{ color: "var(--color-success)" }}>
            {renderMetricValue(metrics?.tasksCreatedToday)}
          </div>
          {renderMetricSubtext("Tasks created today")}
        </div>

        {/* Card 3: Stories Processed */}
        <div className="metric-card" id="kpi-stories-processed">
          <div className="metric-label">Stories Processed</div>
          <div className="metric-value">
            {renderMetricValue(metrics?.storiesProcessed)}
          </div>
          {renderMetricSubtext("Stories all-time")}
        </div>

        {/* Card 4: Total Tasks Created */}
        <div className="metric-card" id="kpi-total-tasks-created">
          <div className="metric-label">Total Tasks Created</div>
          <div className="metric-value">
            {renderMetricValue(metrics?.tasksCreated)}
          </div>
          {renderMetricSubtext("Tasks all-time")}
        </div>

        {/* Card 5: Stories Assigned to Me */}
        <div className="metric-card" id="kpi-stories-assigned-to-me">
          <div className="metric-label">Stories Assigned to Me</div>
          <div className="metric-value" style={{ color: "var(--accent-primary)" }}>
            {loadingMetrics && sprintLoading ? (
              <div className="skeleton" style={{ height: "30px", width: "56px", borderRadius: "4px" }} />
            ) : metricsError && sprintError ? (
              <span style={{ color: "var(--text-muted)" }}>—</span>
            ) : (
              <span>{sprintData?.matched_stories_count ?? metrics?.storiesAssignedToMe ?? 0}</span>
            )}
          </div>
          {metricsError && sprintError
            ? renderMetricSubtext("Unable to load")
            : renderMetricSubtext("Stories in sprint")}
        </div>

        {/* Card 6: Failed Today */}
        <div
          className="metric-card"
          id="kpi-failed-today"
          style={
            metrics && metrics.failedToday > 0
              ? { borderColor: "rgba(239, 68, 68, 0.4)", background: "rgba(239, 68, 68, 0.05)" }
              : undefined
          }
        >
          <div className="metric-label">Failed Today</div>
          <div
            className="metric-value"
            style={{
              color: metrics && metrics.failedToday > 0 ? "var(--color-error)" : undefined,
            }}
          >
            {renderMetricValue(metrics?.failedToday)}
          </div>
          {renderMetricSubtext("Executions today")}
        </div>
      </div>

      {/* 3. Primary Workflow: Stories Processing Section */}
      <section style={{ marginBottom: "36px" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "16px",
            flexWrap: "wrap",
            gap: "12px",
          }}
        >
          <div>
            <h2 style={{ fontSize: "18px", fontWeight: "700", color: "#ffffff" }}>
              Stories
            </h2>
            <div style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
              Provide a Story ID to resolve its Sprint, filter developer ownership, and trigger batch task creation.
            </div>
          </div>

          <Link
            href="/bulk"
            className="btn btn-secondary"
            style={{ fontSize: "12px", padding: "6px 12px" }}
          >
            ⚡ Bulk Action Studio (Paste / CSV) →
          </Link>
        </div>

        {/* Story ID Input Bar */}
        <div
          className="card"
          style={{
            padding: "16px 20px",
            marginBottom: "20px",
            background: "rgba(16, 23, 38, 0.6)",
          }}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleFetchSprint(storyIdInput, filterAssignedToMe);
            }}
            style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}
          >
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <label
                htmlFor="storyId"
                style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", color: "var(--text-muted)", letterSpacing: "0.05em" }}
              >
                Story ID
              </label>
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <input
                  ref={storyInputRef}
                  id="storyId"
                  type="text"
                  className="input"
                  placeholder="e.g. 39713000007827664"
                  value={storyIdInput}
                  onChange={(e) => setStoryIdInput(e.target.value)}
                  style={{ width: "280px", height: "38px", fontSize: "13px", fontFamily: "var(--font-mono)" }}
                />
                <button
                  type="submit"
                  disabled={sprintLoading || !storyIdInput.trim()}
                  className="btn btn-primary"
                  style={{ height: "38px", padding: "0 18px", fontSize: "13px" }}
                >
                  {sprintLoading ? "Resolving Sprint..." : "Fetch Sprint →"}
                </button>
              </div>
            </div>

            {/* Quick Demo ID button */}
            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: "10px" }}>
              <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>Sample ID:</span>
              <button
                type="button"
                onClick={() => {
                  setStoryIdInput("39713000007827664");
                  handleFetchSprint("39713000007827664", filterAssignedToMe);
                }}
                className="btn btn-secondary"
                style={{ fontSize: "11px", padding: "4px 8px", fontFamily: "var(--font-mono)" }}
              >
                39713000007827664
              </button>
            </div>
          </form>

          {/* Error Message */}
          {sprintError && (
            <div
              style={{
                marginTop: "14px",
                padding: "10px 14px",
                background: "rgba(239, 68, 68, 0.1)",
                border: "1px solid rgba(239, 68, 68, 0.25)",
                borderRadius: "var(--radius-sm)",
                color: "#fca5a5",
                fontSize: "13px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <div>
                <strong>Unable to load Stories:</strong> {sprintError}
              </div>
              <button
                onClick={() => handleFetchSprint(storyIdInput, filterAssignedToMe)}
                className="btn btn-secondary"
                style={{ fontSize: "11px", padding: "3px 8px" }}
              >
                Retry
              </button>
            </div>
          )}
        </div>

        {/* Sprint Header Badge & Filter Switch */}
        {sprintData && (
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "16px",
              padding: "14px 18px",
              background: "rgba(99, 102, 241, 0.05)",
              border: "1px solid rgba(99, 102, 241, 0.2)",
              borderRadius: "var(--radius-md)",
              flexWrap: "wrap",
              gap: "12px",
            }}
          >
            <div>
              <div style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", color: "var(--accent-primary)", letterSpacing: "0.06em" }}>
                Detected Sprint
              </div>
              <div style={{ fontSize: "17px", fontWeight: "700", color: "#ffffff", marginTop: "2px" }}>
                {sprintData.sprint_name || `Sprint ${sprintData.sprint_id}`}
              </div>
              <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "2px" }}>
                {sprintData.total_sprint_stories} Total Stories ·{" "}
                <span style={{ color: "var(--color-success)", fontWeight: 600 }}>
                  {sprintData.matched_stories_count} assigned to you
                </span>{" "}
                (Owner: {sprintData.current_user_dev_name || "Ankit Singh"})
              </div>
            </div>

            {/* Toggle: Assigned to me vs All Sprint Stories */}
            <div
              style={{
                display: "inline-flex",
                background: "rgba(0, 0, 0, 0.3)",
                padding: "3px",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-subtle)",
              }}
            >
              <button
                onClick={() => handleToggleDevFilter(true)}
                style={{
                  background: filterAssignedToMe ? "var(--accent-primary)" : "transparent",
                  color: filterAssignedToMe ? "#ffffff" : "var(--text-secondary)",
                  border: "none",
                  padding: "5px 12px",
                  borderRadius: "4px",
                  fontSize: "12px",
                  fontWeight: 600,
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                }}
              >
                Assigned to Me ({sprintData.matched_stories_count})
              </button>
              <button
                onClick={() => handleToggleDevFilter(false)}
                style={{
                  background: !filterAssignedToMe ? "var(--accent-primary)" : "transparent",
                  color: !filterAssignedToMe ? "#ffffff" : "var(--text-secondary)",
                  border: "none",
                  padding: "5px 12px",
                  borderRadius: "4px",
                  fontSize: "12px",
                  fontWeight: 600,
                  cursor: "pointer",
                  transition: "all 0.15s ease",
                }}
              >
                All Sprint Stories ({sprintData.total_sprint_stories})
              </button>
            </div>
          </div>
        )}

        {/* 4. Story Selection UI: Professional Data Table */}
        <div className="data-table-wrapper">
          {/* Table Controls Bar */}
          <div
            style={{
              padding: "12px 16px",
              background: "rgba(16, 23, 38, 0.5)",
              borderBottom: "1px solid var(--border-subtle)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              flexWrap: "wrap",
              gap: "12px",
            }}
          >
            {/* Search Input */}
            <div style={{ display: "flex", alignItems: "center", gap: "10px", flex: 1, minWidth: "220px" }}>
              <input
                type="text"
                className="input"
                placeholder="Search stories by title, ID, or owner..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                style={{ height: "34px", fontSize: "12px", maxWidth: "340px" }}
              />
              {searchTerm && (
                <button
                  onClick={() => setSearchTerm("")}
                  className="btn btn-secondary"
                  style={{ height: "34px", padding: "0 8px", fontSize: "11px" }}
                >
                  Clear
                </button>
              )}
            </div>

            {/* Filter Dropdowns */}
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              {/* Status filter */}
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="input"
                style={{ height: "34px", fontSize: "12px", padding: "0 8px", width: "auto" }}
              >
                <option value="ALL">All Statuses</option>
                {uniqueStatuses.map((st) => (
                  <option key={st} value={st}>
                    {st}
                  </option>
                ))}
              </select>

              {/* Existing task filter */}
              <select
                value={taskFilter}
                onChange={(e) => setTaskFilter(e.target.value as any)}
                className="input"
                style={{ height: "34px", fontSize: "12px", padding: "0 8px", width: "auto" }}
              >
                <option value="ALL">All Task States</option>
                <option value="NO_TASKS">No Existing Tasks</option>
                <option value="HAS_TASKS">Already Has Tasks</option>
              </select>

              {/* Selection Count Pill */}
              <div style={{ fontSize: "12px", color: "var(--text-muted)", marginLeft: "4px" }}>
                <span style={{ color: "#ffffff", fontWeight: 700 }}>{selectedStoryIds.size}</span> of{" "}
                {displayedStories.length} selected
              </div>
            </div>
          </div>

          {/* Table Content */}
          <div style={{ overflowX: "auto" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: "40px", textAlign: "center" }}>
                    <input
                      type="checkbox"
                      className="custom-checkbox"
                      checked={isAllDisplayedSelected}
                      ref={(el) => {
                        if (el) el.indeterminate = isSomeDisplayedSelected;
                      }}
                      onChange={() => {
                        if (isAllDisplayedSelected) {
                          handleClearSelection();
                        } else {
                          handleSelectAllDisplayed();
                        }
                      }}
                      title="Select / Unselect All Displayed"
                    />
                  </th>
                  <th style={{ width: "160px" }}>Story ID</th>
                  <th>Story Title</th>
                  <th style={{ width: "140px" }}>Owner</th>
                  <th style={{ width: "100px" }}>Status</th>
                  <th style={{ width: "110px" }}>Existing Tasks</th>
                  <th style={{ width: "110px" }}>Processing</th>
                  <th style={{ width: "80px", textAlign: "right" }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {sprintLoading ? (
                  <tr>
                    <td colSpan={8} style={{ padding: "40px", textAlign: "center" }}>
                      <div className="skeleton" style={{ height: "24px", width: "60%", margin: "0 auto 8px" }} />
                      <div className="skeleton" style={{ height: "24px", width: "40%", margin: "0 auto" }} />
                    </td>
                  </tr>
                ) : displayedStories.length === 0 ? (
                  <tr>
                    <td colSpan={8} style={{ padding: "48px 24px", textAlign: "center" }}>
                      <div style={{ fontSize: "36px", marginBottom: "8px" }}>🔍</div>
                      <div style={{ fontSize: "15px", fontWeight: "700", color: "#ffffff", marginBottom: "4px" }}>
                        No Stories Found
                      </div>
                      <p style={{ color: "var(--text-muted)", fontSize: "13px", marginBottom: "16px" }}>
                        {filterAssignedToMe
                          ? "We couldn't find any Stories assigned to you in this Sprint."
                          : "No Stories matched your search or status filter."}
                      </p>
                      <button
                        onClick={() => {
                          setSearchTerm("");
                          setStatusFilter("ALL");
                          setTaskFilter("ALL");
                          handleToggleDevFilter(false);
                        }}
                        className="btn btn-secondary"
                        style={{ fontSize: "12px" }}
                      >
                        Reset Filters
                      </button>
                    </td>
                  </tr>
                ) : (
                  displayedStories.map((story) => {
                    const isSelected = selectedStoryIds.has(story.story_id);
                    const taskCount = story.existing_tasks_count || 0;
                    const hasTasks = taskCount > 0 || story.has_existing_tasks;

                    return (
                      <tr
                        key={story.story_id}
                        className={`table-row ${isSelected ? "selected" : ""}`}
                        onClick={() => handleToggleSelectOne(story.story_id)}
                        style={{ cursor: "pointer" }}
                      >
                        <td
                          style={{ textAlign: "center" }}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleToggleSelectOne(story.story_id);
                          }}
                        >
                          <input
                            type="checkbox"
                            className="custom-checkbox"
                            checked={isSelected}
                            onChange={() => handleToggleSelectOne(story.story_id)}
                          />
                        </td>
                        <td style={{ fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--text-secondary)" }}>
                          <Link
                            href={`/stories/${story.story_id}`}
                            onClick={(e) => e.stopPropagation()}
                            style={{ color: "var(--accent-primary)", textDecoration: "none", fontWeight: 600 }}
                          >
                            {story.story_id} ↗
                          </Link>
                        </td>
                        <td>
                          <div style={{ fontWeight: 600, color: "#ffffff", marginBottom: "2px" }}>
                            {story.name}
                          </div>
                          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                            {story.item_type_name && (
                              <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                                {story.item_type_name}
                              </span>
                            )}
                            {story.priority_name && (
                              <>
                                <span style={{ color: "var(--border-subtle)" }}>•</span>
                                <span style={{ fontSize: "11px", color: "var(--color-warning)" }}>
                                  {story.priority_name}
                                </span>
                              </>
                            )}
                            {story.point != null && (
                              <>
                                <span style={{ color: "var(--border-subtle)" }}>•</span>
                                <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                                  {story.point} pts
                                </span>
                              </>
                            )}
                          </div>
                        </td>
                        <td style={{ fontSize: "12px" }}>
                          {story.dev_owner_name ? (
                            <span style={{ color: "#ffffff", fontWeight: 500 }}>
                              {story.dev_owner_name}
                            </span>
                          ) : (
                            <span style={{ color: "var(--text-muted)" }}>Unassigned</span>
                          )}
                        </td>
                        <td>
                          <span
                            className="badge"
                            style={{
                              fontSize: "11px",
                              background:
                                (story.status || "").toLowerCase() === "closed"
                                  ? "rgba(16, 185, 129, 0.12)"
                                  : "rgba(255, 255, 255, 0.05)",
                              color:
                                (story.status || "").toLowerCase() === "closed"
                                  ? "#6ee7b7"
                                  : "var(--text-secondary)",
                              border: "1px solid var(--border-subtle)",
                            }}
                          >
                            {story.status || "Ready"}
                          </span>
                        </td>
                        <td>
                          {hasTasks ? (
                            <span
                              className="badge badge-warning"
                              style={{ fontSize: "11px" }}
                              title="Subtasks already exist in Zoho Sprints"
                            >
                              ⚠ {taskCount} tasks
                            </span>
                          ) : (
                            <span
                              className="badge badge-success"
                              style={{ fontSize: "11px" }}
                            >
                              0 tasks
                            </span>
                          )}
                        </td>
                        <td>
                          {hasTasks ? (
                            <span style={{ fontSize: "11px", color: "var(--color-warning)" }}>
                              Created
                            </span>
                          ) : (
                            <span style={{ fontSize: "11px", color: "#6ee7b7" }}>
                              Ready
                            </span>
                          )}
                        </td>
                        <td style={{ textAlign: "right" }}>
                          <Link
                            href={`/stories/${story.story_id}`}
                            onClick={(e) => e.stopPropagation()}
                            className="btn btn-secondary"
                            style={{ fontSize: "11px", padding: "3px 8px" }}
                          >
                            Inspect
                          </Link>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>



      {/* 6. Execution Result Card */}
      {executionResultSummary && (
        <div
          className="card"
          style={{
            marginBottom: "36px",
            background: "rgba(16, 185, 129, 0.08)",
            border: "1px solid rgba(16, 185, 129, 0.3)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                <span className="badge badge-success">Task Creation Complete</span>
                <span style={{ fontSize: "14px", fontWeight: 700, color: "#ffffff" }}>
                  {executionResultSummary.totalStories} Stories Processed
                </span>
              </div>
              <div style={{ fontSize: "14px", color: "var(--text-secondary)" }}>
                <strong style={{ color: "var(--color-success)" }}>
                  {executionResultSummary.successfulTasks} tasks created successfully
                </strong>{" "}
                · {executionResultSummary.skippedTasks} skipped ·{" "}
                <span style={{ color: executionResultSummary.failedTasks > 0 ? "var(--color-error)" : "inherit" }}>
                  {executionResultSummary.failedTasks} failed
                </span>
              </div>
            </div>

            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <Link href="/executions" className="btn btn-secondary" style={{ fontSize: "12px" }}>
                View Activity →
              </Link>
              <button
                onClick={() => setExecutionResultSummary(null)}
                className="btn btn-secondary"
                style={{ fontSize: "12px" }}
              >
                Dismiss
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 7. Recent Activity Section on Dashboard */}
      <section>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "16px",
          }}
        >
          <div>
            <h2 style={{ fontSize: "18px", fontWeight: "700", color: "#ffffff" }}>
              Recent Activity
            </h2>
            <div style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
              Audit trail of tasks generated and executed in Zoho Sprints.
            </div>
          </div>
          <Link
            href="/executions"
            style={{ fontSize: "13px", color: "var(--accent-primary)", textDecoration: "none", fontWeight: 600 }}
          >
            View all activity →
          </Link>
        </div>

        <div className="data-table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: "120px" }}>Timestamp</th>
                <th>Story ID / Execution</th>
                <th style={{ width: "140px" }}>Action</th>
                <th style={{ width: "120px" }}>Tasks Created</th>
                <th style={{ width: "120px" }}>Status</th>
                <th style={{ width: "160px" }}>Developer</th>
                <th style={{ width: "80px", textAlign: "right" }}>Log</th>
              </tr>
            </thead>
            <tbody>
              {loadingMetrics ? (
                <tr>
                  <td colSpan={7} style={{ padding: "30px", textAlign: "center" }}>
                    <div className="skeleton" style={{ height: "20px", width: "50%", margin: "0 auto" }} />
                  </td>
                </tr>
              ) : executions.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: "36px", textAlign: "center", color: "var(--text-muted)" }}>
                    No recent automation activity recorded yet.
                  </td>
                </tr>
              ) : (
                executions.slice(0, 5).map((exec) => {
                  const statusClass =
                    exec.status === "COMPLETED"
                      ? "badge-success"
                      : exec.status === "PARTIAL"
                      ? "badge-warning"
                      : "badge-error";

                  return (
                    <tr key={exec.execution_id} className="table-row">
                      <td style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                        {new Date(exec.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </td>
                      <td>
                        <div style={{ fontWeight: 600, color: "#ffffff", fontSize: "13px" }}>
                          {exec.story_id || exec.plan_id || "Batch Process"}
                        </div>
                        <div style={{ fontSize: "11px", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                          {exec.execution_id}
                        </div>
                      </td>
                      <td>
                        <span style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                          Task Creation
                        </span>
                      </td>
                      <td style={{ fontWeight: 600, color: "var(--color-success)" }}>
                        {exec.created_count} tasks
                      </td>
                      <td>
                        <span className={`badge ${statusClass}`} style={{ fontSize: "11px" }}>
                          {exec.status}
                        </span>
                      </td>
                      <td style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                        Ankit Singh
                      </td>
                      <td style={{ textAlign: "right" }}>
                        <Link
                          href={`/executions/${exec.execution_id}`}
                          className="btn btn-secondary"
                          style={{ fontSize: "11px", padding: "2px 8px" }}
                        >
                          View →
                        </Link>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* 8. Confirmation Modal Dialog */}
      {showConfirmModal && (
        <div className="modal-backdrop" onClick={() => !executing && setShowConfirmModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ fontSize: "16px", fontWeight: "700", color: "#ffffff" }}>
                Create Tasks Confirmation
              </h3>
              <button
                onClick={() => setShowConfirmModal(false)}
                disabled={executing}
                style={{ background: "transparent", border: "none", color: "var(--text-muted)", cursor: "pointer", fontSize: "18px" }}
              >
                ✕
              </button>
            </div>

            <div className="modal-body">
              <div style={{ marginBottom: "20px" }}>
                <p style={{ fontSize: "14px", color: "var(--text-secondary)", marginBottom: "14px" }}>
                  You are about to generate and create subtasks in Zoho Sprints for{" "}
                  <strong style={{ color: "#ffffff" }}>{selectedStoriesList.length} Stories</strong>.
                </p>

                {/* Estimate info card */}
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: "12px",
                    padding: "14px",
                    background: "rgba(255, 255, 255, 0.03)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "var(--radius-md)",
                    marginBottom: "16px",
                  }}
                >
                  <div>
                    <div style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase" }}>
                      Selected Stories
                    </div>
                    <div style={{ fontSize: "20px", fontWeight: 800, color: "#ffffff" }}>
                      {selectedStoriesList.length}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: "11px", color: "var(--text-muted)", textTransform: "uppercase" }}>
                      Estimated Subtasks
                    </div>
                    <div style={{ fontSize: "20px", fontWeight: 800, color: "var(--accent-primary)" }}>
                      ~{estimatedTasksCount}
                    </div>
                  </div>
                </div>

                {/* Duplicate Warning */}
                {storiesWithExistingTasks.length > 0 && (
                  <div
                    style={{
                      background: "rgba(245, 158, 11, 0.08)",
                      border: "1px solid rgba(245, 158, 11, 0.3)",
                      borderRadius: "var(--radius-md)",
                      padding: "14px",
                      marginBottom: "16px",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#fde047", fontWeight: 700, fontSize: "13px", marginBottom: "4px" }}>
                      <span>⚠</span> {storiesWithExistingTasks.length} Selected{" "}
                      {storiesWithExistingTasks.length === 1 ? "Story already has" : "Stories already have"}{" "}
                      tasks
                    </div>
                    <p style={{ fontSize: "12px", color: "var(--text-secondary)", marginBottom: "10px" }}>
                      To prevent accidental duplicates, you can skip stories that already have existing subtasks.
                    </p>

                    <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", color: "#ffffff", cursor: "pointer" }}>
                      <input
                        type="checkbox"
                        className="custom-checkbox"
                        checked={skipExistingTasks}
                        onChange={(e) => setSkipExistingTasks(e.target.checked)}
                      />
                      <span>Skip Stories that already have subtasks (Recommended)</span>
                    </label>
                  </div>
                )}

                {/* Dry Run Toggle */}
                <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", color: "var(--text-secondary)", cursor: "pointer", marginBottom: "16px" }}>
                  <input
                    type="checkbox"
                    className="custom-checkbox"
                    checked={isDryRun}
                    onChange={(e) => setIsDryRun(e.target.checked)}
                  />
                  <span>Simulate with Dry Run (Preview API payloads without writing to Zoho)</span>
                </label>

                {/* Stories List Preview */}
                <div style={{ fontSize: "12px", color: "var(--text-muted)", marginBottom: "8px", fontWeight: 600 }}>
                  Selected Stories:
                </div>
                <div
                  style={{
                    maxHeight: "180px",
                    overflowY: "auto",
                    background: "rgba(0, 0, 0, 0.2)",
                    border: "1px solid var(--border-subtle)",
                    borderRadius: "var(--radius-md)",
                    padding: "8px 12px",
                  }}
                >
                  {selectedStoriesList.map((story) => (
                    <div
                      key={story.story_id}
                      style={{
                        padding: "6px 0",
                        borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        fontSize: "12px",
                      }}
                    >
                      <span style={{ color: "#ffffff", fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "420px" }}>
                        ✓ {story.name}
                      </span>
                      <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-muted)", fontSize: "11px" }}>
                        {story.story_id}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
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
                onClick={handleStartTaskCreation}
                disabled={executing}
                className="btn btn-primary"
                style={{ fontWeight: 700 }}
              >
                {isDryRun ? `Simulate ${estimatedTasksCount} Tasks` : `Create ${estimatedTasksCount} Tasks`}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 9. Execution Live Progress Modal */}
      {executing && (
        <div className="modal-backdrop">
          <div className="modal-card" style={{ maxWidth: "560px" }}>
            <div className="modal-header">
              <h3 style={{ fontSize: "16px", fontWeight: "700", color: "#ffffff" }}>
                Creating Tasks in Zoho Sprints...
              </h3>
            </div>

            <div className="modal-body">
              {/* Progress bar */}
              <div style={{ marginBottom: "16px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "13px", color: "var(--text-secondary)", marginBottom: "6px" }}>
                  <span>Overall Progress</span>
                  <span style={{ fontWeight: 700, color: "#ffffff" }}>
                    {executionProgress ? `${executionProgress.completed} / ${executionProgress.total}` : "Starting..."}
                  </span>
                </div>
                <div className="progress-track">
                  <div
                    className="progress-fill"
                    style={{
                      width: executionProgress
                        ? `${Math.round((executionProgress.completed / executionProgress.total) * 100)}%`
                        : "5%",
                    }}
                  />
                </div>
              </div>

              {/* Per-story checklist */}
              <div
                style={{
                  maxHeight: "260px",
                  overflowY: "auto",
                  background: "rgba(0, 0, 0, 0.2)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "var(--radius-md)",
                  padding: "10px 14px",
                }}
              >
                {storyProgressList.map((item) => (
                  <div
                    key={item.storyId}
                    style={{
                      padding: "8px 0",
                      borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      fontSize: "13px",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", minWidth: 0 }}>
                      <span>
                        {item.status === "done" && <span style={{ color: "var(--color-success)" }}>✓</span>}
                        {item.status === "processing" && <span style={{ color: "var(--accent-primary)" }}>⟳</span>}
                        {item.status === "pending" && <span style={{ color: "var(--text-muted)" }}>○</span>}
                        {item.status === "error" && <span style={{ color: "var(--color-error)" }}>✕</span>}
                      </span>
                      <span
                        style={{
                          color: item.status === "processing" ? "#ffffff" : "var(--text-secondary)",
                          fontWeight: item.status === "processing" ? 600 : 400,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                          maxWidth: "320px",
                        }}
                      >
                        {item.title}
                      </span>
                    </div>

                    <span
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: "12px",
                        color:
                          item.status === "done"
                            ? "var(--color-success)"
                            : item.status === "error"
                            ? "var(--color-error)"
                            : "var(--text-muted)",
                      }}
                    >
                      {item.countText}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
