"use client";

// The workbench screen. All streaming, interrupt and subagent behaviour comes from LangChain's frontend SDK
// (`useStream`); this component only renders it. The browser never sees a token: requests go to /api/agent.

import { useStream } from "@langchain/react";
import { type FormEvent, useEffect, useMemo, useState } from "react";

import { type Choice, type Review, decisionsFor, reviewsOf } from "@/lib/decisions.ts";
import { isNotification, notificationIds } from "@/lib/messages.ts";

type Todo = { content: string; status: "pending" | "in_progress" | "completed" };
type AnyMessage = {
  id?: string;
  type?: string;
  getType?: () => string;
  content: unknown;
  tool_calls?: { id?: string; name: string }[];
  additional_kwargs?: Record<string, unknown>;
};
// Deep Agents records each background (async subagent) task in the `async_tasks` state channel.
type AsyncTask = { task_id: string; agent_name: string; status: string };
const FINISHED = new Set(["success", "error", "cancelled", "timeout", "interrupted"]);

const THREAD_KEY = "wb.threadId";

function textOf(content: unknown): string {
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((block) => (typeof block === "string" ? block : block?.type === "text" ? String(block.text ?? "") : ""))
      .join("");
  }
  return "";
}

function kindOf(message: AnyMessage): string {
  return message.type ?? message.getType?.() ?? "";
}

export function Workbench({ userName, assistantId }: { userName: string; assistantId: string }) {
  const [origin, setOrigin] = useState<string | null>(null);
  const [threadId, setThreadId] = useState<string | null>(null);

  useEffect(() => {
    setOrigin(window.location.origin);
    setThreadId(window.sessionStorage.getItem(THREAD_KEY));
  }, []);

  if (!origin) return <main className="shell" aria-busy="true" />;
  return (
    <Session
      key={threadId ?? "new"}
      apiUrl={`${origin}/api/agent`}
      assistantId={assistantId}
      userName={userName}
      threadId={threadId}
      onThreadId={(id) => {
        window.sessionStorage.setItem(THREAD_KEY, id);
      }}
      onNewTask={() => {
        window.sessionStorage.removeItem(THREAD_KEY);
        setThreadId(null);
        window.location.reload();
      }}
    />
  );
}

