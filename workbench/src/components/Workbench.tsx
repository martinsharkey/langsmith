"use client";

// The workbench screen. All streaming, interrupt and subagent behaviour comes from LangChain's frontend SDK
// (`useStream`); this component only renders it. The browser never sees a token: requests go to /api/agent.

import { useStream } from "@langchain/react";
import { type FormEvent, useEffect, useMemo, useState } from "react";

type Todo = { content: string; status: "pending" | "in_progress" | "completed" };
type ActionRequest = { name: string; args: Record<string, unknown>; description?: string };
type Decision = { type: "approve" } | { type: "reject"; message: string };
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

// A background task reports back with a message Deep Agents labels as a notification; it is not something the
// user typed, so it is not shown as one.
function isNotification(message: AnyMessage): boolean {
  return Boolean(message.additional_kwargs?.deepagents_notification);
}

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

function actionRequests(interrupt: unknown): ActionRequest[] {
  const value = (interrupt as { value?: Record<string, unknown> } | undefined)?.value;
  const list = (value?.actionRequests ?? value?.action_requests) as ActionRequest[] | undefined;
  return Array.isArray(list) ? list : [];
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
  const [rejectReason, setRejectReason] = useState("");
  const [openFile, setOpenFile] = useState<string | null>(null);

  const values = (stream.values ?? {}) as {
    todos?: Todo[];
    files?: Record<string, unknown>;
    async_tasks?: Record<string, AsyncTask>;
  };
  // A background task finishes after the run that started it, so its status is read from the thread while any
  // task is still open.
  const [polledTasks, setPolledTasks] = useState<Record<string, AsyncTask> | null>(null);
  const [polledAnswer, setPolledAnswer] = useState<string | null>(null);
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
  const pending = actionRequests(stream.interrupt);
  const messages = (stream.messages as unknown as AnyMessage[]).filter((m) => {
    const kind = kindOf(m);
    if (kind === "human") return !isNotification(m);
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

  function decide(decision: Decision) {
    const decisions = pending.map(() => decision);
    setRejectReason("");
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
            {pending.map((action, i) => (
              <div key={i} className="action">
                <strong>{action.name}</strong>
                <pre>{JSON.stringify(action.args, null, 2)}</pre>
              </div>
            ))}
            <label>
              Reason, if rejecting
              <input value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} />
            </label>
            <div className="buttons">
              <button type="button" className="primary" data-testid="approve" onClick={() => decide({ type: "approve" })}>
                Approve
              </button>
              <button
                type="button"
                data-testid="reject"
                onClick={() => decide({ type: "reject", message: rejectReason || "Rejected by the user" })}
              >
                Reject
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

function fileText(file: unknown): string {
  if (typeof file === "string") return file;
  const content = (file as { content?: unknown } | null)?.content;
  if (Array.isArray(content)) return content.join("\n");
  if (typeof content === "string") return content;
  return JSON.stringify(file, null, 2);
}
