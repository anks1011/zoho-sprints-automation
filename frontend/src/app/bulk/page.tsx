"use client";

import { useState, useRef, Fragment } from "react";
import Link from "next/link";
import {
  bulkGeneratePlans,
  bulkExecutePlans,
  ApiError,
} from "@/lib/api-client";
import {
  BulkPlanItem,
  BulkExecuteItem,
} from "@/lib/types";

export default function BulkActionPage() {
  const [inputMode, setInputMode] = useState<"text" | "csv">("text");
  const [rawText, setRawText] = useState("");
  const [csvFileName, setCsvFileName] = useState<string | null>(null);
  const [parsedIds, setParsedIds] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // Generation state
  const [generating, setGenerating] = useState(false);
  const [generateProgress, setGenerateProgress] = useState<{ current: number; total: number } | null>(null);
  const [generationResults, setGenerationResults] = useState<BulkPlanItem[] | null>(null);
  const [generationError, setGenerationError] = useState<string | null>(null);

  // Table filtering & expansion
  const [filterTerm, setFilterTerm] = useState("");
  const [statusFilter, setStatusFilter] = useState<"ALL" | "SUCCESS" | "FAILED">("ALL");
  const [expandedStoryId, setExpandedStoryId] = useState<string | null>(null);

  // Execution state
  const [executing, setExecuting] = useState(false);
  const [dryRunRunning, setDryRunRunning] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [confirmCheckbox, setConfirmCheckbox] = useState(false);
  const [executionResults, setExecutionResults] = useState<BulkExecuteItem[] | null>(null);
  const [executionError, setExecutionError] = useState<string | null>(null);
  const [dryRunSummary, setDryRunSummary] = useState<{ totalPlans: number; totalOps: number } | null>(null);

  // Helper to extract clean unique IDs from text
  const extractIds = (text: string): string[] => {
    const rawTokens = text.split(/[\s,;\n\t\r]+/);
    const valid = rawTokens.map((t) => t.trim()).filter((t) => t.length > 0 && /^[a-zA-Z0-9_-]+$/.test(t));
    const seen = new Set<string>();
    const deduped: string[] = [];
    for (const id of valid) {
      if (!seen.has(id)) {
        seen.add(id);
        deduped.push(id);
      }
    }
    return deduped;
  };

  const handleTextChange = (val: string) => {
    setRawText(val);
    const ids = extractIds(val);
    setParsedIds(ids);
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setCsvFileName(file.name);
    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      if (!content) return;

      const lines = content.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
      if (lines.length === 0) return;

      const header = lines[0].split(",").map((c) => c.trim().toLowerCase().replace(/^["']|["']$/g, ""));
      let targetColIndex = -1;
      const targetHeaders = ["story_id", "storyid", "story id", "item_id", "itemid", "id", "ticket_id", "ticket id"];
      for (let i = 0; i < header.length; i++) {
        if (targetHeaders.includes(header[i])) {
          targetColIndex = i;
          break;
        }
      }

      const extracted: string[] = [];
      if (targetColIndex !== -1 && lines.length > 1) {
        for (let i = 1; i < lines.length; i++) {
          const cells = lines[i].split(",").map((c) => c.trim().replace(/^["']|["']$/g, ""));
          if (cells[targetColIndex]) {
            extracted.push(cells[targetColIndex]);
          }
        }
      } else {
        for (const line of lines) {
          const cells = line.split(/[,;\t]/).map((c) => c.trim().replace(/^["']|["']$/g, ""));
          for (const c of cells) {
            if (c && !targetHeaders.includes(c.toLowerCase())) {
              extracted.push(c);
            }
          }
        }
      }

      const cleanIds = extractIds(extracted.join(" "));
      setParsedIds(cleanIds);
    };
    reader.readAsText(file);
  };

  const handleRemoveId = (idToRemove: string) => {
    const updated = parsedIds.filter((id) => id !== idToRemove);
    setParsedIds(updated);
    if (inputMode === "text") {
      setRawText(updated.join(", "));
    }
  };

  const handleClearAll = () => {
    setParsedIds([]);
    setRawText("");
    setCsvFileName(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    setGenerationResults(null);
    setExecutionResults(null);
    setDryRunSummary(null);
    setGenerationError(null);
    setExecutionError(null);
  };

  const handleLoadDemo = () => {
    const demoIds = ["39713000007827664"];
    setParsedIds(demoIds);
    setRawText(demoIds.join("\n"));
    setInputMode("text");
  };

  // Generate All Plans with Progressive Real-Time Streaming Updates
  const handleBulkGenerate = async () => {
    if (parsedIds.length === 0) return;

    setGenerating(true);
    setGenerationError(null);
    setGenerationResults([]);
    setExecutionResults(null);
    setDryRunSummary(null);
    setGenerateProgress({ current: 0, total: parsedIds.length });

    const total = parsedIds.length;
    let completed = 0;
    const accumulatedResults: BulkPlanItem[] = [];
    const queue = [...parsedIds];
    const concurrency = Math.min(2, queue.length);

    const worker = async () => {
      while (queue.length > 0) {
        const sid = queue.shift();
        if (!sid) break;

        try {
          const resp = await bulkGeneratePlans([sid]);
          if (resp.results && resp.results.length > 0) {
            accumulatedResults.push(resp.results[0]);
          } else {
            accumulatedResults.push({
              story_id: sid,
              success: false,
              error: "Received empty response from server.",
            });
          }
        } catch (err: unknown) {
          const msg =
            err instanceof ApiError
              ? err.detail
              : (err as Error)?.message || `Failed to generate plan for ${sid}`;
          accumulatedResults.push({
            story_id: sid,
            success: false,
            error: msg,
          });
        } finally {
          completed++;
          setGenerateProgress({ current: completed, total });
          // Update the review table dynamically so stories appear immediately
          setGenerationResults([...accumulatedResults]);
        }
      }
    };

    try {
      await Promise.all(Array.from({ length: concurrency }, () => worker()));
    } catch (err: unknown) {
      const msg =
        err instanceof ApiError
          ? err.detail
          : (err as Error)?.message || "Failed to generate bulk plans.";
      setGenerationError(msg);
    } finally {
      setGenerating(false);
    }
  };

  // Dry-run simulation with progressive execution
  const handleDryRunAll = async () => {
    if (!generationResults) return;
    const planIds = generationResults
      .filter((r) => r.success && r.plan?.plan_id)
      .map((r) => r.plan!.plan_id);

    if (planIds.length === 0) return;

    setDryRunRunning(true);
    setExecutionError(null);
    try {
      let totalOps = 0;
      let totalPlans = 0;
      const batchSize = 2;
      for (let i = 0; i < planIds.length; i += batchSize) {
        const batch = planIds.slice(i, i + batchSize);
        const res = await bulkExecutePlans(batch, true, false);
        for (const item of res.results) {
          if (item.result) {
            totalOps += item.result.total_tasks;
          }
          if (item.success) {
            totalPlans++;
          }
        }
      }
      setDryRunSummary({ totalPlans, totalOps });
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.detail : (err as Error)?.message || "Failed to run dry-run simulation.";
      setExecutionError(msg);
    } finally {
      setDryRunRunning(false);
    }
  };

  // Live bulk execution with progressive execution
  const handleConfirmLiveExecution = async () => {
    if (!confirmCheckbox || !generationResults) return;

    const planIds = generationResults
      .filter((r) => r.success && r.plan?.plan_id)
      .map((r) => r.plan!.plan_id);

    if (planIds.length === 0) return;

    setShowConfirmModal(false);
    setExecuting(true);
    setExecutionError(null);
    setExecutionResults([]);

    try {
      const allResults: BulkExecuteItem[] = [];
      const batchSize = 2;
      for (let i = 0; i < planIds.length; i += batchSize) {
        const batch = planIds.slice(i, i + batchSize);
        try {
          const res = await bulkExecutePlans(batch, false, true);
          allResults.push(...res.results);
        } catch (e: unknown) {
          const msg = e instanceof ApiError ? e.detail : (e as Error)?.message || "Batch execution failed";
          for (const pid of batch) {
            allResults.push({
              plan_id: pid,
              success: false,
              error: msg,
            });
          }
        }
        setExecutionResults([...allResults]);
      }
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.detail : (err as Error)?.message || "Failed to execute bulk task creation.";
      setExecutionError(msg);
    } finally {
      setExecuting(false);
    }
  };

  // Computed statistics
  const successfulPlans = generationResults?.filter((r) => r.success && r.plan) || [];
  const failedCount = generationResults?.filter((r) => !r.success).length || 0;
  const totalPlannedTasks = successfulPlans.reduce((sum, r) => sum + (r.plan?.tasks.length || 0), 0);
  const totalFeTasks = successfulPlans.reduce((sum, r) => sum + (r.plan?.tasks.filter((t) => t.task_type === "FE").length || 0), 0);
  const totalBeTasks = successfulPlans.reduce((sum, r) => sum + (r.plan?.tasks.filter((t) => t.task_type === "BE").length || 0), 0);
  const totalDuplicates = successfulPlans.reduce((sum, r) => sum + (r.plan?.duplicate_warnings.length || 0), 0);

  // Filtered rows for table
  const filteredResults = (generationResults || []).filter((item) => {
    if (statusFilter === "SUCCESS" && !item.success) return false;
    if (statusFilter === "FAILED" && item.success) return false;

    if (filterTerm.trim()) {
      const q = filterTerm.toLowerCase();
      const matchId = item.story_id.toLowerCase().includes(q);
      const matchTitle = item.plan?.story_title.toLowerCase().includes(q);
      return matchId || matchTitle;
    }
    return true;
  });

  return (
    <div className="page-container" style={{ maxWidth: "1280px", margin: "0 auto", paddingBottom: "80px" }}>
      {/* Hero Header */}
      <div
        style={{
          background: "linear-gradient(135deg, rgba(99, 102, 241, 0.15) 0%, rgba(168, 85, 247, 0.08) 100%)",
          border: "1px solid var(--border-card)",
          borderRadius: "var(--radius-lg)",
          padding: "36px 40px",
          marginBottom: "28px",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div style={{ maxWidth: "800px" }}>
          <div style={{ display: "flex", gap: "10px", alignItems: "center", marginBottom: "14px" }}>
            <span className="badge badge-primary">Bulk Action Studio</span>
            <span className="badge badge-info">Multi-Story Batch Processing (Up to 50+ Stories)</span>
          </div>
          <h1 style={{ fontSize: "30px", fontWeight: "800", letterSpacing: "-0.03em", marginBottom: "10px" }}>
            Bulk Story-to-Tasks Automation
          </h1>
          <p style={{ color: "var(--text-secondary)", fontSize: "15px", lineHeight: "1.6" }}>
            Paste a list of Zoho Sprints Story IDs or upload a CSV file to synthesize FE and BE task plans in parallel,
            inspect duplicate overlap warnings, run dry-run verification, and safely create tasks across all stories with a single click.
          </p>
        </div>
      </div>

      {/* Input Section Card */}
      <div className="card" style={{ marginBottom: "28px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              type="button"
              className={`btn ${inputMode === "text" ? "btn-primary" : "btn-secondary"}`}
              onClick={() => setInputMode("text")}
              style={{ fontSize: "14px", padding: "8px 16px" }}
            >
              ✍️ Paste Story IDs
            </button>
            <button
              type="button"
              className={`btn ${inputMode === "csv" ? "btn-primary" : "btn-secondary"}`}
              onClick={() => setInputMode("csv")}
              style={{ fontSize: "14px", padding: "8px 16px" }}
            >
              📁 Upload CSV File
            </button>
          </div>

          <div style={{ display: "flex", gap: "10px" }}>
            <button
              type="button"
              onClick={handleLoadDemo}
              className="btn btn-secondary"
              style={{ fontSize: "12px", padding: "6px 12px" }}
            >
              Load Active Story Demo
            </button>
            {parsedIds.length > 0 && (
              <button
                type="button"
                onClick={handleClearAll}
                className="btn btn-secondary"
                style={{ fontSize: "12px", padding: "6px 12px", color: "var(--color-error)" }}
              >
                Clear All
              </button>
            )}
          </div>
        </div>

        {/* Input Mode A: Textarea */}
        {inputMode === "text" && (
          <div>
            <textarea
              className="input"
              rows={5}
              placeholder="Paste Zoho Sprints Story IDs (comma, space, or newline separated)...&#10;e.g. 39713000007827664, 39713000007827665, 39713000007827666..."
              value={rawText}
              onChange={(e) => handleTextChange(e.target.value)}
              style={{
                width: "100%",
                fontFamily: "var(--font-mono)",
                fontSize: "14px",
                lineHeight: "1.6",
                padding: "14px",
                borderRadius: "var(--radius-md)",
                resize: "vertical",
              }}
            />
            <div style={{ fontSize: "12px", color: "var(--text-muted)", marginTop: "6px" }}>
              💡 Tip: You can paste a whole column directly from Excel or a comma-separated list of 50+ IDs.
            </div>
          </div>
        )}

        {/* Input Mode B: CSV File Dropzone */}
        {inputMode === "csv" && (
          <div>
            <div
              onClick={() => fileInputRef.current?.click()}
              style={{
                border: "2px dashed var(--border-card)",
                borderRadius: "var(--radius-md)",
                padding: "40px 20px",
                textAlign: "center",
                cursor: "pointer",
                background: "rgba(22, 32, 50, 0.4)",
                transition: "all 0.2s ease",
              }}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,text/csv,.txt"
                onChange={handleFileUpload}
                style={{ display: "none" }}
              />
              <div style={{ fontSize: "36px", marginBottom: "10px" }}>📄</div>
              <div style={{ fontSize: "16px", fontWeight: "600", marginBottom: "4px" }}>
                {csvFileName ? `Loaded: ${csvFileName}` : "Click to browse or drag & drop CSV file"}
              </div>
              <p style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
                Supports standard CSV with a <code style={{ color: "var(--accent-primary)" }}>story_id</code>,{" "}
                <code style={{ color: "var(--accent-primary)" }}>item_id</code>, or first column of IDs.
              </p>
            </div>
          </div>
        )}

        {/* Parsed Story IDs Tag Preview */}
        {parsedIds.length > 0 && (
          <div style={{ marginTop: "20px", borderTop: "1px solid var(--border-subtle)", paddingTop: "16px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ fontSize: "13px", fontWeight: "600", color: "var(--text-highlight)" }}>
                  Detected Story IDs:
                </span>
                <span className="badge badge-info" style={{ fontFamily: "var(--font-mono)", fontSize: "12px" }}>
                  {parsedIds.length} {parsedIds.length === 1 ? "Story" : "Stories"}
                </span>
              </div>
            </div>

            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                gap: "8px",
                maxHeight: "130px",
                overflowY: "auto",
                padding: "8px",
                background: "rgba(10, 14, 23, 0.5)",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-subtle)",
              }}
            >
              {parsedIds.map((id) => (
                <div
                  key={id}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "6px",
                    background: "rgba(99, 102, 241, 0.12)",
                    border: "1px solid rgba(99, 102, 241, 0.3)",
                    borderRadius: "6px",
                    padding: "4px 8px",
                    fontFamily: "var(--font-mono)",
                    fontSize: "12px",
                    color: "var(--text-primary)",
                  }}
                >
                  <span>{id}</span>
                  <button
                    type="button"
                    onClick={() => handleRemoveId(id)}
                    style={{
                      background: "transparent",
                      border: "none",
                      color: "var(--text-muted)",
                      cursor: "pointer",
                      fontSize: "14px",
                      lineHeight: "1",
                      padding: 0,
                    }}
                    title="Remove ID"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>

            {/* Launch Generation Button */}
            <div style={{ marginTop: "20px", display: "flex", justifyContent: "flex-end" }}>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleBulkGenerate}
                disabled={generating || parsedIds.length === 0}
                style={{ fontSize: "15px", padding: "10px 24px" }}
              >
                {generating ? (
                  <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span className="spinner" style={{ width: "16px", height: "16px", borderWidth: "2px" }} />
                    Generating Plans ({generateProgress ? `${generateProgress.current}/${generateProgress.total}` : "..."})...
                  </span>
                ) : (
                  `⚡ Generate AI Task Plans for ${parsedIds.length} ${parsedIds.length === 1 ? "Story" : "Stories"} →`
                )}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Generation Error Banner */}
      {generationError && (
        <div
          className="card"
          style={{
            marginBottom: "24px",
            border: "1px solid rgba(239, 68, 68, 0.4)",
            background: "rgba(239, 68, 68, 0.08)",
            color: "var(--color-error)",
          }}
        >
          <strong>Bulk Generation Error:</strong> {generationError}
        </div>
      )}

      {/* Generation Progress Bar */}
      {generating && (
        <div className="card" style={{ marginBottom: "28px", textAlign: "center", padding: "30px" }}>
          <div style={{ fontSize: "18px", fontWeight: "700", marginBottom: "8px" }}>
            Processing Story Batch with AI Analyzer...
          </div>
          <p style={{ color: "var(--text-secondary)", fontSize: "14px", marginBottom: "16px" }}>
            Fetching stories, decomposing into FE & BE subtasks, resolving sprint owners, and calculating duplicate overlaps.
          </p>
          <div
            style={{
              height: "8px",
              background: "rgba(255, 255, 255, 0.1)",
              borderRadius: "4px",
              overflow: "hidden",
              maxWidth: "500px",
              margin: "0 auto",
            }}
          >
            <div
              style={{
                height: "100%",
                background: "var(--accent-gradient)",
                width: "100%",
                animation: "pulse 1.5s infinite",
              }}
            />
          </div>
        </div>
      )}

      {/* Review & Preview Section */}
      {generationResults && (
        <div style={{ marginTop: "32px" }}>
          {/* Stats Bar */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: "16px",
              marginBottom: "24px",
            }}
          >
            <div className="card" style={{ padding: "18px" }}>
              <div style={{ fontSize: "12px", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: "600" }}>
                Stories Processed
              </div>
              <div style={{ fontSize: "28px", fontWeight: "800", marginTop: "4px", color: "var(--text-highlight)" }}>
                {successfulPlans.length} / {generationResults.length}
              </div>
              <div style={{ fontSize: "12px", color: failedCount > 0 ? "var(--color-error)" : "var(--color-success)", marginTop: "4px" }}>
                {failedCount > 0 ? `⚠️ ${failedCount} stories failed` : "✓ 100% successfully generated"}
              </div>
            </div>

            <div className="card" style={{ padding: "18px" }}>
              <div style={{ fontSize: "12px", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: "600" }}>
                Total Subtasks Planned
              </div>
              <div style={{ fontSize: "28px", fontWeight: "800", marginTop: "4px", color: "var(--accent-primary)" }}>
                {totalPlannedTasks}
              </div>
              <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "4px" }}>
                Across all generated stories
              </div>
            </div>

            <div className="card" style={{ padding: "18px" }}>
              <div style={{ fontSize: "12px", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: "600" }}>
                FE vs BE Tasks
              </div>
              <div style={{ fontSize: "28px", fontWeight: "800", marginTop: "4px", color: "#38bdf8" }}>
                {totalFeTasks} <span style={{ fontSize: "16px", color: "var(--text-muted)" }}>FE</span> · {totalBeTasks}{" "}
                <span style={{ fontSize: "16px", color: "var(--text-muted)" }}>BE</span>
              </div>
              <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "4px" }}>
                Strict architectural boundaries
              </div>
            </div>

            <div className="card" style={{ padding: "18px" }}>
              <div style={{ fontSize: "12px", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: "600" }}>
                Duplicate Warnings
              </div>
              <div
                style={{
                  fontSize: "28px",
                  fontWeight: "800",
                  marginTop: "4px",
                  color: totalDuplicates > 0 ? "var(--color-warning)" : "var(--color-success)",
                }}
              >
                {totalDuplicates}
              </div>
              <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "4px" }}>
                {totalDuplicates > 0 ? "Checked against existing subtasks" : "Zero duplicates detected"}
              </div>
            </div>
          </div>

          {/* Action Header & Bulk Execution Controls */}
          <div
            className="card"
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: "20px",
              padding: "16px 20px",
              background: "rgba(22, 32, 50, 0.7)",
              border: "1px solid rgba(99, 102, 241, 0.3)",
              flexWrap: "wrap",
              gap: "14px",
            }}
          >
            <div>
              <div style={{ fontSize: "16px", fontWeight: "700" }}>Bulk Action Controls</div>
              <div style={{ fontSize: "13px", color: "var(--text-secondary)" }}>
                Verify simulated payloads or execute live creation across all {successfulPlans.length} approved plans.
              </div>
            </div>

            <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={handleDryRunAll}
                disabled={dryRunRunning || executing || successfulPlans.length === 0}
                style={{ fontSize: "14px" }}
              >
                {dryRunRunning ? "Simulating Dry-Run..." : "🔍 Dry-Run Preview All"}
              </button>

              <button
                type="button"
                className="btn btn-primary"
                onClick={() => {
                  setConfirmCheckbox(false);
                  setShowConfirmModal(true);
                }}
                disabled={executing || dryRunRunning || successfulPlans.length === 0}
                style={{ fontSize: "14px", padding: "8px 20px" }}
              >
                {executing ? "Creating Tasks in Zoho..." : `🚀 Create All ${totalPlannedTasks} Tasks in Zoho`}
              </button>
            </div>
          </div>

          {/* Dry Run Summary Alert */}
          {dryRunSummary && (
            <div
              className="card"
              style={{
                marginBottom: "20px",
                border: "1px solid rgba(16, 185, 129, 0.4)",
                background: "rgba(16, 185, 129, 0.08)",
                padding: "16px 20px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <span style={{ fontSize: "20px" }}>✓</span>
                <div>
                  <strong style={{ color: "var(--color-success)" }}>Dry-Run Simulation Complete:</strong>{" "}
                  Successfully validated <strong>{dryRunSummary.totalOps}</strong> API write payloads across{" "}
                  <strong>{dryRunSummary.totalPlans}</strong> stories. Zero writes were made to Zoho Sprints.
                </div>
              </div>
            </div>
          )}

          {/* Execution Error Alert */}
          {executionError && (
            <div
              className="card"
              style={{
                marginBottom: "20px",
                border: "1px solid rgba(239, 68, 68, 0.4)",
                background: "rgba(239, 68, 68, 0.08)",
                color: "var(--color-error)",
              }}
            >
              <strong>Execution Error:</strong> {executionError}
            </div>
          )}

          {/* Live Execution Results Table */}
          {executionResults && (
            <div className="card" style={{ marginBottom: "28px" }}>
              <h3 style={{ fontSize: "16px", fontWeight: "700", marginBottom: "14px", color: "var(--text-highlight)" }}>
                Live Batch Execution Results
              </h3>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border-card)", textAlign: "left" }}>
                      <th style={{ padding: "10px" }}>Story ID</th>
                      <th style={{ padding: "10px" }}>Status</th>
                      <th style={{ padding: "10px" }}>Created</th>
                      <th style={{ padding: "10px" }}>Skipped</th>
                      <th style={{ padding: "10px" }}>Failed</th>
                      <th style={{ padding: "10px" }}>Execution ID</th>
                      <th style={{ padding: "10px", textAlign: "right" }}>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {executionResults.map((item) => {
                      const res = item.result;
                      const isComplete = res && res.failed_tasks === 0;
                      return (
                        <tr key={item.plan_id} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                          <td style={{ padding: "12px 10px", fontFamily: "var(--font-mono)" }}>
                            {item.story_id || item.plan_id}
                          </td>
                          <td style={{ padding: "12px 10px" }}>
                            {item.success && res ? (
                              <span className={`badge ${isComplete ? "badge-success" : "badge-warning"}`}>
                                {res.status}
                              </span>
                            ) : (
                              <span className="badge badge-error">FAILED</span>
                            )}
                          </td>
                          <td style={{ padding: "12px 10px", color: "var(--color-success)", fontWeight: "600" }}>
                            {res?.created_tasks || 0}
                          </td>
                          <td style={{ padding: "12px 10px", color: "var(--color-warning)" }}>
                            {res?.skipped_tasks || 0}
                          </td>
                          <td style={{ padding: "12px 10px", color: "var(--color-error)" }}>
                            {res?.failed_tasks || (item.error ? 1 : 0)}
                          </td>
                          <td style={{ padding: "12px 10px", fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--text-muted)" }}>
                            {res?.execution_id || "-"}
                          </td>
                          <td style={{ padding: "12px 10px", textAlign: "right" }}>
                            {res?.execution_id ? (
                              <Link
                                href={`/executions/${res.execution_id}`}
                                className="btn btn-secondary"
                                style={{ fontSize: "11px", padding: "4px 8px" }}
                              >
                                View Log →
                              </Link>
                            ) : (
                              <span style={{ fontSize: "12px", color: "var(--color-error)" }}>{item.error || "Error"}</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Generated Stories Review Table with Filter & Search */}
          <div className="card">
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "16px",
                flexWrap: "wrap",
                gap: "10px",
              }}
            >
              <div style={{ display: "flex", gap: "8px" }}>
                <button
                  type="button"
                  className={`btn ${statusFilter === "ALL" ? "btn-primary" : "btn-secondary"}`}
                  onClick={() => setStatusFilter("ALL")}
                  style={{ fontSize: "12px", padding: "6px 12px" }}
                >
                  All ({generationResults.length})
                </button>
                <button
                  type="button"
                  className={`btn ${statusFilter === "SUCCESS" ? "btn-primary" : "btn-secondary"}`}
                  onClick={() => setStatusFilter("SUCCESS")}
                  style={{ fontSize: "12px", padding: "6px 12px" }}
                >
                  Success ({successfulPlans.length})
                </button>
                {failedCount > 0 && (
                  <button
                    type="button"
                    className={`btn ${statusFilter === "FAILED" ? "btn-danger" : "btn-secondary"}`}
                    onClick={() => setStatusFilter("FAILED")}
                    style={{ fontSize: "12px", padding: "6px 12px" }}
                  >
                    Failed ({failedCount})
                  </button>
                )}
              </div>

              <div style={{ maxWidth: "300px", width: "100%" }}>
                <input
                  type="text"
                  className="input"
                  placeholder="Filter stories..."
                  value={filterTerm}
                  onChange={(e) => setFilterTerm(e.target.value)}
                  style={{ fontSize: "13px", padding: "6px 12px" }}
                />
              </div>
            </div>

            {/* Table */}
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border-card)", textAlign: "left", color: "var(--text-secondary)" }}>
                    <th style={{ padding: "10px", width: "32px" }}></th>
                    <th style={{ padding: "10px" }}>Story ID</th>
                    <th style={{ padding: "10px" }}>Story Summary / Title</th>
                    <th style={{ padding: "10px", textAlign: "center" }}>FE Tasks</th>
                    <th style={{ padding: "10px", textAlign: "center" }}>BE Tasks</th>
                    <th style={{ padding: "10px", textAlign: "center" }}>Total</th>
                    <th style={{ padding: "10px" }}>Duplicates</th>
                    <th style={{ padding: "10px" }}>Status</th>
                    <th style={{ padding: "10px", textAlign: "right" }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredResults.map((item) => {
                    const plan = item.plan;
                    const feCount = plan ? plan.tasks.filter((t) => t.task_type === "FE").length : 0;
                    const beCount = plan ? plan.tasks.filter((t) => t.task_type === "BE").length : 0;
                    const dupCount = plan ? plan.duplicate_warnings.length : 0;
                    const isExpanded = expandedStoryId === item.story_id;

                    return (
                      <Fragment key={item.story_id}>
                        <tr
                          style={{
                            borderBottom: isExpanded ? "none" : "1px solid var(--border-subtle)",
                            background: isExpanded ? "rgba(99, 102, 241, 0.05)" : "transparent",
                          }}
                        >
                          <td style={{ padding: "12px 8px", textAlign: "center" }}>
                            {plan && (
                              <button
                                type="button"
                                onClick={() => setExpandedStoryId(isExpanded ? null : item.story_id)}
                                style={{
                                  background: "transparent",
                                  border: "none",
                                  color: "var(--text-muted)",
                                  cursor: "pointer",
                                  fontSize: "12px",
                                }}
                              >
                                {isExpanded ? "▼" : "▶"}
                              </button>
                            )}
                          </td>
                          <td style={{ padding: "12px 10px", fontFamily: "var(--font-mono)", fontWeight: "600" }}>
                            <Link href={`/stories/${item.story_id}`} style={{ color: "var(--accent-primary)", textDecoration: "none" }}>
                              {item.story_id}
                            </Link>
                          </td>
                          <td style={{ padding: "12px 10px", maxWidth: "340px" }}>
                            {plan ? (
                              <div style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                {plan.story_title}
                              </div>
                            ) : (
                              <span style={{ color: "var(--color-error)" }}>{item.error || "Generation Failed"}</span>
                            )}
                          </td>
                          <td style={{ padding: "12px 10px", textAlign: "center" }}>
                            {plan ? <span className="badge badge-info">{feCount}</span> : "-"}
                          </td>
                          <td style={{ padding: "12px 10px", textAlign: "center" }}>
                            {plan ? <span className="badge badge-primary">{beCount}</span> : "-"}
                          </td>
                          <td style={{ padding: "12px 10px", textAlign: "center", fontWeight: "700" }}>
                            {plan ? plan.tasks.length : "-"}
                          </td>
                          <td style={{ padding: "12px 10px" }}>
                            {dupCount > 0 ? (
                              <span className="badge badge-warning">⚠️ {dupCount} Overlap</span>
                            ) : plan ? (
                              <span style={{ color: "var(--color-success)", fontSize: "12px" }}>✓ None</span>
                            ) : (
                              "-"
                            )}
                          </td>
                          <td style={{ padding: "12px 10px" }}>
                            {item.success ? (
                              <span className="badge badge-success">READY</span>
                            ) : (
                              <span className="badge badge-error">FAILED</span>
                            )}
                          </td>
                          <td style={{ padding: "12px 10px", textAlign: "right" }}>
                            {plan && (
                              <Link
                                href={`/plans/${plan.plan_id}`}
                                className="btn btn-secondary"
                                target="_blank"
                                style={{ fontSize: "11px", padding: "4px 8px" }}
                              >
                                Edit Plan ↗
                              </Link>
                            )}
                          </td>
                        </tr>

                        {/* Expanded Tasks Row */}
                        {isExpanded && plan && (
                          <tr style={{ background: "rgba(99, 102, 241, 0.03)", borderBottom: "1px solid var(--border-subtle)" }}>
                            <td colSpan={9} style={{ padding: "12px 20px 20px" }}>
                              <div style={{ fontSize: "13px", fontWeight: "700", marginBottom: "10px", color: "var(--text-highlight)" }}>
                                Generated Tasks for Story {item.story_id}:
                              </div>
                              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "10px" }}>
                                {plan.tasks.map((t) => (
                                  <div
                                    key={t.id}
                                    style={{
                                      background: "rgba(10, 14, 23, 0.6)",
                                      border: "1px solid var(--border-subtle)",
                                      borderRadius: "6px",
                                      padding: "10px 12px",
                                    }}
                                  >
                                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                                      <span className={`badge ${t.task_type === "FE" ? "badge-info" : "badge-primary"}`} style={{ fontSize: "11px" }}>
                                        {t.task_type}
                                      </span>
                                      {t.assignee && (
                                        <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                                          👤 {t.assignee.display_name || t.assignee.user_id}
                                        </span>
                                      )}
                                    </div>
                                    <div style={{ fontSize: "12px", fontWeight: "600", color: "#ffffff" }}>
                                      {t.title}
                                    </div>
                                    <div style={{ fontSize: "11px", color: "var(--text-secondary)", marginTop: "4px", lineHeight: "1.4" }}>
                                      {t.objective}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Safety Confirmation Modal */}
      {showConfirmModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0, 0, 0, 0.75)",
            backdropFilter: "blur(4px)",
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
              maxWidth: "520px",
              width: "100%",
              border: "1px solid rgba(99, 102, 241, 0.5)",
              boxShadow: "var(--shadow-glow)",
              padding: "28px",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "16px" }}>
              <span style={{ fontSize: "24px" }}>⚠️</span>
              <h3 style={{ fontSize: "18px", fontWeight: "800", color: "var(--text-highlight)" }}>
                Confirm Live Bulk Task Creation
              </h3>
            </div>

            <p style={{ fontSize: "14px", color: "var(--text-secondary)", lineHeight: "1.6", marginBottom: "16px" }}>
              You are about to create <strong style={{ color: "var(--accent-primary)" }}>{totalPlannedTasks} tasks</strong> across{" "}
              <strong style={{ color: "var(--accent-primary)" }}>{successfulPlans.length} stories</strong> in Zoho Sprints.
            </p>

            <div
              style={{
                background: "rgba(245, 158, 11, 0.1)",
                border: "1px solid rgba(245, 158, 11, 0.3)",
                borderRadius: "var(--radius-sm)",
                padding: "12px",
                fontSize: "12px",
                color: "var(--color-warning)",
                marginBottom: "20px",
                lineHeight: "1.5",
              }}
            >
              🔒 <strong>Safety Lock Active:</strong> Live Zoho API POST write operations will be executed. Please ensure you have reviewed the generated task cards and duplicate overlap warnings.
            </div>

            <label
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: "10px",
                cursor: "pointer",
                marginBottom: "24px",
                fontSize: "13px",
              }}
            >
              <input
                type="checkbox"
                checked={confirmCheckbox}
                onChange={(e) => setConfirmCheckbox(e.target.checked)}
                style={{ marginTop: "3px", width: "16px", height: "16px" }}
              />
              <span>I confirm that I have reviewed these plans and approve creating all subtasks in Zoho Sprints.</span>
            </label>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "12px" }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setShowConfirmModal(false)}
                style={{ fontSize: "13px" }}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={!confirmCheckbox}
                onClick={handleConfirmLiveExecution}
                style={{ fontSize: "13px", padding: "8px 20px" }}
              >
                Confirm & Create All ({totalPlannedTasks} Tasks)
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
