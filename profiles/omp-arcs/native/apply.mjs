#!/usr/bin/env node
import { cpSync, readFileSync, writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { join, resolve } from "node:path";

const root = resolve(process.argv[2] || "");
if (!process.argv[2]) {
  console.error("Usage: node native/apply.mjs <oh-my-pi-checkout>");
  process.exit(2);
}
const expected = "7057eb9cdda91791fc4fbce4a60f33139bda3b8b";
const check = spawnSync("git", ["-C", root, "rev-parse", "HEAD"], { encoding: "utf8" });
if (check.error || check.status !== 0) {
  throw new Error(check.error?.message || check.stderr || "git rev-parse failed");
}
const actual = check.stdout.trim();
if (actual !== expected) {
  throw new Error("Expected OMP " + expected + ", got " + actual + "; refusing a fuzzy patch.");
}

const here = new URL(".", import.meta.url);

function edit(path, mutate) {
  const file = join(root, path);
  const before = readFileSync(file, "utf8");
  const after = mutate(before);
  if (after === before) throw new Error("No change made to " + path + "; upstream marker drifted.");
  writeFileSync(file, after);
}

function once(text, marker, replacement, label) {
  const first = text.indexOf(marker);
  if (first < 0 || text.indexOf(marker, first + 1) >= 0) {
    throw new Error("Expected exactly one marker for " + label);
  }
  return text.slice(0, first) + replacement + text.slice(first + marker.length);
}

edit("packages/coding-agent/src/advisor/settings.ts", text => {
  const marker = "export const cfgAdvisorSyncBacklog = register({";
  const insertion =
    "export const cfgAdvisorReviewMode = register({\n" +
    "\tid: \"advisor.reviewMode\",\n" +
    "\tprotocolDefault: [\"rpc\", \"acp\"],\n" +
    "\ttype: \"enum\",\n" +
    "\tvalues: [\"continuous\", \"periodic\"] as const,\n" +
    "\tdefault: \"continuous\",\n" +
    "\tui: {\n" +
    "\t\ttab: \"model\",\n" +
    "\t\tgroup: \"Advisor\",\n" +
    "\t\tlabel: \"Advisor Review Mode\",\n" +
    "\t\tdescription: \"Continuous reviews every primary update. Periodic uses the judge role as a cheap wake gate and starts semantic advisor review only when warranted.\",\n" +
    "\t\tcondition: \"advisorEnabled\",\n" +
    "\t},\n" +
    "});\n\n" +
    "export const cfgAdvisorPeriodicEveryTurns = register({\n" +
    "\tid: \"advisor.periodicEveryTurns\",\n" +
    "\tprotocolDefault: [\"rpc\", \"acp\"],\n" +
    "\ttype: \"number\",\n" +
    "\tdefault: 4,\n" +
    "\tui: {\n" +
    "\t\ttab: \"model\",\n" +
    "\t\tgroup: \"Advisor\",\n" +
    "\t\tlabel: \"Periodic Advisor Cadence\",\n" +
    "\t\tdescription: \"In periodic mode, ask the judge after this many primary turn boundaries. Terminal boundaries are always eligible.\",\n" +
    "\t\toptions: [{ value: \"2\", label: \"2 turns\" }, { value: \"4\", label: \"4 turns\", description: \"Default.\" }, { value: \"8\", label: \"8 turns\" }, { value: \"12\", label: \"12 turns\" }],\n" +
    "\t\tcondition: \"advisorEnabled\",\n" +
    "\t},\n" +
    "});\n\n" +
    "export const cfgAdvisorPeriodicWakeThreshold = register({\n" +
    "\tid: \"advisor.periodicWakeThreshold\",\n" +
    "\tprotocolDefault: [\"rpc\", \"acp\"],\n" +
    "\ttype: \"number\",\n" +
    "\tdefault: 0.65,\n" +
    "\tui: {\n" +
    "\t\ttab: \"model\",\n" +
    "\t\tgroup: \"Advisor\",\n" +
    "\t\tlabel: \"Periodic Advisor Wake Threshold\",\n" +
    "\t\tdescription: \"Minimum judge yes-probability from 0 to 1 required to wake the semantic advisor.\",\n" +
    "\t\tcondition: \"advisorEnabled\",\n" +
    "\t},\n" +
    "});\n\n" +
    "export const cfgAdvisorPeriodicRequireNativeJudge = register({\n" +
    "\tid: \"advisor.periodicRequireNativeJudge\",\n" +
    "\tprotocolDefault: [\"rpc\", \"acp\"],\n" +
    "\ttype: \"boolean\",\n" +
    "\tdefault: true,\n" +
    "\tui: {\n" +
    "\t\ttab: \"model\",\n" +
    "\t\tgroup: \"Advisor\",\n" +
    "\t\tlabel: \"Require Native Periodic Judge\",\n" +
    "\t\tdescription: \"Keep the high-frequency wake gate on a native System One judge instead of silently paying for a chat fallback.\",\n" +
    "\t\tcondition: \"advisorEnabled\",\n" +
    "\t},\n" +
    "});\n\n";
  return once(text, marker, insertion + marker, "advisor periodic settings");
});

cpSync(new URL("./periodic-gate.ts", here), join(root, "packages/coding-agent/src/advisor/periodic-gate.ts"));
cpSync(new URL("./periodic-gate.test.ts", here), join(root, "packages/coding-agent/test/advisor/periodic-gate.test.ts"));

edit("packages/coding-agent/src/session/session-advisors.ts", text => {
  text = once(
    text,
    "} from \"../advisor\";\n",
    "} from \"../advisor\";\n" +
      "import {\n" +
      "\tbuildPeriodicAdvisorGateState,\n" +
      "\tPERIODIC_ADVISOR_WAKE_QUESTION,\n" +
      "\tshouldRunPeriodicAdvisorGate,\n" +
      "\tshouldWakePeriodicAdvisor,\n" +
      "} from \"../advisor/periodic-gate\";\n" +
      "import { hasNativeJudge, journalJudgmentUsage, resolveJudge, sharedJudgmentCache } from \"../judgment\";\n",
    "native judge imports",
  );

  text = once(
    text,
    "\tcfgAdvisorEvictStaleResults,\n\tcfgAdvisorImmuneTurns,\n\tcfgAdvisorMaxNotesPerUpdate,\n\tcfgAdvisorSyncBacklog,\n",
    "\tcfgAdvisorEvictStaleResults,\n" +
      "\tcfgAdvisorImmuneTurns,\n" +
      "\tcfgAdvisorMaxNotesPerUpdate,\n" +
      "\tcfgAdvisorPeriodicEveryTurns,\n" +
      "\tcfgAdvisorPeriodicRequireNativeJudge,\n" +
      "\tcfgAdvisorPeriodicWakeThreshold,\n" +
      "\tcfgAdvisorReviewMode,\n" +
      "\tcfgAdvisorSyncBacklog,\n",
    "advisor settings imports",
  );

  text = once(
    text,
    "\t#advisorInterruptImmuneTurnStart: number | undefined;\n\t#pendingAdvisorCardEvents",
    "\t#advisorInterruptImmuneTurnStart: number | undefined;\n" +
      "\t#periodicAdvisorTurnsSinceGate = 0;\n" +
      "\t#periodicAdvisorGateInFlight = false;\n" +
      "\t#periodicAdvisorEpoch = 0;\n" +
      "\t#periodicAdvisorMissingJudgeWarned = false;\n" +
      "\t#pendingAdvisorCardEvents",
    "periodic state fields",
  );

  const opening =
    "\t\tconst terminalBoundary = willContinue !== true;\n" +
    "\t\tif (terminalBoundary) this.#terminalUnwindActive = true;\n" +
    "\t\ttry {\n" +
    "\t\t\tthis.#retuneAutoThinkingAdvisors();\n" +
    "\t\t\tthis.#advisorPrimaryTurnsCompleted++;\n";

  const replacement =
    "\t\tconst terminalBoundary = willContinue !== true;\n" +
    "\t\tif (terminalBoundary) this.#terminalUnwindActive = true;\n" +
    "\t\tif (cfgAdvisorReviewMode.get(this.#host.settings) === \"periodic\") {\n" +
    "\t\t\tthis.#advisorPrimaryTurnsCompleted++;\n" +
    "\t\t\tif (terminalBoundary) {\n" +
    "\t\t\t\tfor (const advisor of this.#advisors) advisor.adviseTool.flushDeferredNotes();\n" +
    "\t\t\t}\n" +
    "\t\t\tthis.#schedulePeriodicAdvisorReview(messages, willContinue);\n" +
    "\t\t\treturn;\n" +
    "\t\t}\n" +
    "\t\ttry {\n" +
    "\t\t\tthis.#retuneAutoThinkingAdvisors();\n" +
    "\t\t\tthis.#advisorPrimaryTurnsCompleted++;\n";
  text = once(text, opening, replacement, "periodic onPrimaryTurnEnd branch");

  const methodMarker = "\n\t/** Rebuilds live advisors when role assignments alter their resolved runtime inputs. */";
  const methods =
    "\n\t#schedulePeriodicAdvisorReview(messages: AgentMessage[], willContinue: boolean | undefined): void {\n" +
    "\t\tif (this.#advisors.length === 0) return;\n" +
    "\t\tthis.#periodicAdvisorTurnsSinceGate++;\n" +
    "\t\tconst terminalBoundary = willContinue !== true;\n" +
    "\t\tconst turnsSinceGate = this.#periodicAdvisorTurnsSinceGate;\n" +
    "\t\tconst everyTurns = cfgAdvisorPeriodicEveryTurns.get(this.#host.settings);\n" +
    "\t\tif (!shouldRunPeriodicAdvisorGate({ turnsSinceGate, everyTurns, terminalBoundary, inFlight: this.#periodicAdvisorGateInFlight })) return;\n" +
    "\t\tthis.#periodicAdvisorTurnsSinceGate = 0;\n" +
    "\t\tthis.#periodicAdvisorGateInFlight = true;\n" +
    "\t\tconst epoch = this.#periodicAdvisorEpoch;\n" +
    "\t\tconst snapshot = messages.slice();\n" +
    "\t\tconst snapshotCount = snapshot.length;\n" +
    "\t\tvoid this.#runPeriodicAdvisorGate(snapshot, snapshotCount, willContinue, epoch, turnsSinceGate).finally(() => {\n" +
    "\t\t\tif (epoch === this.#periodicAdvisorEpoch) this.#periodicAdvisorGateInFlight = false;\n" +
    "\t\t});\n" +
    "\t}\n" +
    "\n" +
    "\tasync #runPeriodicAdvisorGate(messages: AgentMessage[], snapshotCount: number, willContinue: boolean | undefined, epoch: number, turnsSinceGate: number): Promise<void> {\n" +
    "\t\ttry {\n" +
    "\t\t\tif (cfgAdvisorPeriodicRequireNativeJudge.get(this.#host.settings) && !hasNativeJudge(this.#host.settings, this.#host.modelRegistry)) {\n" +
    "\t\t\t\tif (!this.#periodicAdvisorMissingJudgeWarned) {\n" +
    "\t\t\t\t\tthis.#periodicAdvisorMissingJudgeWarned = true;\n" +
    "\t\t\t\t\tthis.#host.emitNotice(\"warning\", \"Periodic advisor skipped: judge is not a native System One model. Configure modelRoles.judge or disable advisor.periodicRequireNativeJudge.\", \"advisor\");\n" +
    "\t\t\t\t}\n" +
    "\t\t\t\treturn;\n" +
    "\t\t\t}\n" +
    "\t\t\tconst judge = resolveJudge({ settings: this.#host.settings, registry: this.#host.modelRegistry, sessionId: this.#host.sessionId(), purpose: \"advisor-periodic-gate\", onUsage: journalJudgmentUsage(this.#host.sessionManager), cache: sharedJudgmentCache() });\n" +
    "\t\t\tconst state = buildPeriodicAdvisorGateState(messages, willContinue !== true, turnsSinceGate, text => this.#host.obfuscator()?.obfuscate(text) ?? text);\n" +
    "\t\t\tconst { answers } = await judge.judge({ state, questions: { wake: PERIODIC_ADVISOR_WAKE_QUESTION } });\n" +
    "\t\t\tif (epoch !== this.#periodicAdvisorEpoch || !this.#advisorEnabled || this.#host.isDisposed()) return;\n" +
    "\t\t\tconst live = this.#host.agent.state.messages;\n" +
    "\t\t\tif (live.length < snapshotCount || live.slice(snapshotCount).some(message => message.role === \"user\")) return;\n" +
    "\t\t\tif (!shouldWakePeriodicAdvisor(answers.wake, cfgAdvisorPeriodicWakeThreshold.get(this.#host.settings))) return;\n" +
    "\t\t\tthis.#retuneAutoThinkingAdvisors();\n" +
    "\t\t\tfor (const advisor of this.#advisors) {\n" +
    "\t\t\t\tif (advisor.runtime.disposed) continue;\n" +
    "\t\t\t\ttry { advisor.runtime.onTurnEnd(messages, { willContinue }); }\n" +
    "\t\t\t\tcatch (error) { logger.warn(\"periodic advisor onTurnEnd threw; delta dropped\", { advisor: advisor.name, err: String(error) }); }\n" +
    "\t\t\t}\n" +
    "\t\t} catch (error) {\n" +
    "\t\t\tlogger.debug(\"periodic advisor gate failed open\", { error: error instanceof Error ? error.message : String(error) });\n" +
    "\t\t}\n" +
    "\t}\n";
  text = once(text, methodMarker, methods + methodMarker, "periodic gate methods");

  text = once(
    text,
    "\tstopRuntime(): void {\n\t\tthis.#stopAdvisorRuntime();\n\t}",
    "\tstopRuntime(): void {\n\t\tthis.#periodicAdvisorEpoch++;\n\t\tthis.#periodicAdvisorTurnsSinceGate = 0;\n\t\tthis.#periodicAdvisorGateInFlight = false;\n\t\tthis.#stopAdvisorRuntime();\n\t}",
    "stopRuntime invalidation",
  );

  text = once(
    text,
    "\tresetSessionState(options: { preserveCost?: boolean } = {}): void {\n\t\tthis.#resetAdvisorSessionState(options.preserveCost === true);\n\t}",
    "\tresetSessionState(options: { preserveCost?: boolean } = {}): void {\n\t\tthis.#periodicAdvisorEpoch++;\n\t\tthis.#periodicAdvisorTurnsSinceGate = 0;\n\t\tthis.#periodicAdvisorGateInFlight = false;\n\t\tthis.#periodicAdvisorMissingJudgeWarned = false;\n\t\tthis.#resetAdvisorSessionState(options.preserveCost === true);\n\t}",
    "resetSessionState invalidation",
  );

  text = once(
    text,
    "\tresetAllRuntimes(reason?: string): void {\n\t\tthis.#resetAllAdvisorRuntimes(reason);\n\t}",
    "\tresetAllRuntimes(reason?: string): void {\n\t\tthis.#periodicAdvisorEpoch++;\n\t\tthis.#periodicAdvisorTurnsSinceGate = 0;\n\t\tthis.#periodicAdvisorGateInFlight = false;\n\t\tthis.#resetAllAdvisorRuntimes(reason);\n\t}",
    "resetAllRuntimes invalidation",
  );

  return text;
});

console.log("Applied native periodic advisor patch to " + root);
