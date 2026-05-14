import type { Conversation, ConversationSummary, CreateRunResponse, ResearchEvent } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

type TokenGetter = () => Promise<string | null>;

async function request<T>(path: string, getToken: TokenGetter, options: RequestInit = {}): Promise<T> {
  const token = await getToken();
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers
    }
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function listConversations(getToken: TokenGetter) {
  return request<ConversationSummary[]>("/api/conversations", getToken);
}

export function getConversation(id: string, getToken: TokenGetter) {
  return request<Conversation>(`/api/conversations/${id}`, getToken);
}

export function createResearchRun(prompt: string, getToken: TokenGetter) {
  return request<CreateRunResponse>("/api/research-runs", getToken, {
    method: "POST",
    body: JSON.stringify({ prompt })
  });
}

export function createFollowup(conversationId: string, content: string, getToken: TokenGetter) {
  return request<CreateRunResponse>(`/api/conversations/${conversationId}/messages`, getToken, {
    method: "POST",
    body: JSON.stringify({ content })
  });
}

export function sendPlanFeedback(runId: string, message: string, getToken: TokenGetter) {
  return request<{ run_id: string; plan: unknown }>(`/api/research-runs/${runId}/plan-feedback`, getToken, {
    method: "POST",
    body: JSON.stringify({ message })
  });
}

export function approveResearchRun(runId: string, getToken: TokenGetter) {
  return request<{ run_id: string; status: string; duration_seconds: number }>(`/api/research-runs/${runId}/approve`, getToken, {
    method: "POST"
  });
}

export function getResearchEvents(runId: string, getToken: TokenGetter) {
  return request<ResearchEvent[]>(`/api/research-runs/${runId}/events`, getToken);
}
