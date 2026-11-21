// Human-in-the-loop decisions for LangChain's HumanInTheLoopMiddleware in its default "batched" mode: one interrupt
// per model turn, whose value lists every gated tool call (`action_requests`) and the decisions each tool allows
// (`review_configs`). The resume value is `{ decisions }`, one per action request and in the same order.

export type DecisionType = "approve" | "edit" | "reject" | "respond";
export type ActionRequest = { name: string; args: Record<string, unknown>; description?: string };
export type Decision =
  | { type: "approve" }
  | { type: "reject"; message: string }
  | { type: "edit"; edited_action: { name: string; args: Record<string, unknown> } };

/** What the user has chosen for one action. An edit carries the arguments as the JSON text the user typed. */
export type Choice = { type: "approve" } | { type: "reject"; message: string } | { type: "edit"; argsText: string };

/** One action to review and the decisions the workbench offers for it. */
export type Review = { action: ActionRequest; allowed: DecisionType[] };

// The workbench offers approve, edit and reject. "respond" (answering in place of the tool) is not offered.
const OFFERED: DecisionType[] = ["approve", "edit", "reject"];

type ReviewConfig = { action_name?: string; allowed_decisions?: DecisionType[] };

export function reviewsOf(interrupt: unknown): Review[] {
  const value = (interrupt as { value?: Record<string, unknown> } | undefined)?.value;
  const actions = (value?.action_requests ?? value?.actionRequests) as ActionRequest[] | undefined;
  const configs = (value?.review_configs ?? value?.reviewConfigs) as ReviewConfig[] | undefined;
  if (!Array.isArray(actions)) return [];
  return actions.map((action) => {
    const config = Array.isArray(configs) ? configs.find((c) => c.action_name === action.name) : undefined;
    // Without a review config for the tool, offer only approve and reject.
    const allowed = config?.allowed_decisions ?? ["approve", "reject"];
    return { action, allowed: OFFERED.filter((d) => allowed.includes(d)) };
  });
}

function editedArgs(text: string): Record<string, unknown> | null {
  try {
    const parsed: unknown = JSON.parse(text);
    return parsed !== null && typeof parsed === "object" && !Array.isArray(parsed) ? (parsed as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

/** The decisions to send, in request order, or null while any action lacks a valid, allowed decision. */
export function decisionsFor(reviews: Review[], choices: (Choice | undefined)[]): Decision[] | null {
  const decisions: Decision[] = [];
  for (const [i, review] of reviews.entries()) {
    const choice = choices[i];
    if (!choice || !review.allowed.includes(choice.type)) return null;
    if (choice.type === "edit") {
      const args = editedArgs(choice.argsText);
      if (!args) return null;
      decisions.push({ type: "edit", edited_action: { name: review.action.name, args } });
    } else {
      decisions.push(choice);
    }
  }
  return decisions;
}
