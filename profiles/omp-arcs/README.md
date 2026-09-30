# OMP Arcs-style native periodic advisor pilot

This directory now stages the OMP-core version of the Arcs idea rather than
running a parallel supervisor beside OMP. It is being proven in ai-config-registry
only because there is not currently a writable MooseGooseConsulting/oh-my-pi fork
available to this integration. The intended permanent home is an OMP fork, or
upstream if accepted, not this registry.

## Architecture

Primary execution feeds a periodic eligibility gate. The gate uses OMP's native
judge role for one typed wake probability. A low-probability result sleeps. A
wake sends the accumulated primary transcript delta to the existing native OMP
Advisor. WATCHDOG discovery, advisor transcript state, provider fallback, usage
accounting, output quarantine, emission guard, and nit/concern/blocker delivery
remain OMP's existing implementation.

This removes the previous custom chat-model sentry and custom guardian runtime.

## New native settings

The staged patch adds:

- advisor.reviewMode: continuous or periodic. Default remains continuous.
- advisor.periodicEveryTurns: default 4.
- advisor.periodicWakeThreshold: default 0.65.
- advisor.periodicRequireNativeJudge: default true.

Periodic mode does not await the judge on the primary execution path. Gate errors
fail open. A result is discarded after a session epoch change or when a new user
message arrives after the judged snapshot. A terminal boundary is always eligible.

A native judge is required by default so high-frequency supervision does not
silently fall through to a prompted chat model. Configure modelRoles.judge to a
native System One model such as TypeSafe JEV, or deliberately turn the requirement
off.

The semantic review still uses native Advisor delivery policy. A native Advisor
concern or blocker can therefore use OMP's existing interrupting delivery semantics.
This patch changes when the Advisor runs, not what an admitted Advisor note means.

## Suggested routing

See recommended-config.yml. The current allocation hypothesis is:

- judge: TypeSafe JEV / native System One.
- advisor: GPT-6 Astra medium for rare semantic escalation.
- smol: MiMo V2.6 Flash low for broad investigation and mechanical work.
- task: DeepSeek V4.1 Flash high for ordinary delegated implementation.
- arcs-reviewer: @advisor as an explicitly requested fresh artifact reviewer.

These are routing hypotheses to evaluate, not benchmark claims.

The profile still contributes arcs-scout, arcs-worker, and arcs-reviewer, but they
route through ordinary OMP roles. There is no subagent-spawn model override and no
second agent registry.

## Apply to a pinned OMP checkout

~~~sh
node profiles/omp-arcs/bootstrap.mjs /tmp/omp-arcs-source
node profiles/omp-arcs/native/apply.mjs /tmp/omp-arcs-source/omp
cd /tmp/omp-arcs-source/omp
bun install --frozen-lockfile
bun test packages/coding-agent/test/advisor/periodic-gate.test.ts
bun --cwd=packages/coding-agent run check:types
~~~

The apply script refuses any OMP revision except the pin in upstream.json. CI
performs those exact steps and uploads the resulting git diff as a transplantable
artifact. That patch is the artifact to commit into a future OMP fork.

## Deliberately unchanged

This does not alter AGENTS.md, product goals, specs, project documentation, Goal
mode, task, Vibe, eval/workpool, TTSR, reviewer, security-reviewer, credentials,
or user-level configuration. Continuous Advisor behavior is untouched unless the
new review mode is explicitly set to periodic.

This is not full Arcs parity. It gates primary turn boundaries rather than
stitching every child event into a single master trajectory, and it does not yet
attach measured intervention-outcome labels.

architecture.json is editable Archify JSON IR. CI renders it with the pinned real
Archify checkout and requires showcase validation and browser checks.
