import type { HealthData, OnboardingInput, Profile, TodayData } from "./types";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, options);
  if (!response.ok) {
    let message = "服务暂时不可用，请稍后重试。";
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      // Keep the user-facing fallback when the server response is not JSON.
    }
    throw new Error(message);
  }
  return (await response.json()) as T;
}

export function getProfile(): Promise<Profile | null> {
  return request<Profile | null>("/api/v1/profile");
}

export async function saveOnboarding(input: OnboardingInput): Promise<Profile> {
  const response = await request<{ profile: Profile }>("/api/v1/onboarding", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return response.profile;
}

export function getToday(): Promise<TodayData> {
  return request<TodayData>("/api/v1/today");
}

export function getHealth(): Promise<HealthData> {
  return request<HealthData>("/api/health");
}

