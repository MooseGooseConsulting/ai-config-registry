import type { AgentMessage } from "@oh-my-pi/pi-agent-core";
import type { NoulAnswer, NoulQuestion } from "@oh-my-pi/pi-ai";

const OWNER_CHARS = 3_000;
const RECENT_CHARS = 10_000;
const RECENT_MESSAGES = 20;
const PER_MESSAGE_CHARS = 2_000;

export const PERIODIC_ADVISOR_WAKE_QUESTION: NoulQuestion = {
  type: "noul",
  instructions:
    "Does this recent coding trajectory warrant a deeper independent advisor review right now?",
  criteria: {
    true:
      "Clear evidence of material drift from the owner's request, repeated failure without a changed hypothesis, an unsupported success or completion claim, or a consequential choice that merits semantic review.",
    false:
      "Ordinary useful progress, normal exploration, a corrected issue, minor style or nits, or insufficient evidence of a material trajectory problem.",
  },
};

function bound(text: string, max: number): { text: string; truncated: boolean } {
  if (text.length <= max) return { text, truncated: false };
  return { text: text.slice(0, max) + "\n...[truncated]", truncated: true };
}

function safeJson(value: unknown): string {
  try {
    return JSON.stringify(value);
  } catch {
    return "[unserializable]";
  }
}

function projectMessage(message: AgentMessage): { text: string; truncated: boolean } {
  const raw = message as unknown as Record<string, unknown>;
  const role = typeof raw.role === "string" ? raw.role : "unknown";
  const content = raw.content;
  let body = "";

  if (typeof content === "string") {
    body = content;
  } else if (Array.isArray(content)) {
    const parts: string[] = [];
    for (const item of content) {
      if (!item || typeof item !== "object") {
        parts.push(String(item));
        continue;
      }
      const block = item as Record<string, unknown>;
      if (block.type === "text" && typeof block.text === "string") {
        parts.push(block.text);
      } else if (block.type === "toolCall") {
        parts.push(
          "tool_call " +
            String(block.name ?? "unknown") +
            " " +
            safeJson(block.arguments ?? {}),
        );
      } else if (block.type === "image") {
        parts.push("[image]");
      } else {
        parts.push(safeJson(block));
      }
    }
    body = parts.join("\n");
  } else if (content !== undefined) {
    body = safeJson(content);
  } else {
    body = safeJson(raw);
  }

  const projected = bound(role + ": " + body, PER_MESSAGE_CHARS);
  return projected;
}

function renderMessages(
  messages: readonly AgentMessage[],
  transform: (text: string) => string,
): { text: string; truncated: boolean } {
  const parts: string[] = [];
  let truncated = false;
  for (const message of messages) {
    const projected = projectMessage(message);
    truncated ||= projected.truncated;
    parts.push(transform(projected.text));
  }
  return { text: parts.join("\n\n"), truncated };
}

export interface PeriodicAdvisorGateState {
  ownerRequests: string;
  recentActivity: string;
  partial: boolean;
  terminalBoundary: boolean;
  turnsSinceGate: number;
}

export function buildPeriodicAdvisorGateState(
  messages: readonly AgentMessage[],
  terminalBoundary: boolean,
  turnsSinceGate: number,
  transform: (text: string) => string = text => text,
): PeriodicAdvisorGateState {
  const userMessages = messages.filter(message => message.role === "user");
  const ownerMessages =
    userMessages.length <= 3
      ? userMessages
      : [userMessages[0], ...userMessages.slice(-2)];

  const ownerRendered = renderMessages(ownerMessages, transform);
  const recentRendered = renderMessages(messages.slice(-RECENT_MESSAGES), transform);
  const owner = bound(ownerRendered.text, OWNER_CHARS);
  const recent = bound(recentRendered.text, RECENT_CHARS);

  return {
    ownerRequests: owner.text,
    recentActivity: recent.text,
    partial:
      owner.truncated ||
      recent.truncated ||
      ownerRendered.truncated ||
      recentRendered.truncated ||
      userMessages.length > 3 ||
      messages.length > RECENT_MESSAGES,
    terminalBoundary,
    turnsSinceGate,
  };
}

export function shouldRunPeriodicAdvisorGate(args: {
  turnsSinceGate: number;
  everyTurns: number;
  terminalBoundary: boolean;
  inFlight: boolean;
}): boolean {
  if (args.inFlight) return false;
  const every = Math.max(1, Math.trunc(args.everyTurns));
  return args.terminalBoundary || args.turnsSinceGate >= every;
}

export function shouldWakePeriodicAdvisor(
  answer: NoulAnswer,
  threshold: number,
): boolean {
  const bounded = Math.min(1, Math.max(0, threshold));
  return answer.noul >= bounded;
}
