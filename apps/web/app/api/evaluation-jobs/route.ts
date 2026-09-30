import { NextResponse } from "next/server";

import { ApiRequestError, getEvaluationJob } from "@/lib/api";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const jobIds = searchParams.get("job_ids")?.split(",").filter(Boolean) ?? [];

  if (jobIds.length === 0) {
    return NextResponse.json({ detail: "At least one evaluation job is required." }, { status: 400 });
  }

  try {
    const jobs = await Promise.all(jobIds.map((jobId) => getEvaluationJob(jobId)));
    return NextResponse.json(jobs, {
      headers: { "cache-control": "no-store, max-age=0" }
    });
  } catch (error) {
    const status = error instanceof ApiRequestError && error.status > 0 ? error.status : 502;
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Evaluation status is unavailable." },
      { status, headers: { "cache-control": "no-store, max-age=0" } }
    );
  }
}
