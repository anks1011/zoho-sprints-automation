"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  fetchSprintStories,
  bulkGeneratePlans,
  bulkExecutePlans,
  ApiError,
} from "@/lib/api-client";
import {
  SprintStoryItem,
  SprintStoriesResponse,
  BulkExecuteItem,
} from "@/lib/types";

export function SprintStoryNavbarPicker() {
  const router = useRouter();
  const [storyIdInput, setStoryIdInput] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sprint stories state
  const [sprintData, setSprintData] = useState<SprintStoriesResponse | null>(null);
  const [filterDevOnly, setFilterDevOnly] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedStoryIds, setSelectedStoryIds] = useState<Set<string>>(new Set());

  // Task creation execution state
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [confirmCheckbox, setConfirmCheckbox] = useState(false);
  const [dryRunMode, setDryRunMode] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [executionProgress, setExecutionProgress] = useState<string | null>(null);
  const [executionResults, setExecutionResults] = useState<BulkExecuteItem[] | null>(null);
  const [executionError, setExecutionError] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement | null>(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        if (!executing) {
          setIsOpen(false);
        }
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [executing]);

  const loadSprintStories = async (storyId: string, devOnly: boolean) => {
    const clean = storyId.trim();
    if (!clean) return;

    setLoading(true);
    setError(null);
    setExecutionResults(null);
    setExecutionError(null);
    setIsOpen(true);

    try {
      const resp = await fetchSprintStories(clean, devOnly);
      setSprintData(resp);
      // Pre-select all returned matched stories by default
      const allIds = new Set(resp.stories.map((s) => s.story_id));
      setSelectedStoryIds(allIds);
    } catch (err: unknown) {
      const msg =
        err instanceof ApiError
          ? err.detail
          : (err as Error)?.message || "Failed to fetch sprint stories.";
      setError(msg);
      setSprintData(null);
    } finally {
      setLoading(false);
    }
  };

  const handleFetchClick = (e: React.FormEvent) => {
    e.preventDefault();
    if (storyIdInput.trim()) {
      loadSprintStories(storyIdInput, filterDevOnly);
    }
  };

  const handleToggleFilter = (devOnly: boolean) => {
    setFilterDevOnly(devOnly);
    if (storyIdInput.trim()) {
      loadSprintStories(storyIdInput, devOnly);
    }
  };

  const handleToggleSelectStory = (id: string) => {
    const updated = new Set(selectedStoryIds);
    if (updated.has(id)) {
      updated.delete(id);
    } else {
      updated.add(id);
    }
    setSelectedStoryIds(updated);
  };

  const handleSelectAll = (storiesList: SprintStoryItem[]) => {
    const updated = new Set(selectedStoryIds);
    storiesList.forEach((s) => updated.add(s.story_id));
    setSelectedStoryIds(updated);
  };

  const handleUnselectAll = (storiesList: SprintStoryItem[]) => {
    const updated = new Set(selectedStoryIds);
    storiesList.forEach((s) => updated.delete(s.story_id));
    setSelectedStoryIds(updated);
  };

  // Trigger task creation for selected stories only
  const handleTriggerCreation = async () => {
    const targetIds = Array.from(selectedStoryIds);
    if (targetIds.length === 0) return;

    setShowConfirmModal(false);
    setExecuting(true);
    setExecutionError(null);
    setExecutionResults(null);

    try {
      // Step 1: Generate plans for selected stories progressively
      const planIds: string[] = [];
      const genErrors: string[] = [];

      for (let i = 0; i < targetIds.length; i++) {
        const id = targetIds[i];
        setExecutionProgress(
          `Step 1/2: Generating AI task plan for story ${i + 1}/${targetIds.length} (${id})...`
        );
        try {
          const resp = await bulkGeneratePlans([id]);
          if (resp.results && resp.results.length > 0 && resp.results[0].success && resp.results[0].plan?.plan_id) {
            planIds.push(resp.results[0].plan.plan_id);
          } else if (resp.results && resp.results[0]?.error) {
            genErrors.push(`${id}: ${resp.results[0].error}`);
          }
        } catch (e: unknown) {
          const msg = e instanceof ApiError ? e.detail : (e as Error)?.message || "Generation error";
          genErrors.push(`${id}: ${msg}`);
        }
      }

      if (planIds.length === 0) {
        throw new Error(
          `Could not generate plans for any selected stories.${genErrors.length > 0 ? " Errors: " + genErrors.join("; ") : ""}`
        );
      }

      // Step 2: Execute task creation for the generated plans progressively
      const allExecResults: BulkExecuteItem[] = [];
      for (let i = 0; i < planIds.length; i++) {
        const pid = planIds[i];
        setExecutionProgress(
          `Step 2/2: ${dryRunMode ? "Simulating dry-run" : "Creating tasks in Zoho"} (${i + 1}/${planIds.length})...`
        );
        try {
          const execResp = await bulkExecutePlans([pid], dryRunMode, true);
          if (execResp.results && execResp.results.length > 0) {
            allExecResults.push(...execResp.results);
          }
        } catch (e: unknown) {
          const msg = e instanceof ApiError ? e.detail : (e as Error)?.message || "Execution error";
          allExecResults.push({
            plan_id: pid,
            success: false,
            error: msg,
          });
        }
      }

      setExecutionResults(allExecResults);
      setExecutionProgress(null);
    } catch (err: unknown) {
      const msg =
        err instanceof ApiError
          ? err.detail
          : (err as Error)?.message || "Failed to trigger task creation.";
      setExecutionError(msg);
      setExecutionProgress(null);
    } finally {
      setExecuting(false);
    }
  };

  const visibleStories = (sprintData?.stories || []).filter((s) => {
    if (!searchTerm.trim()) return true;
    const q = searchTerm.toLowerCase();
    return s.story_id.toLowerCase().includes(q) || s.name.toLowerCase().includes(q);
  });

  const selectedCountInVisible = visibleStories.filter((s) =>
    selectedStoryIds.has(s.story_id)
  ).length;

  return (
    <div ref={containerRef} style={{ position: "relative" }}>
      {/* Navbar Input Bar */}
      <form
        onSubmit={handleFetchClick}
        style={{ display: "flex", alignItems: "center", gap: "8px", width: "480px" }}
      >
        <div style={{ position: "relative", width: "100%" }}>
          <input
            type="text"
            className="input"
            placeholder="Enter Story ID to pick sprint stories..."
            value={storyIdInput}
            onChange={(e) => setStoryIdInput(e.target.value)}
            onFocus={() => {
              if (sprintData) setIsOpen(true);
            }}
            style={{
              paddingLeft: "36px",
              paddingRight: "80px",
              height: "38px",
              fontSize: "13px",
              borderRadius: "var(--radius-md)",
            }}
          />
          <svg
            style={{
              position: "absolute",
              left: "12px",
              top: "11px",
              color: "var(--text-muted)",
              pointerEvents: "none",
            }}
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.3-4.3" />
          </svg>

          {storyIdInput.trim() && (
            <button
              type="button"
              onClick={() => {
                router.push(`/stories/${storyIdInput.trim()}`);
              }}
              title="Inspect Single Story"
              style={{
                position: "absolute",
                right: "6px",
                top: "6px",
                background: "rgba(255, 255, 255, 0.08)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "4px",
                color: "var(--text-secondary)",
                fontSize: "11px",
                padding: "3px 8px",
                cursor: "pointer",
              }}
            >
              Inspect ↗
            </button>
          )}
        </div>

        <button
          type="submit"
          className="btn btn-primary"
          disabled={loading || !storyIdInput.trim()}
          style={{
            padding: "8px 14px",
            height: "38px",
            fontSize: "13px",
            whiteSpace: "nowrap",
            display: "flex",
            alignItems: "center",
            gap: "6px",
          }}
        >
          {loading ? (
            <>
              <span className="spinner" style={{ width: "14px", height: "14px", borderWidth: "2px" }} />
              <span>Fetching...</span>
            </>
          ) : (
            <>
              <span>⚡ Sprint Stories</span>
            </>
          )}
        </button>
      </form>

      {/* Floating Multi-Select Panel */}
      {isOpen && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 8px)",
            left: 0,
            width: "620px",
            maxHeight: "560px",
            background: "#111827",
            border: "1px solid rgba(99, 102, 241, 0.4)",
            borderRadius: "var(--radius-lg)",
            boxShadow: "0 20px 45px rgba(0, 0, 0, 0.7), 0 0 25px rgba(99, 102, 241, 0.2)",
            zIndex: 100,
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          {/* Header Bar */}
          <div
            style={{
              padding: "14px 18px",
              borderBottom: "1px solid var(--border-subtle)",
              background: "rgba(22, 32, 50, 0.8)",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                <span className="badge badge-primary" style={{ fontSize: "11px" }}>
                  {sprintData?.sprint_name || "Sprint Stories"}
                </span>
                {sprintData?.current_user_dev_name && (
                  <span className="badge badge-info" style={{ fontSize: "11px" }}>
                    👤 Dev: {sprintData.current_user_dev_name}
                  </span>
                )}
              </div>
              <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                Sprint ID: <code style={{ color: "#ffffff" }}>{sprintData?.sprint_id || "-"}</code>
              </div>
            </div>

            <button
              type="button"
              onClick={() => setIsOpen(false)}
              style={{
                background: "transparent",
                border: "none",
                color: "var(--text-muted)",
                fontSize: "18px",
                cursor: "pointer",
                padding: "2px 6px",
              }}
              title="Close panel"
            >
              ✕
            </button>
          </div>

          {/* Filter Pills & Selection Controls */}
          {sprintData && (
            <div
              style={{
                padding: "10px 18px",
                borderBottom: "1px solid var(--border-subtle)",
                background: "rgba(10, 14, 23, 0.5)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: "8px",
              }}
            >
              {/* Tab toggles */}
              <div style={{ display: "flex", gap: "6px" }}>
                <button
                  type="button"
                  onClick={() => handleToggleFilter(true)}
                  style={{
                    background: filterDevOnly ? "var(--accent-primary)" : "rgba(255,255,255,0.06)",
                    color: filterDevOnly ? "#ffffff" : "var(--text-secondary)",
                    border: "none",
                    borderRadius: "4px",
                    padding: "4px 10px",
                    fontSize: "12px",
                    cursor: "pointer",
                    fontWeight: "600",
                  }}
                >
                  My Dev Stories ({sprintData.matched_stories_count})
                </button>
                <button
                  type="button"
                  onClick={() => handleToggleFilter(false)}
                  style={{
                    background: !filterDevOnly ? "var(--accent-primary)" : "rgba(255,255,255,0.06)",
                    color: !filterDevOnly ? "#ffffff" : "var(--text-secondary)",
                    border: "none",
                    borderRadius: "4px",
                    padding: "4px 10px",
                    fontSize: "12px",
                    cursor: "pointer",
                    fontWeight: "600",
                  }}
                >
                  All Sprint Stories ({sprintData.total_sprint_stories})
                </button>
              </div>

              {/* Selection buttons */}
              <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px" }}>
                <button
                  type="button"
                  onClick={() => handleSelectAll(visibleStories)}
                  style={{
                    background: "transparent",
                    border: "none",
                    color: "var(--accent-primary)",
                    cursor: "pointer",
                    textDecoration: "underline",
                  }}
                >
                  Select All
                </button>
                <span style={{ color: "var(--border-card)" }}>|</span>
                <button
                  type="button"
                  onClick={() => handleUnselectAll(visibleStories)}
                  style={{
                    background: "transparent",
                    border: "none",
                    color: "var(--text-muted)",
                    cursor: "pointer",
                    textDecoration: "underline",
                  }}
                >
                  Unselect All
                </button>
                <span
                  className="badge badge-neutral"
                  style={{ fontFamily: "var(--font-mono)", fontSize: "11px", marginLeft: "4px" }}
                >
                  {selectedStoryIds.size} Selected
                </span>
              </div>
            </div>
          )}

          {/* Quick Search inside list */}
          {sprintData && sprintData.stories.length > 3 && (
            <div style={{ padding: "8px 18px", borderBottom: "1px solid var(--border-subtle)" }}>
              <input
                type="text"
                className="input"
                placeholder="Filter stories by title or ID..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                style={{ height: "30px", fontSize: "12px", padding: "4px 10px" }}
              />
            </div>
          )}

          {/* Error Banner */}
          {error && (
            <div
              style={{
                padding: "16px",
                background: "rgba(239, 68, 68, 0.1)",
                color: "var(--color-error)",
                fontSize: "13px",
              }}
            >
              <strong>Error:</strong> {error}
            </div>
          )}

          {/* Loading Indicator */}
          {loading && (
            <div style={{ padding: "36px", textAlign: "center", color: "var(--text-secondary)" }}>
              <div className="spinner" style={{ margin: "0 auto 12px", width: "24px", height: "24px" }} />
              <div style={{ fontSize: "13px" }}>
                Resolving sprint context and filtering stories for Developer Owner...
              </div>
            </div>
          )}

          {/* Execution Progress */}
          {executing && (
            <div
              style={{
                padding: "24px",
                textAlign: "center",
                background: "rgba(99, 102, 241, 0.08)",
                borderBottom: "1px solid var(--border-subtle)",
              }}
            >
              <div className="spinner" style={{ margin: "0 auto 10px", width: "22px", height: "22px" }} />
              <div style={{ fontSize: "13px", fontWeight: "600", color: "#ffffff" }}>
                {executionProgress || "Processing task creation..."}
              </div>
            </div>
          )}

          {/* Execution Results Summary Banner */}
          {executionResults && (
            <div
              style={{
                padding: "12px 18px",
                background: "rgba(16, 185, 129, 0.1)",
                borderBottom: "1px solid rgba(16, 185, 129, 0.3)",
                fontSize: "12px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div style={{ color: "var(--color-success)", fontWeight: "600" }}>
                ✓ Execution complete for {executionResults.length} stories!
              </div>
              <Link
                href="/executions"
                className="btn btn-secondary"
                style={{ fontSize: "11px", padding: "4px 8px" }}
              >
                View History →
              </Link>
            </div>
          )}

          {/* Execution Error */}
          {executionError && (
            <div
              style={{
                padding: "12px 18px",
                background: "rgba(239, 68, 68, 0.1)",
                color: "var(--color-error)",
                fontSize: "12px",
              }}
            >
              <strong>Creation Error:</strong> {executionError}
            </div>
          )}

          {/* Selectable Stories List */}
          {!loading && sprintData && (
            <div
              style={{
                overflowY: "auto",
                maxHeight: "260px",
                padding: "6px 0",
              }}
            >
              {visibleStories.length === 0 ? (
                <div style={{ padding: "30px", textAlign: "center", color: "var(--text-muted)", fontSize: "13px" }}>
                  {filterDevOnly
                    ? "No stories found in this sprint matching the Developer Owner."
                    : "No stories found in this sprint."}
                </div>
              ) : (
                visibleStories.map((story) => {
                  const isSelected = selectedStoryIds.has(story.story_id);
                  return (
                    <div
                      key={story.story_id}
                      onClick={() => handleToggleSelectStory(story.story_id)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "12px",
                        padding: "10px 18px",
                        cursor: "pointer",
                        background: isSelected ? "rgba(99, 102, 241, 0.12)" : "transparent",
                        borderBottom: "1px solid var(--border-subtle)",
                        transition: "background 0.15s ease",
                      }}
                      onMouseEnter={(e) => {
                        if (!isSelected) e.currentTarget.style.background = "rgba(255, 255, 255, 0.03)";
                      }}
                      onMouseLeave={(e) => {
                        if (!isSelected) e.currentTarget.style.background = "transparent";
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => {}}
                        style={{
                          width: "16px",
                          height: "16px",
                          cursor: "pointer",
                          accentColor: "var(--accent-primary)",
                        }}
                      />

                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "3px" }}>
                          <span
                            style={{
                              fontFamily: "var(--font-mono)",
                              fontSize: "11px",
                              color: "var(--accent-primary)",
                              fontWeight: "600",
                            }}
                          >
                            {story.story_id}
                          </span>
                          {story.is_current_story && (
                            <span className="badge badge-info" style={{ fontSize: "10px", padding: "1px 6px" }}>
                              Input Story
                            </span>
                          )}
                          {story.status && (
                            <span className="badge badge-neutral" style={{ fontSize: "10px", padding: "1px 6px" }}>
                              {story.status}
                            </span>
                          )}
                          {story.dev_owner_name && (
                            <span style={{ fontSize: "11px", color: "var(--text-muted)", marginLeft: "auto" }}>
                              Dev: {story.dev_owner_name}
                            </span>
                          )}
                        </div>
                        <div
                          style={{
                            fontSize: "13px",
                            color: isSelected ? "#ffffff" : "var(--text-primary)",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                            fontWeight: isSelected ? "600" : "400",
                          }}
                        >
                          {story.name}
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          )}

          {/* Action Footer */}
          {sprintData && (
            <div
              style={{
                padding: "12px 18px",
                borderTop: "1px solid var(--border-subtle)",
                background: "rgba(22, 32, 50, 0.9)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                <strong style={{ color: "#ffffff" }}>{selectedStoryIds.size}</strong> of{" "}
                {visibleStories.length} stories selected
              </div>

              <div style={{ display: "flex", gap: "10px" }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setIsOpen(false)}
                  style={{ fontSize: "12px", padding: "6px 12px" }}
                >
                  Close
                </button>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={selectedStoryIds.size === 0 || executing}
                  onClick={() => {
                    setConfirmCheckbox(false);
                    setShowConfirmModal(true);
                  }}
                  style={{ fontSize: "12px", padding: "6px 16px" }}
                >
                  Confirm & Create Tasks ({selectedStoryIds.size}) →
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Confirmation Modal */}
      {showConfirmModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0, 0, 0, 0.8)",
            backdropFilter: "blur(6px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
            padding: "20px",
          }}
        >
          <div
            className="card"
            style={{
              maxWidth: "480px",
              width: "100%",
              border: "1px solid rgba(99, 102, 241, 0.5)",
              boxShadow: "var(--shadow-glow)",
              padding: "24px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "14px" }}>
              <span style={{ fontSize: "22px" }}>🚀</span>
              <h3 style={{ fontSize: "17px", fontWeight: "800", color: "#ffffff" }}>
                Confirm Task Creation for Selected Stories
              </h3>
            </div>

            <p style={{ fontSize: "13px", color: "var(--text-secondary)", lineHeight: "1.6", marginBottom: "16px" }}>
              Task creation will be triggered <strong>only for the {selectedStoryIds.size} selected Stories</strong> in{" "}
              <strong>{sprintData?.sprint_name}</strong>.
            </p>

            <div
              style={{
                background: "rgba(22, 32, 50, 0.6)",
                border: "1px solid var(--border-card)",
                borderRadius: "var(--radius-sm)",
                padding: "12px",
                marginBottom: "16px",
              }}
            >
              <div style={{ fontSize: "12px", fontWeight: "600", marginBottom: "6px" }}>Execution Mode:</div>
              <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", cursor: "pointer", marginBottom: "6px" }}>
                <input
                  type="radio"
                  name="execMode"
                  checked={!dryRunMode}
                  onChange={() => setDryRunMode(false)}
                />
                <span>Live Creation in Zoho Sprints</span>
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", cursor: "pointer" }}>
                <input
                  type="radio"
                  name="execMode"
                  checked={dryRunMode}
                  onChange={() => setDryRunMode(true)}
                />
                <span>Dry-Run Simulation (Zero Writes)</span>
              </label>
            </div>

            <label
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: "8px",
                cursor: "pointer",
                marginBottom: "20px",
                fontSize: "12px",
                color: "var(--text-secondary)",
              }}
            >
              <input
                type="checkbox"
                checked={confirmCheckbox}
                onChange={(e) => setConfirmCheckbox(e.target.checked)}
                style={{ marginTop: "2px" }}
              />
              <span>I confirm subtask creation for the {selectedStoryIds.size} selected Stories.</span>
            </label>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px" }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setShowConfirmModal(false)}
                style={{ fontSize: "12px" }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={!confirmCheckbox}
                onClick={handleTriggerCreation}
                style={{ fontSize: "12px", padding: "6px 16px" }}
              >
                {dryRunMode ? "Simulate Dry-Run" : `Create Tasks (${selectedStoryIds.size} Stories)`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
