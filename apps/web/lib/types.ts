export type RunStatus = "UNSET" | "OK" | "ERROR";
export type EvaluationStatus = "PASS" | "FAIL" | "ERROR";

export type SpanType =
  | "AGENT"
  | "LLM"
  | "RETRIEVER"
  | "TOOL"
  | "CHAIN"
  | "EMBEDDING"
  | "RERANKER"
  | "CUSTOM";

export type JsonValue =
  | null
  | boolean
  | number
  | string
  | JsonValue[]
  | { [key: string]: JsonValue };

export interface Project {
  id: string;
  workspace_id: string | null;
  name: string;
  slug: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface ApplicationVersion {
  id: string;
  project_id: string;
  name: string;
  version: string;
  git_commit: string | null;
  model_config: Record<string, JsonValue>;
  prompt_config: Record<string, JsonValue>;
  retrieval_config: Record<string, JsonValue>;
  agent_config: Record<string, JsonValue>;
  metadata: Record<string, JsonValue>;
  created_at: string;
}

export interface Span {
  id: string;
  trace_id: string;
  parent_span_id: string | null;
  external_span_id: string | null;
  type: SpanType;
  name: string;
  status: RunStatus;
  input: JsonValue | null;
  output: JsonValue | null;
  metadata: Record<string, JsonValue>;
  attributes: Record<string, JsonValue>;
  provider: string | null;
  model_name: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost: string | number | null;
  started_at: string;
  ended_at: string;
  duration_ms: number;
  error: Record<string, JsonValue> | null;
  created_at: string;
}

export interface Trace {
  id: string;
  project_id: string;
  application_version_id: string;
  external_trace_id: string | null;
  name: string;
  status: RunStatus;
  input: JsonValue | null;
  output: JsonValue | null;
  metadata: Record<string, JsonValue>;
  started_at: string;
  ended_at: string;
  duration_ms: number;
  total_input_tokens: number | null;
  total_output_tokens: number | null;
  estimated_cost: string | number | null;
  error: Record<string, JsonValue> | null;
  created_at: string;
  spans: Span[];
}

export interface TraceList {
  items: Trace[];
  limit: number;
  offset: number;
  total: number;
}

export interface EvaluationResult {
  id: string;
  project_id: string;
  dataset_id: string | null;
  dataset_case_id: string | null;
  application_version_id: string;
  trace_id: string;
  evaluator_name: string;
  score: string | number;
  threshold: string | number | null;
  status: EvaluationStatus;
  passed: boolean;
  label: string | null;
  explanation: string | null;
  metadata: Record<string, JsonValue>;
  created_at: string;
}

export interface EvaluationList {
  items: EvaluationResult[];
  limit: number;
  offset: number;
  total: number;
}

export interface EvaluationSummary {
  project_id: string;
  application_version_id: string;
  evaluation_count: number;
  trace_count: number;
  pass_count: number;
  fail_count: number;
  error_count: number;
  pass_rate: string | number | null;
  average_score: string | number | null;
}

export interface VersionComparison {
  project_id: string;
  baseline_version_id: string;
  candidate_version_id: string;
  baseline: EvaluationSummary;
  candidate: EvaluationSummary;
  score_delta: string | number | null;
  pass_rate_delta: string | number | null;
  regression_count_delta: number;
}

export interface ReleaseDecision {
  project_id: string;
  baseline_version_id: string;
  candidate_version_id: string;
  decision: "PASS" | "BLOCK" | "REVIEW";
  summary: string;
  reasons: string[];
  comparison: VersionComparison;
  minimum_pass_rate: string | number;
  maximum_regressions: number;
  allowed_score_drop: string | number;
}

export interface DatasetCase {
  id: string;
  dataset_id: string;
  name: string;
  input: Record<string, JsonValue>;
  expected_output: JsonValue | null;
  expected_substring: string | null;
  metadata: Record<string, JsonValue>;
  created_at: string;
}

export interface Dataset {
  id: string;
  project_id: string;
  name: string;
  slug: string;
  description: string | null;
  metadata: Record<string, JsonValue>;
  created_at: string;
  cases: DatasetCase[];
}

export interface DatasetList {
  items: Dataset[];
  limit: number;
  offset: number;
  total: number;
}

export interface DatasetCaseRun {
  dataset_id: string;
  dataset_case_id: string;
  application_version_id: string;
  trace: Trace;
  evaluation: EvaluationResult;
}

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  created_at: string;
}

export interface User {
  id: string;
  workspace_id: string;
  email: string;
  name: string;
  role: string;
  created_at: string;
}

export interface AuthTokenPair {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_at: string;
  refresh_expires_at: string;
  user: User;
  workspace: Workspace;
}

export interface ProviderIntegration {
  id: string;
  workspace_id: string;
  provider: string;
  name: string;
  default_model: string | null;
  base_url: string | null;
  api_key_secret_ref: string | null;
  is_enabled: boolean;
  created_at: string;
}

export interface RedactionPolicy {
  id: string;
  workspace_id: string;
  name: string;
  mode: string;
  patterns: string;
  is_enabled: boolean;
  created_at: string;
}

export interface DemoSeedResult {
  project_id: string;
  baseline_version_id: string;
  candidate_version_id: string;
  dataset_id: string;
  trace_ids: string[];
  message: string;
}
