// Which conversation messages the user typed. A background (async subagent) task reports back with a human message
// that Deep Agents marks with LangChain's notification metadata; it is not shown as the user's. The text of a
// message is never used to decide this, so a user who writes about notifications still sees their own message.

import { type BaseMessage, getNotificationMetadata } from "@langchain/core/messages";

export type MessageLike = { content: unknown; additional_kwargs?: Record<string, unknown> };

export function isNotification(message: MessageLike): boolean {
  const kwargs = message.additional_kwargs ?? {};
  // `getNotificationMetadata` reads only `additional_kwargs`; the older Deep Agents key is still written alongside.
  return (
    getNotificationMetadata({ additional_kwargs: kwargs } as unknown as BaseMessage) !== undefined ||
    Boolean(kwargs.deepagents_notification)
  );
}
