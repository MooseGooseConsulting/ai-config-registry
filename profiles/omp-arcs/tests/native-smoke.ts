/** Run under Bun with the real, pinned OMP package. No model prompt or credentials. */
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import * as sdk from '@oh-my-pi/pi-coding-agent';
import arcs from '../index';

const root = await mkdtemp(join(tmpdir(), 'omp-arcs-smoke-'));
try {
  const auth = await sdk.discoverAuthStorage(join(root, 'agent'));
  const models = new sdk.ModelRegistry(auth);
  const result = await sdk.createAgentSession({
    cwd: root, agentDir: join(root, 'agent'), modelRegistry: models,
    settings: sdk.Settings.isolated({ 'advisor.enabled': false, 'memory.backend': 'off', 'autolearn.enabled': false }),
    sessionManager: sdk.SessionManager.inMemory(), agentRegistry: new sdk.AgentRegistry(),
    extensions: [arcs], disableExtensionDiscovery: true,
    toolNames: [], restrictToolNames: true, enableMCP: false, enableLsp: false,
    skills: [], rules: [], contextFiles: [], promptTemplates: [],
    bindProcessState: false, cacheWarming: false,
  });
  try {
    assert.equal(result.extensionsResult.errors.length, 0);
    assert.deepEqual(result.session.getActiveToolNames(), []);
    assert.equal(typeof result.session.getLastAssistantText, 'function');
    console.log('Native OMP session and Arcs extension loaded without model inference.');
  } finally { await result.session.dispose(); }
} finally { await rm(root, { recursive: true, force: true }); }
