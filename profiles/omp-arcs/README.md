# OMP Arcs-style pilot

Periodic supervisory check-ins around an autonomous Oh My Pi worker, plus explicit
routing for three useful specialist agents. This is an OMP extension, not an OMP
fork, not an OpenCode plugin, and not a claim to implement the whole Arcs design.

## What this changes

- Adds `arcs-scout`, `arcs-worker`, and `arcs-reviewer` to OMP's agent catalog.
- Adds `/arcs on|off|status|check`. Loading the package alone spends no reviewer tokens.
- Once enabled, checks after **12 tool results or 90 seconds with new activity**,
  with a 20-second minimum interval and one review pipeline in flight.
- Runs a cheap sentry first. Only an evidence-backed `wake` invokes the guardian.
- Appends ready advice to an ordinary tool result at a later boundary. It does not
  interrupt, ask permission, delay the worker for inference, restart an idle worker,
  change task acceptance, or execute tools through the sentry/guardian.
- Leaves the primary model, existing agents, `AGENTS.md`, goals, credentials,
  Supabase automation, and user-level configuration unchanged.

These cadence values are proposed pilot defaults, not measured optimal values or
claims about community practice. A final-turn check is asynchronous and observational;
late findings appear in the UI but do not reopen completed work.

## Model allocation

`policy.json` is the complete routing policy for this package. Its `roles` are
**extension-owned configuration**, not undocumented native OMP settings.

| Work | First choice | Availability fallback | Reason for this allocation |
|---|---|---|---|
| Code investigation / scout | MiMo V2.6 Flash, low | DeepSeek V4.1 Flash, low | Give broad evidence gathering to a separate economical role. |
| Implementation / worker | DeepSeek V4.1 Flash, high | MiMo V2.6 Pro, high | Use Patrick's preferred everyday coding model rather than inheriting an expensive main model. |
| Requested independent review | GPT-6 Astra, medium | None | Reserve a different model family for occasional critical judgment; no xhigh. |
| Periodic sentry | DeepSeek V4.1 Flash, low | MiMo V2.6 Flash, low | A narrow sleep/wake judgment, not a second implementation agent. |
| Escalated guardian | GPT-6 Astra, medium | None | Spend stronger review effort only on the sentry's nominated concern. |

This is a workload-allocation hypothesis based on the requested preferences, not a
new benchmark ranking. GLM Flash is deliberately not the default goal-alignment
critic. The existing main driver is not replaced; neither Muse nor every other
subscription is forced into a role merely because it is available.

The resolver searches **only authenticated models in the current OMP catalog**.
It recognizes exact IDs (including vendor-prefixed IDs), with a documented provider
preference list. Native `deepseek-flash` is an allowed rolling alias; the inspected
catalog maps it to V4.1 Flash, but explicit version IDs are tried first. `/arcs status`
prints each resolved provider/model/effort. Pin a full `provider/model` in `ids` to
choose a route exactly. Unavailable guardian models disable activation; they never
silently become the primary. A missing named-worker route rejects that one spawn,
not the main session. Provider errors are not used to silently choose another model.
The independent context is guaranteed; independent model-family diversity relative
to an arbitrary main driver is not (the main driver could itself be Astra).

## Start without changing your installed configuration

From your working project, using OMP **18.4.4** (source pin in `upstream.json`):

```sh
omp -e /absolute/path/to/ai-config-registry/profiles/omp-arcs
```

The directory is an OMP extension package: its manifest loads `index.ts`; OMP's
sibling-capability discovery finds `agents/`. This does not copy files into your
home configuration. In the session:

```text
/arcs status
/advisor off
/arcs on
```

`/advisor off` is only to avoid paying for native continuous review alongside this
periodic pilot. This package does **not** turn the native advisor off for you. Once
you enable Arcs, it runs autonomously; there are no per-check approval prompts.
`/arcs off` immediately cancels its reviews and clears pending advice.

Use the specialists naturally through OMP's task tool, for example:

```text
Use arcs-scout to establish the relevant contracts and source locations, then
arcs-worker for the implementation slices that benefit from delegation.
Use arcs-reviewer to independently compare the resulting diff to the actual task.
```

The three names always use this package's policy; other agent names retain normal
OMP routing. The supervisor is not a peer agent, and is never dispatched via `task`.
No feature spec, task DAG, or approval ceremony is imposed by this extension.

For a local policy without editing the package, set `OMP_ARCS_POLICY` to an absolute
path to a complete copy of `policy.json`. Restart OMP after changing the policy.
This environment variable contains a path, not credentials. Credentials remain in
OMP's existing auth storage. No provider keys belong in the package.

## Source checkout and diagram

```sh
node profiles/omp-arcs/bootstrap.mjs /path/to/source-checkouts
```

This clones OMP and Archify at the exact inspected revisions. Existing dirty or
wrong-origin directories are left alone. It does not install a new global `omp`
binary, migrate credentials, or overwrite a user profile.

