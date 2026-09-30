import type { AgentMessage } from "@oh-my-pi/pi-agent-core";
import type { NoulAnswer, NoulQuestion } from "@oh-my-pi/pi-ai";
import { formatSessionHistoryMarkdown } from "../session/session-history-format";

const OWNER_CHARS = 3_000;
const RECENT_CHARS = 10_000;
const RECENT_MESSAGES = 20;

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

function tail(text: string, max: number): { text: string; truncated: boolean } {
  if (text.length <= max) return { text, truncated: false };
  return { text: text.slice(text.length - max), truncated: true };
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
): PeriodicAdvisorGateState {
  const userMessages = messages.filter(message => message.role === "user");
  const ownerMessages =
    userMessages.length <= 3
      ? userMessages
      : [userMessages[0], ...userMessages.slice(-2)];
  const owner = tail(formatSessionHistoryMarkdown(ownerMessages), OWNER_CHARS);
  const recent = tail(
    formatSessionHistoryMarkdown(messages.slice(-RECENT_MESSAGES)),
    RECENT_CHARS,
  );
  return {
    ownerRequests: owner.text,
    recentActivity: recent.text,
    partial:
      owner.truncated ||
      recent.truncated ||
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
