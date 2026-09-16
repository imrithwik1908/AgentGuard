import type { ApplicationVersion, Project, Trace } from "./types";

export interface ProductStats {
  projectCount: number;
  versionCount: number;
  traceCount: number;
  okCount: number;
  errorCount: number;
  spanCount: number;
}

export function summarizeTelemetry({
  projects,
  versions,
  traces
}: {
  projects: Project[];
  versions: ApplicationVersion[];
  traces: Trace[];
}): ProductStats {
  return {
    projectCount: projects.length,
    versionCount: versions.length,
    traceCount: traces.length,
    okCount: traces.filter((trace) => trace.status === "OK").length,
    errorCount: traces.filter((trace) => trace.status === "ERROR").length,
    spanCount: traces.reduce((total, trace) => total + trace.spans.length, 0)
  };
}

export function latestErrorTrace(traces: Trace[]): Trace | null {
  return traces.find((trace) => trace.status === "ERROR") ?? null;
}
