"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { seedDemo } from "@/lib/api";

export async function seedDemoAction() {
  let baseline = "";
  let candidate = "";
  try {
    const result = await seedDemo();
    baseline = result.baseline_version_id;
    candidate = result.candidate_version_id;
  } catch (error) {
    const message = encodeURIComponent(error instanceof Error ? error.message : String(error));
    redirect(`/?demo_error=${message}`);
  }

  revalidatePath("/");
  revalidatePath("/projects");
  revalidatePath("/traces");
  revalidatePath("/datasets");
  revalidatePath("/evaluations");
  revalidatePath("/releases");
  redirect(`/releases?baseline_version_id=${baseline}&candidate_version_id=${candidate}`);
}
