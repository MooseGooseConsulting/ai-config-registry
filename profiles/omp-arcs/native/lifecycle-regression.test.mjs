import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const sourcePath = process.env.OMP_SESSION_ADVISORS_SOURCE;
if (!sourcePath) throw new Error("Set OMP_SESSION_ADVISORS_SOURCE to the patched session-advisors.ts path");

function extractMethodBody(source) {
  const signature = "async onPrimaryTurnEnd(";
  const start = source.indexOf(signature);
  assert.notEqual(start, -1, "onPrimaryTurnEnd exists");
  const bodyStart = source.indexOf("): Promise<void> {", start);
  assert.notEqual(bodyStart, -1, "onPrimaryTurnEnd signature is unchanged");
  const open = source.indexOf("{", bodyStart);
  let depth = 0;
  for (let i = open; i < source.length; i++) {
    if (source[i] === "{") depth++;
    if (source[i] === "}" && --depth === 0) return source.slice(open, i + 1);
  }
  throw new Error("Could not find the end of onPrimaryTurnEnd");
}

test("periodic onPrimaryTurnEnd still clears a prior terminal unwind on a continuing boundary", async () => {
  const source = readFileSync(sourcePath, "utf8");
  const body = extractMethodBody(source).replaceAll(/this\.#([A-Za-z0-9_]+)/g, "this.$1");
  const makeMethod = new Function(
    "cfgAdvisorReviewMode",
    `return async function onPrimaryTurnEnd(messages, willContinue, signal) ${body}`,
  );
  const scheduled = [];
  const subject = {
    terminalUnwindActive: false,
    advisorPrimaryTurnsCompleted: 0,
    advisors: [],
    host: { settings: {} },
    retuneAutoThinkingAdvisors() { throw new Error("periodic mode must not retune advisors"); },
    schedulePeriodicAdvisorReview(messages, willContinue) { scheduled.push(willContinue); },
  };
  const onPrimaryTurnEnd = makeMethod({ get: () => "periodic" });

  await onPrimaryTurnEnd.call(subject, [], undefined);
  assert.equal(subject.terminalUnwindActive, true, "terminal boundary holds the unwind guard");
  await onPrimaryTurnEnd.call(subject, [], true);

  assert.equal(subject.terminalUnwindActive, false, "continuing boundary clears the previous guard in finally");
  assert.deepEqual(scheduled, [undefined, true]);
  assert.equal(subject.advisorPrimaryTurnsCompleted, 2);
});
