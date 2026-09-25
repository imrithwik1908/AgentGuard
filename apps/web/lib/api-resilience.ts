const DEFAULT_REQUEST_TIMEOUT_MS = 55_000;
const MIN_REQUEST_TIMEOUT_MS = 5_000;
const MAX_REQUEST_TIMEOUT_MS = 60_000;

const RETRYABLE_GATEWAY_STATUSES = new Set([502, 503, 504]);

export function requestTimeoutMs(configuredValue?: string): number {
  if (!configuredValue) return DEFAULT_REQUEST_TIMEOUT_MS;

  const parsed = Number.parseInt(configuredValue, 10);
  if (!Number.isFinite(parsed)) return DEFAULT_REQUEST_TIMEOUT_MS;
  return Math.min(MAX_REQUEST_TIMEOUT_MS, Math.max(MIN_REQUEST_TIMEOUT_MS, parsed));
}

export function mayRetryRequest(method: string | undefined, status: number): boolean {
  const normalizedMethod = (method ?? "GET").toUpperCase();
  return (normalizedMethod === "GET" || normalizedMethod === "HEAD") &&
    RETRYABLE_GATEWAY_STATUSES.has(status);
}

export function apiConnectionMessage(timedOut: boolean): string {
  return timedOut
    ? "AgentGuard's API is taking longer than expected to wake. Please retry in a moment."
    : "AgentGuard's API is waking up or temporarily unavailable. Please retry in a moment.";
}
