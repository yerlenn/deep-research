import { ArrowUp, BookOpen, Check, ChevronRight, Edit3, FileText, PanelLeft, Search, X } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Link, Route, Routes, useNavigate, useParams } from "react-router-dom";

import { approveResearchRun, createFollowup, createResearchRun, getConversation, getResearchEvents, listConversations, sendPlanFeedback } from "../api";
import { useAppAuth } from "../auth";
import type { Conversation, ConversationSummary, ResearchEvent, ResearchRunSummary } from "../types";

const pendingPromptKey = "pendingResearchPrompt";

function formatDuration(seconds: number | null) {
  if (!seconds) return "a moment";
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return minutes > 0 ? `${minutes}m ${rest}s` : `${rest}s`;
}

export function AppShell() {
  const { isLoaded, isSignedIn, getToken, userControl } = useAppAuth();
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  async function refreshConversations() {
    if (!isLoaded || !isSignedIn) return;
    setConversations(await listConversations(getToken));
  }

  useEffect(() => {
    void refreshConversations();
  }, [isLoaded, isSignedIn]);

  return (
    <div className="app">
      <aside className={sidebarOpen ? "sidebar open" : "sidebar"}>
        <div className="sidebar-top">
          <Link className="new-chat" to="/">
            <Edit3 size={16} />
            New research
          </Link>
          <button className="icon-button mobile-only" onClick={() => setSidebarOpen(false)} aria-label="Close sidebar">
            <X size={18} />
          </button>
        </div>
        <nav className="conversation-list">
          {conversations.map((item) => (
            <Link key={item.id} to={`/c/${item.id}`} className="conversation-link">
              <span>{item.title}</span>
              <ChevronRight size={14} />
            </Link>
          ))}
        </nav>
      </aside>

      <main className="main">
        <header className="topbar">
          <button className="icon-button" onClick={() => setSidebarOpen((value) => !value)} aria-label="Toggle sidebar">
            <PanelLeft size={18} />
          </button>
          <div className="brand">
            <span className="brand-mark" aria-hidden="true" />
            <span>Deep Research</span>
          </div>
          <div className="user-slot">{userControl}</div>
        </header>
        <Routes>
          <Route path="/" element={<NewChat onCreated={refreshConversations} />} />
          <Route path="/c/:conversationId" element={<ConversationPage onChanged={refreshConversations} />} />
        </Routes>
      </main>
    </div>
  );
}

