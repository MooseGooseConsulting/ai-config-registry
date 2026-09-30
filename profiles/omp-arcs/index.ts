import { readFileSync } from 'node:fs';
import * as sdk from '@oh-my-pi/pi-coding-agent';
import { registerArcs } from './host.mjs';
import { validatePolicy } from './core.mjs';

export default function arcs(pi: sdk.ExtensionAPI) {
  const policyPath = process.env.OMP_ARCS_POLICY || new URL('./policy.json', import.meta.url);
  const policy = validatePolicy(JSON.parse(readFileSync(policyPath, 'utf8')));
  const prompts = Object.fromEntries(['sentry', 'guardian'].map(role => [
    role, readFileSync(new URL(`./prompts/${role}.md`, import.meta.url), 'utf8'),
  ]));
  registerArcs(pi, sdk, policy, prompts);
}
