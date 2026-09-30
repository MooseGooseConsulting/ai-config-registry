import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { registerArcs } from '../host.mjs';
const policy = JSON.parse(readFileSync(new URL('../policy.json', import.meta.url)));
function harness(kind = 'main') {
  const handlers = new Map(), commands = new Map(), logs = [], notes = [], options = [];
  const ctx = { cwd: '/repo', hasUI: true, agent: {kind}, modelRegistry: {},
    models: { list: () => [{provider:'deepseek',id:'deepseek-v4.1-flash'}, {provider:'openai-codex',id:'gpt-6-astra'}] },
    ui: {notify: text => notes.push(text)}, setInterval: fn => fn, clearTimer: () => {} };
  const pi = { on: (name, fn) => handlers.set(name, fn), registerCommand: (name, cfg) => commands.set(name, cfg),
    appendEntry: (type, data) => logs.push({type,data}), sendMessage: () => assert.fail('must not wake or steer') };
  const sdk = {
    AgentRegistry: class {}, SessionManager: {inMemory: () => ({})}, Settings: {isolated: value => value},
    createAgentSession: async config => {
      options.push(config); let packet;
      return {session: { subscribe: () => () => {}, prompt: async text => { packet = JSON.parse(text); },
        getLastAssistantText: () => JSON.stringify(config.systemPrompt === 'sentry'
          ? {decision:'wake',evidence:[packet.events[0].seq],reason:'check intent'}
          : {decision:'advise',evidence:[packet.events[0].seq],message:'Verify the requested invariant.'}),
        abort: async () => {}, dispose: async () => {} }};
    },
  };
  const s = registerArcs(pi, sdk, policy, {sentry:'sentry',guardian:'guardian'});
  const fire = (name, event = {}) => handlers.get(name)?.(event, ctx);
  fire('session_start');
  return {s,ctx,handlers,commands,logs,notes,options,fire};
}
const result = {toolName:'read',input:{path:'source.ts'},content:[{type:'text',text:'original result'}],isError:false};

test('registration/startup never invokes a reviewer until explicitly enabled', () => {
  const h = harness(); assert.equal(h.s.enabled, false); assert.equal(h.options.length, 0);
  assert.ok(h.commands.has('arcs')); assert.ok(h.handlers.has('before_subagent_spawn'));
});
test('tool-result hook remains synchronous and preserves original output and error status', async () => {
  const h = harness(); await h.commands.get('arcs').handler('on',h.ctx);
  h.fire('before_agent_start',{prompt:'Implement the feature'}); h.fire('agent_start');
  for(let i=0;i<12;i++) assert.equal(h.fire('tool_result',result), undefined);
  await h.s.flight.promise;
  assert.equal(h.options.length,2);
  const output = h.fire('tool_result',{...result,isError:true});
  assert.equal(output.content[0], result.content[0]);
  assert.match(output.content[1].text,/arcs-advisory/);
  assert.equal(output.isError,undefined); assert.equal(output.additionalContext,undefined);
  assert.ok(!h.s.events.at(-1).text.includes('arcs-advisory'));
});
test('native helper options exclude tools, extra contexts, nested advisors, and process-state ownership', async () => {
  const h = harness(); await h.commands.get('arcs').handler('on',h.ctx);
  h.fire('before_agent_start',{prompt:'task'}); h.fire('agent_start');
  for(let i=0;i<12;i++) h.fire('tool_result',result);
  await h.s.flight.promise;
  for(const o of h.options) {
    assert.deepEqual(o.toolNames,[]); assert.equal(o.restrictToolNames,true);
    assert.equal(o.bindProcessState,false); assert.equal(o.disableExtensionDiscovery,true);
    assert.deepEqual(o.contextFiles,[]); assert.deepEqual(o.extensions,[]);
    assert.equal(o.settings['advisor.enabled'],false); assert.equal(o.enableMCP,false);
    assert.equal(o.modelRegistry,h.ctx.modelRegistry);
  }
  assert.equal(h.options[0].model.provider,'deepseek');
  assert.equal(h.options[1].model.provider,'openai-codex');
  assert.equal(h.options[1].thinkingLevel,'medium');
});
test('named agent routing changes only our specialist names', () => {
  const h = harness();
  assert.equal(h.fire('before_subagent_spawn',{agent:'existing-worker'}),undefined);
  assert.deepEqual(h.fire('before_subagent_spawn',{agent:'arcs-worker'}),{model:'deepseek/deepseek-v4.1-flash:high'});
  h.ctx.models.list=()=>[];
  assert.equal(h.fire('before_subagent_spawn',{agent:'arcs-reviewer'}).block,true);
});
test('child factories may route workers but do not start supervision', async () => {
  const h = harness('sub'); await h.commands.get('arcs').handler('on',h.ctx);
  h.fire('agent_start'); for(let i=0;i<20;i++) h.fire('tool_result',result);
  assert.equal(h.s.enabled,false); assert.equal(h.options.length,0);
});
test('missing reviewer model prevents activation rather than using an expensive implicit parent', async () => {
  const h = harness(); h.ctx.models.list=()=>[];
  await h.commands.get('arcs').handler('on',h.ctx);
  assert.equal(h.s.enabled,false); assert.match(h.notes.at(-1),/not started/);
});
test('real repeated user input invalidates old advice; duplicate preparation does not fabricate intent', () => {
  const h = harness();
  h.fire('input',{source:'interactive',text:'Original request'});
  h.fire('before_agent_start',{prompt:'Original request'});
  h.fire('before_agent_start',{prompt:'Original request'});
  assert.equal(h.s.intent.length,1);
  const epoch=h.s.epoch; h.fire('input',{source:'interactive',text:'Original request'});
  assert.ok(h.s.epoch>epoch); assert.equal(h.s.intent.length,2);
});
test('compaction preserves owner intent and shutdown cancels the supervisor', () => {
  const h = harness(); h.fire('before_agent_start',{prompt:'Original intent'});
  h.fire('session_compact'); assert.deepEqual(h.s.intent,['Original intent']);
  h.fire('session_shutdown'); assert.equal(h.s.enabled,false);
});
