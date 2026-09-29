import {
  AuthStatus,
  BulkExecuteResponse,
  BulkGenerateResponse,
  CreationResult,
  DryRunResponse,
  ExecutePlanRequest,
  ExecutionRecord,
  PlanResponse,
  PlanValidationResult,
  SprintStoriesResponse,
  StoryDetails,
  UpdatePlanRequest,
} from "./types";

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = path.startsWith("http") ? path : path;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
  });

  if (!res.ok) {
    let detail = `Request failed with status ${res.status}`;
    try {
      const data = await res.json();
      if (data && data.detail) {
        detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
      }
    } catch {
      // Fallback to text
      const text = await res.text().catch(() => "");
      if (text) {
        if (text.includes("<html") || text.includes("<!DOCTYPE")) {
          detail = `Server error (${res.status}): Request failed or timed out. Please check backend server.`;
        } else {
          detail = text;
        }
      }
    }
    throw new ApiError(res.status, detail);
  }

  return res.json() as Promise<T>;
}

export async function fetchAuthStatus(): Promise<AuthStatus> {
  return apiFetch<AuthStatus>("/api/v1/auth/status");
}

export async function fetchStory(storyId: string): Promise<StoryDetails> {
  const cleanId = encodeURIComponent(storyId.trim());
  return apiFetch<StoryDetails>(`/api/v1/stories/${cleanId}`);
}

export async function generatePlan(storyId: string): Promise<PlanResponse> {
  return apiFetch<PlanResponse>("/api/v1/plans/generate", {
    method: "POST",
    body: JSON.stringify({ story_id: storyId.trim() }),
  });
}

export async function getPlan(planId: string): Promise<PlanResponse> {
  const cleanId = encodeURIComponent(planId.trim());
  return apiFetch<PlanResponse>(`/api/v1/plans/${cleanId}`);
}

export async function updatePlan(planId: string, req: UpdatePlanRequest): Promise<PlanResponse> {
  const cleanId = encodeURIComponent(planId.trim());
  return apiFetch<PlanResponse>(`/api/v1/plans/${cleanId}`, {
    method: "PUT",
    body: JSON.stringify(req),
  });
}

export async function dryRunPlan(planId: string): Promise<DryRunResponse> {
  const cleanId = encodeURIComponent(planId.trim());
  return apiFetch<DryRunResponse>(`/api/v1/plans/${cleanId}/dry-run`, {
    method: "POST",
  });
}

export async function executePlan(planId: string, req: ExecutePlanRequest): Promise<CreationResult> {
  const cleanId = encodeURIComponent(planId.trim());
  return apiFetch<CreationResult>(`/api/v1/plans/${cleanId}/execute`, {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function listExecutions(): Promise<ExecutionRecord[]> {
  return apiFetch<ExecutionRecord[]>("/api/v1/executions");
}

export async function getExecution(executionId: string): Promise<ExecutionRecord> {
  const cleanId = encodeURIComponent(executionId.trim());
  return apiFetch<ExecutionRecord>(`/api/v1/executions/${cleanId}`);
}

export async function resumeExecution(executionId: string): Promise<CreationResult> {
  const cleanId = encodeURIComponent(executionId.trim());
  return apiFetch<CreationResult>(`/api/v1/executions/${cleanId}/resume`, {
    method: "POST",
  });
}

export async function validatePlan(planId: string): Promise<PlanValidationResult> {
  const cleanId = encodeURIComponent(planId.trim());
  return apiFetch<PlanValidationResult>(`/api/v1/plans/${cleanId}/validate`, {
    method: "POST",
  });
}

export async function bulkGeneratePlans(
  storyIds: string[],
  teamId?: string,
  projectId?: string,
  sprintId?: string
): Promise<BulkGenerateResponse> {
  return apiFetch<BulkGenerateResponse>("/api/v1/plans/bulk-generate", {
    method: "POST",
    body: JSON.stringify({
      story_ids: storyIds,
      team_id: teamId,
      project_id: projectId,
      sprint_id: sprintId,
    }),
  });
}

export async function bulkExecutePlans(
  planIds: string[],
  dryRun = false,
  confirm = false
): Promise<BulkExecuteResponse> {
  return apiFetch<BulkExecuteResponse>("/api/v1/plans/bulk-execute", {
    method: "POST",
    body: JSON.stringify({
      plan_ids: planIds,
      dry_run: dryRun,
      confirm: confirm,
    }),
  });
}

export async function fetchSprintStories(
  storyId: string,
  filterDevOwner = true,
  devOwnerId?: string
): Promise<SprintStoriesResponse> {
  const cleanId = encodeURIComponent(storyId.trim());
  let url = `/api/v1/stories/${cleanId}/sprint-stories?filter_dev_owner=${filterDevOwner}`;
  if (devOwnerId) {
    url += `&developer_owner_id=${encodeURIComponent(devOwnerId)}`;
  }
  return apiFetch<SprintStoriesResponse>(url);
}


