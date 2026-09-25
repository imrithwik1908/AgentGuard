import { describe, expect, it } from "vitest";

import {
  apiConnectionMessage,
  mayRetryRequest,
  requestTimeoutMs
} from "@/lib/api-resilience";

describe("API cold-start resilience", () => {
  it("waits long enough for a sleeping free service by default", () => {
    expect(requestTimeoutMs()).toBe(55_000);
  });

  it("bounds configured request timeouts", () => {
    expect(requestTimeoutMs("1000")).toBe(5_000);
    expect(requestTimeoutMs("120000")).toBe(60_000);
    expect(requestTimeoutMs("invalid")).toBe(55_000);
  });

  it("retries only safe reads after temporary gateway failures", () => {
    expect(mayRetryRequest(undefined, 503)).toBe(true);
    expect(mayRetryRequest("GET", 502)).toBe(true);
    expect(mayRetryRequest("POST", 503)).toBe(false);
    expect(mayRetryRequest("GET", 401)).toBe(false);
  });

  it("explains a cold start without exposing infrastructure details", () => {
    expect(apiConnectionMessage(false)).toContain("waking up");
    expect(apiConnectionMessage(true)).toContain("taking longer than expected");
  });
});