function Session(props: {
  apiUrl: string;
  assistantId: string;
  userName: string;
  threadId: string | null;
  onThreadId: (id: string) => void;
  onNewTask: () => void;
}) {
  const [knownThread, setKnownThread] = useState<string | null>(props.threadId);
  const stream = useStream({
    apiUrl: props.apiUrl,
    assistantId: props.assistantId,
    threadId: props.threadId,
    onThreadId: (id: string) => {
      setKnownThread(id);
      props.onThreadId(id);
    },
    transport: "sse",
  });
  const [draft, setDraft] = useState("");
  const [choices, setChoices] = useState<(Choice | undefined)[]>([]);
  const [openFile, setOpenFile] = useState<string | null>(null);

  const values = (stream.values ?? {}) as {
    todos?: Todo[];
    files?: Record<string, unknown>;
    async_tasks?: Record<string, AsyncTask>;
    messages?: AnyMessage[];
  };
  // A background task finishes after the run that started it, so its status is read from the thread while any
  // task is still open.
  const [polledTasks, setPolledTasks] = useState<Record<string, AsyncTask> | null>(null);
  const [polledAnswer, setPolledAnswer] = useState<string | null>(null);
  const [polledMessages, setPolledMessages] = useState<AnyMessage[]>([]);
  const streamTasks = values.async_tasks;
  const tasks = Object.values({ ...(streamTasks ?? {}), ...(polledTasks ?? {}) });
  const openTasks = tasks.some((task) => !FINISHED.has(task.status));
  useEffect(() => {
    if (!openTasks || !knownThread || stream.isLoading) return;
    let stopped = false;
    const timer = window.setInterval(async () => {
      try {
        const response = await fetch(`${props.apiUrl}/threads/${knownThread}/state`, { credentials: "same-origin" });
        if (!response.ok || stopped) return;
        const state = (await response.json()) as { values?: { async_tasks?: Record<string, AsyncTask>; messages?: AnyMessage[] } };
        setPolledTasks(state.values?.async_tasks ?? {});
        setPolledMessages(state.values?.messages ?? []);
        const last = state.values?.messages?.at(-1);
        if (last && (last.type ?? "") === "ai") setPolledAnswer(textOf(last.content));
      } catch {
        // the next tick retries
      }
    }, 2000);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [openTasks, knownThread, stream.isLoading, props.apiUrl]);
  const todos = values.todos ?? [];
  const files = values.files ?? {};
  const subagents = useMemo(() => [...stream.subagents.values()], [stream.subagents]);
  const pending = reviewsOf(stream.interrupt);
  const decisions = decisionsFor(pending, choices);
  // A new interrupt starts with no decisions.
  const interruptKey = JSON.stringify(pending.map((review) => review.action));
  useEffect(() => setChoices([]), [interruptKey]);
  // A background task's report is not something the user typed, so it is not shown as one. Streamed copies lose
  // its notification metadata, so it is also recognised by id in the thread values (streamed and polled).
  const hiddenIds = notificationIds([...(values.messages ?? []), ...polledMessages]);
  const messages = (stream.messages as unknown as AnyMessage[]).filter((m) => {
    const kind = kindOf(m);
    if (kind === "human") return !isNotification(m) && !(m.id && hiddenIds.has(m.id));
    return (kind === "ai" && (textOf(m.content) || m.tool_calls?.length));
  });

  const lastShown = messages.length ? textOf(messages[messages.length - 1].content) : "";
  const backgroundAnswer = polledAnswer && polledAnswer !== lastShown && !stream.isLoading ? polledAnswer : null;

  function send(event: FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || stream.isLoading) return;
    setDraft("");
    void stream.submit({ messages: [{ type: "human", content: text }] });
  }

  function choose(index: number, choice: Choice) {
    setChoices((current) => {
      const next = [...current];
      next[index] = choice;
      return next;
    });
  }

  function submitDecisions() {
    if (!decisions) return;
    setChoices([]);
    void stream.respond({ decisions });
  }

  return (
    <main className="shell">
      <header className="top">
        <h1>Innovox Workbench</h1>
        <div className="who">
          <span data-testid="user-name">{props.userName}</span>
          <button type="button" onClick={props.onNewTask}>New task</button>
          <form method="post" action="/api/auth/logout">
            <button type="submit">Sign out</button>
          </form>
        </div>
      </header>

      <section className="chat" aria-label="Conversation">
        <ol className="messages" data-testid="messages">
          {messages.map((m, i) => {
            const kind = kindOf(m);
            return (
              <li key={m.id ?? i} className={`msg ${kind}`} data-testid={`msg-${kind}`}>
                <span className="role">{kind === "human" ? "You" : "Agent"}</span>
                {textOf(m.content) && <p>{textOf(m.content)}</p>}
                {kind === "ai" && m.tool_calls?.length ? (
                  <p className="tools">
                    {m.tool_calls.map((call, n) => (
                      <code key={call.id ?? n}>{call.name}</code>
                    ))}
                  </p>
                ) : null}
              </li>
            );
          })}
          {backgroundAnswer ? (
            <li className="msg ai" data-testid="msg-background">
              <span className="role">Agent</span>
              <p>{backgroundAnswer}</p>
            </li>
          ) : null}
        </ol>

        {pending.length > 0 && (
          <div className="approval" role="alertdialog" aria-label="Approval needed" data-testid="approval">
            <h2>Approval needed</h2>
            {pending.map((review, i) => (
              <ActionReview key={i} index={i} review={review} choice={choices[i]} onChoose={(choice) => choose(i, choice)} />
            ))}
            <div className="buttons">
              <button
                type="button"
                className="primary"
                data-testid="submit-decisions"
                disabled={!decisions}
                onClick={submitDecisions}
              >
                {pending.length > 1 ? "Send decisions" : "Send decision"}
              </button>
            </div>
          </div>
        )}

        {stream.error ? (
          <p className="error" role="alert">
            Something went wrong. Start a new task, or sign in again if your session has expired.
          </p>
        ) : null}

        <form className="composer" onSubmit={send}>
          <label htmlFor="task">Task</label>
          <textarea
            id="task"
            data-testid="task-input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Describe the task for the agent"
            rows={3}
            disabled={pending.length > 0}
          />
          <div className="buttons">
            <button type="submit" className="primary" data-testid="send" disabled={stream.isLoading || pending.length > 0}>
              {stream.isLoading ? "Working…" : "Send"}
            </button>
            {stream.isLoading && (
              <button type="button" onClick={() => void stream.stop()}>
                Stop
              </button>
            )}
          </div>
        </form>
      </section>

      <aside className="side" aria-label="Agent activity">
        <section data-testid="plan">
          <h2>Plan</h2>
          {todos.length === 0 ? (
            <p className="muted">No plan yet.</p>
          ) : (
            <ul className="todos">
              {todos.map((todo, i) => (
                <li key={i} className={todo.status}>
                  <span aria-hidden="true">{todo.status === "completed" ? "✓" : todo.status === "in_progress" ? "▸" : "○"}</span>
                  {todo.content}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section data-testid="subagents">
          <h2>Subagents</h2>
          {subagents.length === 0 ? (
            <p className="muted">None running.</p>
          ) : (
            <ul>
              {subagents.map((s) => (
                <li key={s.id} className={s.status}>
                  <strong>{s.name}</strong> <span className="muted">{s.status}</span>
                  {s.taskInput ? <p>{s.taskInput}</p> : null}
                </li>
              ))}
            </ul>
          )}
        </section>

        <section data-testid="background-tasks">
          <h2>Background tasks</h2>
          {tasks.length === 0 ? (
            <p className="muted">None started.</p>
          ) : (
            <ul>
              {tasks.map((task) => (
                <li key={task.task_id} data-status={task.status}>
                  <strong>{task.agent_name}</strong> <span className="muted">{task.status}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section data-testid="files">
          <h2>Files</h2>
          {Object.keys(files).length === 0 ? (
            <p className="muted">No files yet.</p>
          ) : (
            <ul>
              {Object.keys(files).map((path) => (
                <li key={path}>
                  <button type="button" className="link" onClick={() => setOpenFile(openFile === path ? null : path)}>
                    {path}
                  </button>
                  {openFile === path && <pre>{fileText(files[path])}</pre>}
                </li>
              ))}
            </ul>
          )}
        </section>
      </aside>
    </main>
  );
}

/** One pending action with a decision of its own: approve, edit or reject, as its tool allows. */
function ActionReview(props: { index: number; review: Review; choice: Choice | undefined; onChoose: (choice: Choice) => void }) {
  const { index, review, choice, onChoose } = props;
  const original = JSON.stringify(review.action.args, null, 2);
  return (
    <div className="action" data-testid="action" data-decision={choice?.type ?? "none"}>
      <strong>{review.action.name}</strong>
      {review.action.description ? <p className="muted">{review.action.description}</p> : null}
      {choice?.type === "edit" ? (
        <label>
          Arguments (JSON)
          <textarea
            data-testid={`edit-args-${index}`}
            rows={6}
            value={choice.argsText}
            onChange={(e) => onChoose({ type: "edit", argsText: e.target.value })}
          />
        </label>
      ) : (
        <pre>{original}</pre>
      )}
      {choice?.type === "reject" ? (
        <label>
          Reason
          <input
            data-testid={`reject-reason-${index}`}
            value={choice.message}
            onChange={(e) => onChoose({ type: "reject", message: e.target.value })}
          />
        </label>
      ) : null}
      <div className="buttons" role="radiogroup" aria-label={`Decision for ${review.action.name}`}>
        {review.allowed.includes("approve") && (
          <button
            type="button"
            role="radio"
            aria-checked={choice?.type === "approve"}
            data-testid={`approve-${index}`}
            onClick={() => onChoose({ type: "approve" })}
          >
            Approve
          </button>
        )}
        {review.allowed.includes("edit") && (
          <button
            type="button"
            role="radio"
            aria-checked={choice?.type === "edit"}
            data-testid={`edit-${index}`}
            onClick={() => onChoose({ type: "edit", argsText: original })}
          >
            Edit
          </button>
        )}
        {review.allowed.includes("reject") && (
          <button
            type="button"
            role="radio"
            aria-checked={choice?.type === "reject"}
            data-testid={`reject-${index}`}
            onClick={() => onChoose({ type: "reject", message: "Rejected by the user" })}
          >
            Reject
          </button>
        )}
      </div>
    </div>
  );
}

function fileText(file: unknown): string {
  if (typeof file === "string") return file;
  const content = (file as { content?: unknown } | null)?.content;
  if (Array.isArray(content)) return content.join("\n");
  if (typeof content === "string") return content;
  return JSON.stringify(file, null, 2);
}
