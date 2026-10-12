import { describe, expect, it } from "bun:test";
import type { AgentMessage } from "@oh-my-pi/pi-agent-core";
import {
  buildPeriodicAdvisorGateState,
  shouldRunPeriodicAdvisorGate,
  shouldWakePeriodicAdvisor,
} from "../../src/advisor/periodic-gate";

const user = (text: string): AgentMessage =>
  ({ role: "user", content: text, timestamp: 1 } as unknown as AgentMessage);
const assistant = (text: string): AgentMessage =>
  ({
    role: "assistant",
    content: [{ type: "text", text }],
    timestamp: 2,
  } as unknown as AgentMessage);

describe("periodic advisor gate", () => {
  it("runs on cadence or terminal boundary, never with another gate in flight", () => {
    expect(shouldRunPeriodicAdvisorGate({ turnsSinceGate: 3, everyTurns: 4, terminalBoundary: false, inFlight: false })).toBe(false);
    expect(shouldRunPeriodicAdvisorGate({ turnsSinceGate: 4, everyTurns: 4, terminalBoundary: false, inFlight: false })).toBe(true);
    expect(shouldRunPeriodicAdvisorGate({ turnsSinceGate: 1, everyTurns: 4, terminalBoundary: true, inFlight: false })).toBe(true);
    expect(shouldRunPeriodicAdvisorGate({ turnsSinceGate: 99, everyTurns: 4, terminalBoundary: true, inFlight: true })).toBe(false);
  });

  it("uses the noul probability as the explicit wake threshold", () => {
    expect(shouldWakePeriodicAdvisor({ type: "noul", noul: 0.649 }, 0.65)).toBe(false);
    expect(shouldWakePeriodicAdvisor({ type: "noul", noul: 0.65 }, 0.65)).toBe(true);
  });

  it("preserves the first and latest owner requests and marks bounded views partial", () => {
    const messages: AgentMessage[] = [
      user("Original outcome"),
      ...Array.from({ length: 25 }, (_, i) => assistant("step " + i)),
      user("Second request"),
      user("Do not widen scope"),
    ];
    const state = buildPeriodicAdvisorGateState(messages, false, 4);
    expect(state.ownerRequests).toContain("Original outcome");
    expect(state.ownerRequests).toContain("Do not widen scope");
    expect(state.partial).toBe(true);
    expect(state.turnsSinceGate).toBe(4);
  });

  it("keeps the newest activity when the aggregate recent window is truncated", () => {
    const messages = Array.from({ length: 20 }, (_, i) => assistant(`${i}: ${"x".repeat(700)}`));
    messages[messages.length - 1] = assistant("LATEST_TURN_EVIDENCE");

    const state = buildPeriodicAdvisorGateState(messages, false, 4);

    expect(state.recentActivity).toContain("...[older content omitted; newest content follows]");
    expect(state.recentActivity).toContain("LATEST_TURN_EVIDENCE");
    expect(state.partial).toBe(true);
  });

  it("keeps the end of an oversized message with a clear truncation marker", () => {
    const state = buildPeriodicAdvisorGateState(
      [assistant(`OLDEST_ONLY_SENTINEL ${"old detail ".repeat(400)}LATEST_MESSAGE_EVIDENCE`)],
      false,
      1,
    );

    expect(state.recentActivity).toContain("...[older content omitted; newest content follows]");
    expect(state.recentActivity).toContain("LATEST_MESSAGE_EVIDENCE");
    expect(state.recentActivity).not.toContain("OLDEST_ONLY_SENTINEL");
    expect(state.partial).toBe(true);
  });
});