The editable Archify source is [architecture.json](architecture.json). Render with
that checkout (Node 18+, dependency install uses Archify's committed lockfile):

```sh
npm ci --prefix /path/to/source-checkouts/archify/archify
node /path/to/source-checkouts/archify/archify/bin/archify.mjs finalize architecture \
  profiles/omp-arcs/architecture.json profiles/omp-arcs/build/omp-arcs.html \
  --quality showcase --json
```

The PR workflow renders the same artifact and uploads its HTML and validation
receipts. A nonzero Archify result is a failure, not a successful diagram delivery.
The drawing describes this pilot, not an already deployed fleet.

## The actual boundaries

The sentry receives bounded excerpts of primary tool arguments/results, the original
intent anchor and two recent owner inputs. The guardian gets the same evidence plus
the sentry's claim. Both use separate native SDK sessions, inherited model-registry
credentials, and **no tools**, with ambient extensions/MCP/LSP disabled. This preserves
OMP's provider request pipeline; it is not a custom unauthenticated HTTP client.
It does not promise to inherit every live parent sampling/service-tier override.
The configured providers receive this context, potentially across two vendors.

Each advice item carries an intent epoch, event watermark, and creation time. It is
dropped after 60 seconds, 24 newer events, changed owner intent, a session transition,
or a duplicate/cooldown collision. Compaction invalidates old evidence but retains
the bounded intent anchor. Branch/switch resets the anchor to avoid importing the
wrong branch's intent. Interactive input is observed directly; some hosts expose
only the prepared prompt, and repeated identical SDK prompts cannot always be
distinguished from repeated preparation. There is no universal raw-input guarantee.

Advice is framed as fallible model output in a **tool-result text block**, with
markup escaping, not in trusted `additionalContext`. This is provenance, not proof
that the receiving model cannot be misled. Original tool content is preserved;
error status and tool metadata are not changed. The original result is recorded
before the advisory addition, preventing the sidecar from reviewing its own output.

This first pilot does **not** recursively ingest child-agent transcripts, reconstruct
a complete cross-repo trajectory, or keep a persistent Tier-2 conversation. Main
session task results can be observed, but they are not full child coverage. Buffers
are bounded; truncated context is marked `partial`, never called exhaustive coverage.
It is not a security sandbox, merge gate, permissions arbiter, or completion verifier.

## Tests and observability

```sh
node --test profiles/omp-arcs/tests/*.test.mjs
cd profiles/omp-arcs
bun install
bun tests/native-smoke.ts
```

Node tests exercise the scheduler, stale/deduplicated advice, cancellation, missing
models, mocked host integration, and the no-wait/no-wake contracts. The separate
Bun smoke test loads the **real** pinned OMP SDK and extension with no provider
prompt. Neither substitutes for a credentialed end-to-end run on your workstation.
Package dependencies are exact at the direct OMP version, but the generated Bun
lockfile is not committed yet; this pilot is not a fully locked distribution.

`/arcs status` shows actual route resolution, observed/reviewed watermarks, in-flight
state, truncation, delivered/discarded counts, and failures. `arcs-audit` session
entries record check reasons, model selections, returned token usage where available,
latencies, and delivery/discard decisions. No fabricated dollar totals or task-success
scores are computed. Use a small real-task pilot to measure useful nudges, misses,
false alarms, latency, and spend before making it a global default.

## Source basis

Inspected 2026-09-30 at OMP commit
`969bd9fb1e2b1b058c65a0dc048fa8f06d8bb9f4`:

- [Extension discovery](https://github.com/can1357/oh-my-pi/blob/969bd9fb1e2b1b058c65a0dc048fa8f06d8bb9f4/docs/extension-loading.md): explicit packages, manifests, native roots.
- [Extension API](https://github.com/can1357/oh-my-pi/blob/969bd9fb1e2b1b058c65a0dc048fa8f06d8bb9f4/docs/extensions.md): host timers, model catalog, tool hooks, idle-wake delivery distinction.
- [Task agents](https://github.com/can1357/oh-my-pi/blob/969bd9fb1e2b1b058c65a0dc048fa8f06d8bb9f4/docs/task-agent-discovery.md): agent frontmatter and sibling capability discovery.
- [SDK](https://github.com/can1357/oh-my-pi/blob/969bd9fb1e2b1b058c65a0dc048fa8f06d8bb9f4/docs/sdk.md): independent registries, restricted toolsets, process-state ownership, disposal.
- [DeepSeek catalog contract](https://github.com/can1357/oh-my-pi/blob/969bd9fb1e2b1b058c65a0dc048fa8f06d8bb9f4/packages/catalog/src/compat/rules/providers/deepseek.kdl) and [MiMo catalog](https://github.com/can1357/oh-my-pi/blob/969bd9fb1e2b1b058c65a0dc048fa8f06d8bb9f4/packages/catalog/src/compat/rules/providers/xiaomi-token-plan-cn.kdl): model IDs, not performance rankings.
- [Archify](https://github.com/tt-a1i/archify/tree/d5a1333d7447c866a765adac7d4d062f2f02e4d2): actual JSON-IR renderer, not a lookalike diagram.
