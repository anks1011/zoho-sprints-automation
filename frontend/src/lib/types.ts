/** Type definitions for Zoho Sprints AI Automation Web Interface */

export interface Subitem {
  id: string;
  name: string;
  description?: string;
  item_type_id?: string;
  item_type_name?: string;
  priority_id?: string;
  priority_name?: string;
  status?: string;
  point?: number | null;
}

export interface StoryDetails {
  id: string;
  name: string;
  description: string;
  acceptance_criteria?: string | null;
  team_id?: string;
  project_id?: string;
  sprint_id?: string;
  item_type_id?: string;
  item_type_name?: string;
  priority_id?: string;
  priority_name?: string;
  status?: string;
  subitems: Subitem[];
}

export interface AuthStatus {
  is_authenticated: boolean;
  has_refresh_token: boolean;
  is_expired: boolean;
  expires_at_iso?: string | null;
  accounts_url: string;
  message: string;
}

export interface DuplicateWarning {
  generated_title: string;
  existing_title: string;
  existing_id: string;
  match_type: string;
  similarity_score: number;
  recommendation: string;
}

export interface TaskOwner {
  user_id: string;
  display_name?: string | null;
  email?: string | null;
}

export interface ValidationIssue {
  code: string;
  message: string;
  field?: string | null;
}

export interface PlanValidationResult {
  valid: boolean;
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
}

export interface GeneratedTask {
  id: string;
  title: string;
  task_type: "FE" | "BE";
  index?: number | null;
  objective: string;
  scope: string;
  expected_behavior: string;
  dependencies: string;
  description?: string;
  testing_considerations?: string;
  acceptance_criteria?: string[];
  assignee?: TaskOwner | null;
  qa_owner?: TaskOwner | null;
}

export interface PlanResponse {
  plan_id: string;
  story_id: string;
  story_title: string;
  story_summary: string;
  team_id: string;
  project_id: string;
  sprint_id: string;
  status: string;
  assumptions: string[];
  ambiguities: string[];
  tasks: GeneratedTask[];
  dev_owner?: TaskOwner | null;
  qa_owner?: TaskOwner | null;
  validation?: PlanValidationResult | null;
  duplicate_warnings: DuplicateWarning[];
  created_at: string;
  updated_at?: string | null;
}

export interface UpdatePlanRequest {
  tasks: GeneratedTask[];
  story_summary?: string;
  status?: string;
}

export interface DryRunOperation {
  task_title: string;
  method: string;
  endpoint: string;
  payload: Record<string, unknown>;
  item_type_id?: string;
  priority_id?: string;
}

export interface DryRunResponse {
  plan_id: string;
  story_id: string;
  total_operations: number;
  operations: DryRunOperation[];
}

export interface ExecutePlanRequest {
  confirm: boolean;
  dry_run?: boolean;
}

export interface TaskExecutionState {
  title: string;
  task_type: "FE" | "BE";
  status: "PENDING" | "CREATED" | "FAILED" | "SKIPPED";
  zoho_task_id?: string | null;
  zoho_task_url?: string | null;
  error_message?: string | null;
  attempted_at?: string | null;
}

export interface CreationResult {
  execution_id: string;
  plan_id?: string;
  story_id?: string;
  total_tasks: number;
  created_tasks: number;
  skipped_tasks: number;
  failed_tasks: number;
  status: string;
  tasks: TaskExecutionState[];
  is_dry_run: boolean;
}

export interface ExecutionRecord {
  execution_id: string;
  plan_id: string;
  story_id: string;
  team_id: string;
  project_id: string;
  sprint_id: string;
  status: string;
  tasks: TaskExecutionState[];
  created_count: number;
  failed_count: number;
  pending_count: number;
  created_at: string;
  updated_at: string;
}

export interface ApiError {
  detail: string;
  error_code?: string;
}

export interface BulkPlanItem {
  story_id: string;
  success: boolean;
  error?: string | null;
  plan?: PlanResponse | null;
}

export interface BulkGenerateResponse {
  total: number;
  successful: number;
  failed: number;
  results: BulkPlanItem[];
}

export interface BulkExecuteItem {
  plan_id: string;
  story_id?: string | null;
  story_title?: string | null;
  success: boolean;
  error?: string | null;
  result?: CreationResult | null;
}

export interface BulkExecuteResponse {
  total: number;
  successful: number;
  failed: number;
  dry_run: boolean;
  results: BulkExecuteItem[];
}

export interface SprintStoryItem {
  story_id: string;
  name: string;
  item_type_id?: string | null;
  item_type_name?: string | null;
  priority_id?: string | null;
  priority_name?: string | null;
  status?: string | null;
  point?: number | null;
  dev_owner_id?: string | null;
  dev_owner_name?: string | null;
  qa_owner_id?: string | null;
  qa_owner_name?: string | null;
  is_current_story?: boolean;
}

export interface SprintStoriesResponse {
  input_story_id: string;
  team_id: string;
  project_id: string;
  sprint_id: string;
  sprint_name?: string | null;
  current_user_dev_id?: string | null;
  current_user_dev_name?: string | null;
  filter_applied: boolean;
  total_sprint_stories: number;
  matched_stories_count: number;
  stories: SprintStoryItem[];
}


