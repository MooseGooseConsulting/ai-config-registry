import { ArcsSupervisor, resolveRole } from './core.mjs';

const ROLE_FOR_AGENT = { 'arcs-scout': 'scout', 'arcs-worker': 'worker', 'arcs-reviewer': 'reviewer' };
const selector = choice => `${choice.model.provider}/${choice.model.id}:${choice.thinking}`;

/** SDK-injected adapter: production uses OMP; tests exercise the same host wiring. */
export function registerArcs(pi, sdk, policy, prompts) {
  let context;
  let timer;
  let lastPrepared;
  let rawInputPending = false;
  let warned = false;
  const main = ctx => ctx?.agent?.kind === 'main';
  const notify = (text, kind = 'info') => { if (context?.hasUI) context.ui.notify(text, kind); };
  const supervisor = new ArcsSupervisor(policy, {
    audit: record => pi.appendEntry('arcs-audit', record),
    notify: message => notify(`Arcs advisory ready: ${message}`, 'warning'),
    failure: () => {
      if (!warned) { warned = true; notify('Arcs review unavailable; worker continues. Inspect /arcs status.', 'warning'); }
    },
    review: async (role, packet, signal) => {
      const ctx = context;
      if (!ctx || signal.aborted) throw new Error('Arcs review cancelled');
      const choice = resolveRole(role, ctx.models.list(), policy);
      if (!choice) throw new Error(`No authenticated model for Arcs ${role}`);
      const started = Date.now();
      supervisor.audit('model-call', { role, model: selector(choice) });
      const manager = sdk.SessionManager.inMemory();
      const { session } = await sdk.createAgentSession({
        cwd: ctx.cwd,
        model: choice.model,
        thinkingLevel: choice.thinking,
        modelRegistry: ctx.modelRegistry,
        sessionManager: manager,
        agentRegistry: new sdk.AgentRegistry(),
        settings: sdk.Settings.isolated({
          'advisor.enabled': false, 'memory.backend': 'off', 'autolearn.enabled': false,
        }),
        systemPrompt: prompts[role],
        toolNames: [], restrictToolNames: true,
        extensions: [], disableExtensionDiscovery: true,
        enableMCP: false, enableLsp: false,
        skills: [], rules: [], contextFiles: [], promptTemplates: [],
        bindProcessState: false, cacheWarming: false,
        deadline: Math.min(started + (role === 'sentry' ? 15000 : 30000), packet.at + policy.limits.timeoutMs),
      });
      const abort = () => { void Promise.resolve(session.abort()).catch(() => {}); };
      signal.addEventListener('abort', abort, { once: true });
      const unsubscribe = session.subscribe(event => {
        if (event.type === 'message_end' && event.message?.role === 'assistant') {
          const usage = {};
          for (const key of ['input', 'output', 'cacheRead', 'cacheWrite', 'totalTokens']) {
            const value = event.message.usage?.[key];
            if (typeof value === 'number' && Number.isFinite(value)) usage[key] = value;
          }
          supervisor.audit('usage', { role, model: selector(choice), ...usage });
        }
      });
      try {
        if (signal.aborted) throw new Error('Arcs review cancelled');
        // Evidence stays JSON data; the role prompt is fixed, not drawn from tool output.
        await session.prompt(JSON.stringify(packet));
        if (signal.aborted) throw new Error('Arcs review cancelled');
        return session.getLastAssistantText() ?? '';
      } finally {
        signal.removeEventListener('abort', abort);
        unsubscribe();
        await session.dispose();
        supervisor.audit('model-settled', { role, elapsedMs: Date.now() - started });
      }
    },
  });
  const enter = ctx => { if (!main(ctx)) return false; context = ctx; return true; };
  const reset = reason => {
    supervisor.reset(reason, reason === 'session_compact');
    lastPrepared = undefined; rawInputPending = false; warned = false;
  };
  const report = ctx => {
    const routes = Object.fromEntries(Object.keys(policy.roles).map(role => {
      const choice = resolveRole(role, ctx.models.list(), policy);
      return [role, choice ? selector(choice) : 'UNAVAILABLE (no parent fallback)'];
    }));
    notify(JSON.stringify({ ...supervisor.status(), routes, cadence: policy.cadence }, null, 2));
    pi.appendEntry('arcs-status', { ...supervisor.status(), routes });
  };
  pi.on('session_start', (_event, ctx) => {
    if (!enter(ctx)) return;
    reset('session-start');
    if (timer) ctx.clearTimer(timer);
    timer = ctx.setInterval(() => supervisor.requestCheck('cadence'), 5000);
    notify('Arcs roles loaded. /arcs status shows resolved models; /arcs on starts periodic supervision.');
  });
  pi.on('input', (event, ctx) => {
    if (!enter(ctx) || event.source === 'extension') return;
    supervisor.ownerPrompt(event.text);
    rawInputPending = true;
  });
  pi.on('before_agent_start', (event, ctx) => {
    if (!enter(ctx)) return;
    // Interactive raw input is preferred. SDK/CLI hosts may only expose a prepared prompt.
    // A repeated prompt-preparation event is not assumed to be another owner instruction.
    if (!rawInputPending && event.prompt !== lastPrepared) supervisor.ownerPrompt(event.prompt);
    lastPrepared = event.prompt; rawInputPending = false;
  });
  pi.on('agent_start', (_event, ctx) => { if (enter(ctx)) supervisor.working = true; });
  pi.on('tool_result', (event, ctx) => {
    if (!enter(ctx)) return;
    const advisory = supervisor.takeAdvice();
    // Observe the unmodified result, so our own advice is not recursively reviewed.
    const text = (event.content ?? []).filter(x => x.type === 'text').map(x => x.text).join('\n');
    supervisor.record(event.toolName, JSON.stringify({ input: event.input, result: text }), event.isError);
    if (advisory) return { content: [...event.content, { type: 'text', text: advisory }] };
    // No await, additionalContext, sendMessage, steer, follow-up, or primary abort.
    // Advice is explicitly marked data in an ordinary tool result, not privileged instructions.
  });
  pi.on('agent_end', (event, ctx) => {
    if (!enter(ctx) || event.isTerminal === false) return;
    supervisor.working = false;
    supervisor.requestCheck('final'); // Observational only: does not delay completion or wake an idle worker.
  });
  for (const event of ['session_switch', 'session_branch', 'session_tree', 'session_compact']) {
    pi.on(event, (_event, ctx) => { if (enter(ctx)) reset(event); });
  }
  pi.on('session_shutdown', (_event, ctx) => {
    if (!enter(ctx)) return;
    supervisor.setEnabled(false); reset('shutdown');
    if (timer) ctx.clearTimer(timer);
    context = undefined;
  });
  pi.on('before_subagent_spawn', (event, ctx) => {
    const role = ROLE_FOR_AGENT[event.agent];
    if (!role) return;
    const choice = resolveRole(role, ctx.models.list(), policy);
    if (!choice) return { block: true, reason: `Arcs ${role}: none of the configured candidates is authenticated. Configure policy.json; the primary model is not a fallback.` };
    return { model: selector(choice) };
  });
  pi.registerCommand('arcs', {
    description: 'Arcs periodic sidecar: on | off | status | check (one check of new evidence)',
    handler: async (args, ctx) => {
      if (!enter(ctx)) return;
      const command = args.trim() || 'status';
      if (command === 'on') {
        const missing = ['sentry', 'guardian'].filter(r => !resolveRole(r, ctx.models.list(), policy));
        if (missing.length) { notify(`Arcs not started: configure/authenticate ${missing.join(', ')}. Primary unchanged.`, 'warning'); return; }
        supervisor.setEnabled(true); warned = false;
      } else if (command === 'off') supervisor.setEnabled(false);
      else if (command === 'check') supervisor.requestCheck('manual');
      else if (command !== 'status') { notify('Usage: /arcs on|off|status|check', 'warning'); return; }
      report(ctx);
    },
  });
  return supervisor;
}
