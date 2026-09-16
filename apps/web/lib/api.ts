import "server-only";

import { getAccessToken } from "./session";
import type {
  ApplicationVersion,
  ApiKey,
  ApiKeyCreateResponse,
  AuthTokenPair,
  Dataset,
  DatasetCase,
  DatasetCaseRun,
  DatasetList,
  DemoSeedResult,
  EvaluationList,
  EvaluationSummary,
  Project,
  ProviderIntegration,
  ReleaseDecision,
  RedactionPolicy,
  RunStatus,
  Trace,
  TraceList,
  VersionComparison,
  Workspace
} from "./types";

function normalizeApiUrl(value: string): string {
  return /^https?:\/\//.test(value) ? value : `http://${value}`;
}

const API_URL = normalizeApiUrl(process.env.AGENTGUARD_API_URL ?? "http://localhost:8000");
const REQUEST_TIMEOUT_MS = 1200;

export function getApiUrl(): string {
  return API_URL;
}

export class ApiRequestError extends Error {
  readonly status: number;
  readonly details: unknown;

  constructor(message: string, status: number, details: unknown) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.details = details;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const token = await getAccessToken();
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: {
        "content-type": "application/json",
        ...(token ? { authorization: `Bearer ${token}` } : {}),
        ...(init?.headers ?? {})
      },
      signal: controller.signal,
      cache: "no-store"
    });
  } catch (error) {
    throw new ApiRequestError(
      `AgentGuard API is unreachable at ${API_URL}`,
      0,
      error instanceof Error ? error.message : String(error)
    );
  } finally {
    clearTimeout(timeout);
  }

  if (!response.ok) {
    let details: unknown = null;
    try {
      details = await response.json();
    } catch {
      details = await response.text();
    }
    throw new ApiRequestError(`AgentGuard API request failed: ${path}`, response.status, details);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function registerAccount(input: {
  workspace_name: string;
  workspace_slug: string;
  email: string;
  name: string;
  password: string;
}): Promise<AuthTokenPair> {
  return request<AuthTokenPair>("/api/v1/security/auth/register", {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export async function loginAccount(input: {
  email: string;
  password: string;
  workspace_slug?: string;
}): Promise<AuthTokenPair> {
  return request<AuthTokenPair>("/api/v1/security/auth/login", {
    method: "POST",
    body: JSON.stringify({
      ...input,
      workspace_slug: input.workspace_slug || null
    })
  });
}

export async function logoutAccount(): Promise<void> {
  await request<void>("/api/v1/security/auth/logout", { method: "POST" });
}

export async function listProjects(): Promise<Project[]> {
  return request<Project[]>("/api/v1/projects?limit=200");
}

export async function createProject(input: {
  workspace_id?: string;
  name: string;
  slug: string;
  description?: string;
}): Promise<Project> {
  return request<Project>("/api/v1/projects", {
    method: "POST",
    body: JSON.stringify({ ...input, description: input.description || null })
  });
}

export async function listWorkspaces(): Promise<Workspace[]> {
  return request<Workspace[]>("/api/v1/security/workspaces");
}

export async function listApiKeys(): Promise<ApiKey[]> {
  return request<ApiKey[]>("/api/v1/security/api-keys");
}

export async function createApiKey(input: {
  workspace_id: string;
  name: string;
}): Promise<ApiKeyCreateResponse> {
  return request<ApiKeyCreateResponse>("/api/v1/security/api-keys", {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export async function listProviders(): Promise<ProviderIntegration[]> {
  return request<ProviderIntegration[]>("/api/v1/security/providers");
}

export async function listRedactionPolicies(): Promise<RedactionPolicy[]> {
  return request<RedactionPolicy[]>("/api/v1/security/redaction-policies");
}

export async function createVersion(
  projectIdOrSlug: string,
  input: {
    name: string;
    version: string;
    git_commit?: string;
  }
): Promise<ApplicationVersion> {
  return request<ApplicationVersion>(`/api/v1/projects/${projectIdOrSlug}/versions`, {
    method: "POST",
    body: JSON.stringify({
      name: input.name,
      version: input.version,
      git_commit: input.git_commit || null
    })
  });
}

export async function getProject(projectIdOrSlug: string): Promise<Project> {
  return request<Project>(`/api/v1/projects/${projectIdOrSlug}`);
}

export async function listVersions(projectIdOrSlug: string): Promise<ApplicationVersion[]> {
  return request<ApplicationVersion[]>(`/api/v1/projects/${projectIdOrSlug}/versions`);
}

export async function listTraces(filters?: {
  projectId?: string;
  versionId?: string;
  status?: RunStatus | "";
  limit?: number;
  offset?: number;
}): Promise<TraceList> {
  const params = new URLSearchParams();
  params.set("limit", String(filters?.limit ?? 100));
  params.set("offset", String(filters?.offset ?? 0));
  if (filters?.projectId) params.set("project_id", filters.projectId);
  if (filters?.versionId) params.set("application_version_id", filters.versionId);
  if (filters?.status) params.set("status", filters.status);
  return request<TraceList>(`/api/v1/traces?${params.toString()}`);
}

export async function getTrace(traceId: string): Promise<Trace> {
  return request<Trace>(`/api/v1/traces/${traceId}`);
}

export async function listEvaluations(filters?: {
  projectId?: string;
  versionId?: string;
  traceId?: string;
  limit?: number;
  offset?: number;
}): Promise<EvaluationList> {
  const params = new URLSearchParams();
  params.set("limit", String(filters?.limit ?? 100));
  params.set("offset", String(filters?.offset ?? 0));
  if (filters?.projectId) params.set("project_id", filters.projectId);
  if (filters?.versionId) params.set("application_version_id", filters.versionId);
  if (filters?.traceId) params.set("trace_id", filters.traceId);
  return request<EvaluationList>(`/api/v1/evaluations?${params.toString()}`);
}

export async function createStatusEvaluation(traceId: string) {
  return request(`/api/v1/evaluations/traces/${traceId}/status-check`, { method: "POST" });
}

export async function createTraceHealthEvaluation(traceId: string) {
  return request(`/api/v1/evaluations/traces/${traceId}/health-check`, { method: "POST" });
}

export async function getEvaluationSummary(versionId: string): Promise<EvaluationSummary> {
  return request<EvaluationSummary>(`/api/v1/evaluations/summary/${versionId}`);
}

export async function compareVersions(
  baselineVersionId: string,
  candidateVersionId: string
): Promise<VersionComparison> {
  const params = new URLSearchParams({
    baseline_version_id: baselineVersionId,
    candidate_version_id: candidateVersionId
  });
  return request<VersionComparison>(`/api/v1/evaluations/compare?${params.toString()}`);
}

export async function getReleaseDecision(
  baselineVersionId: string,
  candidateVersionId: string
): Promise<ReleaseDecision> {
  const params = new URLSearchParams({
    baseline_version_id: baselineVersionId,
    candidate_version_id: candidateVersionId
  });
  return request<ReleaseDecision>(`/api/v1/evaluations/release-decision?${params.toString()}`);
}

export async function listDatasets(filters?: {
  projectId?: string;
  limit?: number;
  offset?: number;
}): Promise<DatasetList> {
  const params = new URLSearchParams();
  params.set("limit", String(filters?.limit ?? 100));
  params.set("offset", String(filters?.offset ?? 0));
  if (filters?.projectId) params.set("project_id", filters.projectId);
  return request<DatasetList>(`/api/v1/datasets?${params.toString()}`);
}

export async function createDataset(input: {
  project_id: string;
  name: string;
  slug: string;
  description?: string;
  cases?: Array<{
    name: string;
    input: Record<string, unknown>;
    expected_output?: unknown;
    expected_substring?: string;
  }>;
}): Promise<Dataset> {
  return request<Dataset>("/api/v1/datasets", {
    method: "POST",
    body: JSON.stringify({
      ...input,
      description: input.description || null,
      cases: input.cases ?? []
    })
  });
}

export async function createDatasetCase(
  datasetId: string,
  input: {
    name: string;
    input: Record<string, unknown>;
    expected_output?: unknown;
    expected_substring?: string;
  }
): Promise<DatasetCase> {
  return request<DatasetCase>(`/api/v1/datasets/${datasetId}/cases`, {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export async function runDatasetCase(caseId: string, versionId: string): Promise<DatasetCaseRun> {
  return request<DatasetCaseRun>(`/api/v1/datasets/cases/${caseId}/run`, {
    method: "POST",
    body: JSON.stringify({ application_version_id: versionId })
  });
}

export async function seedDemo(): Promise<DemoSeedResult> {
  return request<DemoSeedResult>("/api/v1/demo/seed", { method: "POST" });
}
