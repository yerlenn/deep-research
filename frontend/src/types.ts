export type ResearchPlan = {
  title: string;
  goal: string;
  steps: string[];
  expected_output: string;
  revision_note?: string | null;
};

export type ResearchRunSummary = {
  id: string;
  status: "planning" | "awaiting_approval" | "running" | "completed" | "failed";
  plan: ResearchPlan | null;
  duration_seconds: number | null;
  created_at: string;
};

export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  research_run: ResearchRunSummary | null;
};

export type Conversation = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: Message[];
  pending_runs: ResearchRunSummary[];
};

export type ConversationSummary = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type CreateRunResponse = {
  conversation_id: string;
  message_id: string;
  run_id: string;
  plan: ResearchPlan;
};

export type ResearchEvent = {
  id: string;
  sequence_number: number;
  event_type: string;
  title: string;
  content: string;
  url: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
};