function NewChat({ onCreated }: { onCreated: () => Promise<void> }) {
  const auth = useAppAuth();
  const navigate = useNavigate();
  const [prompt, setPrompt] = useState("");
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const saved = sessionStorage.getItem(pendingPromptKey);
    if (saved) {
      setPrompt(saved);
    }
  }, []);

  async function submit() {
    const clean = prompt.trim();
    if (!clean) return;
    if (!auth.isSignedIn) {
      sessionStorage.setItem(pendingPromptKey, clean);
      setAuthModalOpen(true);
      return;
    }
    setError(null);
    setIsSubmitting(true);
    try {
      const response = await createResearchRun(clean, auth.getToken);
      sessionStorage.removeItem(pendingPromptKey);
      await onCreated();
      navigate(`/c/${response.conversation_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create research run");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="new-chat-screen">
      <div className="new-chat-copy">
        <h1>What should we research?</h1>
      </div>
      <Composer value={prompt} onChange={setPrompt} onSubmit={submit} disabled={isSubmitting} placeholder="Ask a research question..." />
      {error && <p className="error-text">{error}</p>}
      {authModalOpen && <AuthRequiredModal onClose={() => setAuthModalOpen(false)} />}
    </section>
  );
}

function ConversationPage({ onChanged }: { onChanged: () => Promise<void> }) {
  const { conversationId } = useParams();
  const auth = useAppAuth();
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    if (!conversationId) return;
    setConversation(await getConversation(conversationId, auth.getToken));
  }

  useEffect(() => {
    setLoading(true);
    setError(null);
    refresh()
      .catch((err) => setError(err instanceof Error ? err.message : "Could not load conversation"))
      .finally(() => setLoading(false));
  }, [conversationId]);

  async function submitFollowup() {
    if (!conversationId || !prompt.trim()) return;
    const content = prompt.trim();
    setPrompt("");
    try {
      await createFollowup(conversationId, content, auth.getToken);
      await refresh();
      await onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send message");
    }
  }

  async function handleRunChanged() {
    await refresh();
    await onChanged();
  }

  if (loading) return <div className="center-state">Loading conversation...</div>;
  if (error) return <div className="center-state error-text">{error}</div>;
  if (!conversation) return <div className="center-state">Conversation not found.</div>;

  return (
    <section className="conversation-screen">
      <div className="message-stack">
        {conversation.messages.map((message) => (
          <MessageBlock key={message.id} message={message} onRunChanged={handleRunChanged} />
        ))}
        {conversation.pending_runs.map((run) => (
          <PlanCard key={run.id} run={run} onChanged={handleRunChanged} />
        ))}
      </div>
      <div className="composer-dock">
        <Composer value={prompt} onChange={setPrompt} onSubmit={submitFollowup} placeholder="Ask a follow-up..." />
      </div>
    </section>
  );
}

function MessageBlock({ message, onRunChanged }: { message: Conversation["messages"][number]; onRunChanged: () => Promise<void> }) {
  const isUser = message.role === "user";
  return (
    <article className={isUser ? "message user-message" : "message assistant-message"}>
      {message.research_run && <RunSummary run={message.research_run} />}
      {isUser ? (
        <div className="message-content">{message.content}</div>
      ) : (
        <div className="message-content markdown-content">
          <ReactMarkdown>{message.content}</ReactMarkdown>
        </div>
      )}
      {!isUser && message.research_run?.status === "awaiting_approval" && <PlanCard run={message.research_run} onChanged={onRunChanged} />}
    </article>
  );
}

function PlanCard({ run, onChanged }: { run: ResearchRunSummary; onChanged: () => Promise<void> }) {
  const auth = useAppAuth();
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const plan = run.plan;

  async function approve() {
    setBusy(true);
    setError(null);
    try {
      await approveResearchRun(run.id, auth.getToken);
      await onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not approve plan");
    } finally {
      setBusy(false);
    }
  }

  async function revise(event: FormEvent) {
    event.preventDefault();
    if (!feedback.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await sendPlanFeedback(run.id, feedback.trim(), auth.getToken);
      setFeedback("");
      setFeedbackOpen(false);
      await onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not revise plan");
    } finally {
      setBusy(false);
    }
  }

  if (!plan || run.status !== "awaiting_approval") return null;

  return (
    <section className="plan-card">
      <div className="section-eyebrow">Agent plan</div>
      <h2>{plan.title}</h2>
      <p>{plan.goal}</p>
      <ol>
        {plan.steps.map((step, index) => (
          <li key={`${step}-${index}`}>{step}</li>
        ))}
      </ol>
      <p className="muted">{plan.expected_output}</p>
      <div className="plan-actions">
        <button className="button primary" onClick={approve} disabled={busy}>
          <Check size={16} />
          Approve
        </button>
        <button className="button" onClick={() => setFeedbackOpen((value) => !value)} disabled={busy}>
          <Edit3 size={16} />
          Edit
        </button>
      </div>
      {feedbackOpen && (
        <form className="feedback-form" onSubmit={revise}>
          <textarea value={feedback} onChange={(event) => setFeedback(event.target.value)} placeholder="Tell the agent what to change..." />
          <button className="button primary" disabled={busy || !feedback.trim()}>
            Regenerate plan
          </button>
        </form>
      )}
      {error && <p className="error-text">{error}</p>}
    </section>
  );
}

function RunSummary({ run }: { run: ResearchRunSummary }) {
  const auth = useAppAuth();
  const [open, setOpen] = useState(false);
  const [events, setEvents] = useState<ResearchEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const label = useMemo(() => {
    if (run.status === "completed") return `Agent researched for ${formatDuration(run.duration_seconds)}`;
    if (run.status === "running") return "Agent is researching...";
    return "Agent is preparing research...";
  }, [run]);

  async function openEvents() {
    setOpen(true);
    setLoading(true);
    try {
      setEvents(await getResearchEvents(run.id, auth.getToken));
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <button className="run-summary" onClick={openEvents}>
        <Search size={16} />
        <span>{label}</span>
      </button>
      {open && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="process-modal">
            <div className="modal-header">
              <div>
                <div className="section-eyebrow">Agent process</div>
                <h2>Full research log</h2>
              </div>
              <button className="icon-button" onClick={() => setOpen(false)} aria-label="Close process log">
                <X size={18} />
              </button>
            </div>
            {loading ? (
              <p className="muted">Loading process...</p>
            ) : (
              <div className="event-list">
                {events.map((event) => (
                  <div className="event-row" key={event.id}>
                    <div className="event-icon">
                      <BookOpen size={15} />
                    </div>
                    <div>
                      <h3>{event.title}</h3>
                      <p>{event.content}</p>
                      {event.url && (
                        <a href={event.url} target="_blank" rel="noreferrer">
                          {event.url}
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}

function Composer({
  value,
  onChange,
  onSubmit,
  disabled,
  placeholder
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void | Promise<void>;
  disabled?: boolean;
  placeholder: string;
}) {
  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void onSubmit();
  }

  return (
    <form className="composer" onSubmit={handleSubmit}>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            void onSubmit();
          }
        }}
        placeholder={placeholder}
        disabled={disabled}
      />
      <button className="send-button" disabled={disabled || !value.trim()} aria-label="Send research request">
        <ArrowUp size={18} />
      </button>
    </form>
  );
}

function AuthRequiredModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="auth-required-modal">
        <button className="icon-button close-modal" onClick={onClose} aria-label="Close">
          <X size={18} />
        </button>
        <FileText size={22} />
        <h2>Sign in to start research</h2>
        <p>Your prompt is saved. After signing in, it will be restored here for you to review and send.</p>
        <div className="modal-actions">
          <Link className="button primary" to="/sign-in">
            Sign in
          </Link>
          <Link className="button" to="/sign-up">
            Create account
          </Link>
        </div>
      </div>
    </div>
  );
}
