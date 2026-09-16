"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { ApiRequestError, createProject, createVersion } from "@/lib/api";

function messageFromError(error: unknown, fallback: string): string {
  if (error instanceof ApiRequestError) {
    const details = error.details as { message?: unknown } | null;
    if (typeof details?.message === "string") return details.message;
    return error.message;
  }
  if (error instanceof Error) return error.message;
  return fallback;
}

export async function createProjectAction(formData: FormData) {
  const name = String(formData.get("name") ?? "").trim();
  const slug = String(formData.get("slug") ?? "").trim();
  const description = String(formData.get("description") ?? "").trim();

  if (!name || !slug) {
    redirect("/projects?project_error=Project%20name%20and%20slug%20are%20required");
  }

  try {
    await createProject({ name, slug, description });
  } catch (error) {
    const message = encodeURIComponent(messageFromError(error, "Project could not be created"));
    redirect(`/projects?project_error=${message}`);
  }
  revalidatePath("/projects");
}

export async function createVersionAction(projectId: string, formData: FormData) {
  const name = String(formData.get("name") ?? "").trim();
  const version = String(formData.get("version") ?? "").trim();
  const gitCommit = String(formData.get("git_commit") ?? "").trim();

  if (!name || !version) {
    redirect(
      `/projects/${projectId}?version_error=Version%20name%20and%20version%20are%20required`
    );
  }

  try {
    await createVersion(projectId, { name, version, git_commit: gitCommit });
  } catch (error) {
    const message = encodeURIComponent(messageFromError(error, "Version could not be registered"));
    redirect(`/projects/${projectId}?version_error=${message}`);
  }
  revalidatePath(`/projects/${projectId}`);
  revalidatePath("/traces");
}
