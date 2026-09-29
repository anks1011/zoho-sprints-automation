"use client";

import { useEffect, useState, useMemo, useRef } from "react";
import Link from "next/link";
import {
  fetchSprintStories,
  bulkGeneratePlans,
  bulkExecutePlans,
  ApiError,
} from "@/lib/api-client";
import {
  SprintStoryItem,
  SprintStoriesResponse,
} from "@/lib/types";
import { useToast } from "@/components/ui/Toast";

export default function StoriesPage() {
  const toast = useToast();

  const [storyIdInput, setStoryIdInput] = useState("39713000007827664");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sprintData, setSprintData] = useState<SprintStoriesResponse | null>(null);
  const [filterAssignedToMe, setFilterAssignedToMe] = useState(true);

  // Table filtering and selection
  const [searchTerm, setSearchTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [selectedStoryIds, setSelectedStoryIds] = useState<Set<string>>(new Set());

  // Task creation execution
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [skipExistingTasks, setSkipExistingTasks] = useState(true);
  const [executing, setExecuting] = useState(false);
  const [executionProgress, setExecutionProgress] = useState<{
    completed: number;
    total: number;
    currentTitle: string;
  } | null>(null);

  const loadSprint = async (sid: string, devOnly: boolean) => {
    const cleanId = sid.trim();
    if (!cleanId) return;

    setLoading(true);
    setError(null);

    try {
      const resp = await fetchSprintStories(cleanId, devOnly);
      setSprintData(resp);
      const defaultSelected = new Set(
        resp.stories
          .filter((s) => !s.has_existing_tasks && (!s.existing_tasks_count || s.existing_tasks_count === 0))
          .map((s) => s.story_id)
      );
      if (defaultSelected.size === 0 && resp.stories.length > 0) {
        resp.stories.forEach((s) => defaultSelected.add(s.story_id));
      }
      setSelectedStoryIds(defaultSelected);
      toast.success(`Loaded Sprint: ${resp.sprint_name || resp.sprint_id}`);
    } catch (err: unknown) {
      const msg =
        err instanceof ApiError
          ? err.detail
          : (err as Error)?.message || "Failed to load sprint stories.";
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSprint("39713000007827664", true);
  }, []);

  const handleToggleFilter = (devOnly: boolean) => {
    setFilterAssignedToMe(devOnly);
    if (storyIdInput.trim()) {
      loadSprint(storyIdInput, devOnly);
    }
  };

  // Filtered stories
  const displayedStories = useMemo(() => {
    if (!sprintData?.stories) return [];
    return sprintData.stories.filter((story) => {
      if (searchTerm.trim()) {
        const q = searchTerm.toLowerCase();
        if (
          !story.name.toLowerCase().includes(q) &&
          !story.story_id.toLowerCase().includes(q) &&
          !story.dev_owner_name?.toLowerCase().includes(q)
        ) {
          return false;
        }
      }
      if (statusFilter !== "ALL") {
        if ((story.status || "").toUpperCase() !== statusFilter.toUpperCase()) return false;
      }
      return true;
    });
  }, [sprintData, searchTerm, statusFilter]);

  const handleToggleSelectOne = (storyId: string) => {
    const updated = new Set(selectedStoryIds);
    if (updated.has(storyId)) {
      updated.delete(storyId);
    } else {
      updated.add(storyId);
    }
    setSelectedStoryIds(updated);
  };

  const handleSelectAll = () => {
    const updated = new Set(selectedStoryIds);
    displayedStories.forEach((s) => updated.add(s.story_id));
    setSelectedStoryIds(updated);
  };

  const handleClearSelection = () => {
    setSelectedStoryIds(new Set());
  };

  const isAllSelected =
    displayedStories.length > 0 && displayedStories.every((s) => selectedStoryIds.has(s.story_id));

  const selectedStories = useMemo(() => {
    if (!sprintData?.stories) return [];
    return sprintData.stories.filter((s) => selectedStoryIds.has(s.story_id));
  }, [sprintData, selectedStoryIds]);

  const estimatedTasks = selectedStories.length * 6;

  // Trigger task creation
  const handleStartCreation = async () => {
    if (selectedStories.length === 0) return;
    setShowConfirmModal(false);
    setExecuting(true);

    let createdCount = 0;
    const target = [...selectedStories];

    for (let i = 0; i < target.length; i++) {
      const story = target[i];
      if (skipExistingTasks && ((story.existing_tasks_count || 0) > 0 || story.has_existing_tasks)) {
        continue;
      }

      setExecutionProgress({
        completed: i,
        total: target.length,
        currentTitle: story.name,
      });

      try {
        const planResp = await bulkGeneratePlans([story.story_id]);
        const planItem = planResp.results?.[0];
        if (planItem?.success && planItem.plan?.plan_id) {
          const execResp = await bulkExecutePlans([planItem.plan.plan_id], false, true);
          if (execResp.results?.[0]?.success) {
            createdCount += execResp.results[0].result?.created_tasks || 6;
          }
        }
      } catch {
        // continue batch
      }
    }

    setExecuting(false);
    setExecutionProgress(null);
    toast.success(`Successfully created ${createdCount} tasks in Zoho Sprints.`);
    loadSprint(storyIdInput, filterAssignedToMe);
  };

  return (
    <div className="page-container" style={{ paddingBottom: "100px" }}>
      {/* Breadcrumb Header */}
      <div style={{ marginBottom: "24px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", color: "var(--text-muted)", marginBottom: "6px" }}>
          <Link href="/" style={{ color: "var(--text-secondary)", textDecoration: "none" }}>
            Dashboard
          </Link>
          <span>/</span>
          <span style={{ color: "var(--text-primary)", fontWeight: 600 }}>Stories</span>
          {sprintData?.sprint_name && (
            <>
              <span>/</span>
              <span style={{ color: "var(--accent-primary)", fontFamily: "var(--font-mono)" }}>
                {sprintData.sprint_name}
              </span>
            </>
          )}
        </div>
        <h1 style={{ fontSize: "24px", fontWeight: "800", color: "#ffffff", letterSpacing: "-0.02em" }}>
          Sprint Stories Workspace
        </h1>
        <p style={{ color: "var(--text-secondary)", fontSize: "14px" }}>
          Explore all stories in the sprint, filter by developer assignment, and bulk-create verified subtasks.
        </p>
      </div>

      {/* Story ID Input & Sprint Resolution Card */}
      <div className="card" style={{ padding: "18px 22px", marginBottom: "24px", background: "rgba(16, 23, 38, 0.6)" }}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            loadSprint(storyIdInput, filterAssignedToMe);
          }}
          style={{ display: "flex", alignItems: "flex-end", gap: "12px", flexWrap: "wrap" }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "6px", flex: 1, minWidth: "260px", maxWidth: "420px" }}>
            <label style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", color: "var(--text-muted)", letterSpacing: "0.05em" }}>
              Enter Story ID to Resolve Sprint
            </label>
            <input
              type="text"
              className="input"
              placeholder="e.g. 39713000007827664"
              value={storyIdInput}
              onChange={(e) => setStoryIdInput(e.target.value)}
              style={{ height: "38px", fontSize: "13px", fontFamily: "var(--font-mono)" }}
            />
          </div>

          <button
            type="submit"
            disabled={loading || !storyIdInput.trim()}
            className="btn btn-primary"
            style={{ height: "38px", padding: "0 18px", fontSize: "13px" }}
          >
            {loading ? "Resolving Sprint..." : "Resolve Sprint →"}
          </button>
        </form>

        {error && (
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
              <strong>Error:</strong> {error}
            </div>
            <button
              onClick={() => loadSprint(storyIdInput, filterAssignedToMe)}
              className="btn btn-secondary"
              style={{ fontSize: "11px", padding: "3px 8px" }}
            >
              Retry
            </button>
          </div>
        )}
      </div>

      {/* Detected Sprint Details */}
      {sprintData && (
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "20px",
            padding: "16px 20px",
            background: "rgba(99, 102, 241, 0.05)",
            border: "1px solid rgba(99, 102, 241, 0.2)",
            borderRadius: "var(--radius-md)",
            flexWrap: "wrap",
            gap: "14px",
          }}
        >
          <div>
            <div style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", color: "var(--accent-primary)", letterSpacing: "0.06em" }}>
              Active Sprint
            </div>
            <div style={{ fontSize: "18px", fontWeight: "800", color: "#ffffff", marginTop: "2px" }}>
              {sprintData.sprint_name || `Sprint ${sprintData.sprint_id}`}
            </div>
            <div style={{ fontSize: "13px", color: "var(--text-muted)", marginTop: "2px" }}>
              {sprintData.total_sprint_stories} Total Stories ·{" "}
              <span style={{ color: "var(--color-success)", fontWeight: 600 }}>
                {sprintData.matched_stories_count} assigned to you
              </span>{" "}
              (Owner: {sprintData.current_user_dev_name || "Ankit Singh"})
            </div>
          </div>

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
              onClick={() => handleToggleFilter(true)}
              style={{
                background: filterAssignedToMe ? "var(--accent-primary)" : "transparent",
                color: filterAssignedToMe ? "#ffffff" : "var(--text-secondary)",
                border: "none",
                padding: "6px 14px",
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
              onClick={() => handleToggleFilter(false)}
              style={{
                background: !filterAssignedToMe ? "var(--accent-primary)" : "transparent",
                color: !filterAssignedToMe ? "#ffffff" : "var(--text-secondary)",
                border: "none",
                padding: "6px 14px",
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

      {/* Data Table */}
      <div className="data-table-wrapper">
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
          <div style={{ display: "flex", alignItems: "center", gap: "10px", flex: 1, minWidth: "220px" }}>
            <input
              type="text"
              className="input"
              placeholder="Search by title, story ID, or developer..."
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

          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>
              <span style={{ color: "#ffffff", fontWeight: 700 }}>{selectedStoryIds.size}</span> of{" "}
              {displayedStories.length} selected
            </div>
            <button
              onClick={isAllSelected ? handleClearSelection : handleSelectAll}
              className="btn btn-secondary"
              style={{ height: "34px", padding: "0 10px", fontSize: "11px" }}
            >
              {isAllSelected ? "Deselect All" : "Select All"}
            </button>
          </div>
        </div>

        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: "40px", textAlign: "center" }}>
                  <input
                    type="checkbox"
                    className="custom-checkbox"
                    checked={isAllSelected}
                    onChange={() => {
                      if (isAllSelected) handleClearSelection();
                      else handleSelectAll();
                    }}
                  />
                </th>
                <th style={{ width: "160px" }}>Story ID</th>
                <th>Title</th>
                <th style={{ width: "140px" }}>Owner</th>
                <th style={{ width: "100px" }}>Status</th>
                <th style={{ width: "110px" }}>Tasks</th>
                <th style={{ width: "80px", textAlign: "right" }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} style={{ padding: "40px", textAlign: "center" }}>
                    <div className="skeleton" style={{ height: "24px", width: "60%", margin: "0 auto 8px" }} />
                    <div className="skeleton" style={{ height: "24px", width: "40%", margin: "0 auto" }} />
                  </td>
                </tr>
              ) : displayedStories.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: "48px 24px", textAlign: "center" }}>
                    <div style={{ fontSize: "36px", marginBottom: "8px" }}>📋</div>
                    <div style={{ fontSize: "15px", fontWeight: "700", color: "#ffffff", marginBottom: "4px" }}>
                      No Stories Found
                    </div>
                    <p style={{ color: "var(--text-muted)", fontSize: "13px", marginBottom: "16px" }}>
                      No stories match the active view. Try switching to "All Sprint Stories" or enter another ID.
                    </p>
                    <button
                      onClick={() => handleToggleFilter(false)}
                      className="btn btn-secondary"
                      style={{ fontSize: "12px" }}
                    >
                      Show All Sprint Stories
                    </button>
                  </td>
                </tr>
              ) : (
                displayedStories.map((story) => {
                  const isSelected = selectedStoryIds.has(story.story_id);
                  const taskCount = story.existing_tasks_count || 0;

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
                      <td style={{ fontFamily: "var(--font-mono)", fontSize: "12px" }}>
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
                        <div style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                          {story.item_type_name || "User Story"}
                          {story.point != null && ` · ${story.point} pts`}
                        </div>
                      </td>
                      <td style={{ fontSize: "12px", color: story.dev_owner_name ? "#ffffff" : "var(--text-muted)" }}>
                        {story.dev_owner_name || "Unassigned"}
                      </td>
                      <td>
                        <span className="badge badge-neutral" style={{ fontSize: "11px" }}>
                          {story.status || "Ready"}
                        </span>
                      </td>
                      <td>
                        {taskCount > 0 ? (
                          <span className="badge badge-warning" style={{ fontSize: "11px" }}>
                            ⚠ {taskCount} tasks
                          </span>
                        ) : (
                          <span className="badge badge-success" style={{ fontSize: "11px" }}>
                            0 tasks
                          </span>
                        )}
                      </td>
                      <td style={{ textAlign: "right" }}>
                        <Link
                          href={`/stories/${story.story_id}`}
                          onClick={(e) => e.stopPropagation()}
                          className="btn btn-secondary"
                          style={{ fontSize: "11px", padding: "2px 8px" }}
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

      {/* Floating Action Bar */}
      {selectedStoryIds.size > 0 && (
        <div className="selection-action-bar">
          <div>
            <span style={{ fontWeight: 700, color: "#ffffff" }}>
              {selectedStoryIds.size} Stories selected
            </span>
            <span style={{ color: "var(--text-muted)", margin: "0 8px" }}>·</span>
            <span style={{ color: "var(--accent-primary)", fontSize: "13px" }}>
              Est. ~{estimatedTasks} tasks
            </span>
          </div>

          <button
            onClick={handleClearSelection}
            className="btn btn-secondary"
            style={{
              fontSize: "12px",
              padding: "4px 10px",
              background: "transparent",
              border: "none",
              color: "var(--text-muted)",
            }}
          >
            Clear selection
          </button>

          <button
            onClick={() => setShowConfirmModal(true)}
            className="btn btn-primary"
            style={{ padding: "8px 20px", fontSize: "13px", fontWeight: 700 }}
          >
            Create {estimatedTasks} Tasks →
          </button>
        </div>
      )}

      {/* Confirmation Modal */}
      {showConfirmModal && (
        <div className="modal-backdrop" onClick={() => !executing && setShowConfirmModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 style={{ fontSize: "16px", fontWeight: "700", color: "#ffffff" }}>
                Confirm Task Creation
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
              <p style={{ fontSize: "14px", color: "var(--text-secondary)", marginBottom: "16px" }}>
                You are about to create tasks for{" "}
                <strong style={{ color: "#ffffff" }}>{selectedStories.length} Stories</strong>.
              </p>

              <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", color: "#ffffff", cursor: "pointer", marginBottom: "16px" }}>
                <input
                  type="checkbox"
                  className="custom-checkbox"
                  checked={skipExistingTasks}
                  onChange={(e) => setSkipExistingTasks(e.target.checked)}
                />
                <span>Skip Stories that already have subtasks (Prevent duplicates)</span>
              </label>

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
                {selectedStories.map((story) => (
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
                    <span style={{ color: "#ffffff", fontWeight: 500 }}>✓ {story.name}</span>
                    <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>{story.story_id}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="modal-footer">
              <button onClick={() => setShowConfirmModal(false)} className="btn btn-secondary">
                Cancel
              </button>
              <button onClick={handleStartCreation} className="btn btn-primary" style={{ fontWeight: 700 }}>
                Create {estimatedTasks} Tasks
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Progress Modal */}
      {executing && (
        <div className="modal-backdrop">
          <div className="modal-card" style={{ maxWidth: "500px" }}>
            <div className="modal-header">
              <h3 style={{ fontSize: "16px", fontWeight: "700", color: "#ffffff" }}>
                Creating Tasks...
              </h3>
            </div>
            <div className="modal-body">
              <div style={{ marginBottom: "12px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "13px", color: "var(--text-secondary)", marginBottom: "6px" }}>
                  <span>{executionProgress?.currentTitle || "Processing..."}</span>
                  <span style={{ fontWeight: 700, color: "#ffffff" }}>
                    {executionProgress ? `${executionProgress.completed}/${executionProgress.total}` : "..."}
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
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
