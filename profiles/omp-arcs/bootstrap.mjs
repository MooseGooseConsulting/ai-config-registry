#!/usr/bin/env node
import { mkdirSync, existsSync, readFileSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { spawnSync } from 'node:child_process';

const pins = JSON.parse(readFileSync(new URL('./upstream.json', import.meta.url)));
const destination = process.argv[2];
if (!destination) { console.error('Usage: node bootstrap.mjs <checkout-directory>'); process.exit(2); }
const run = (args, cwd, capture = false) => {
  const r = spawnSync('git', args, { cwd, encoding: 'utf8', stdio: capture ? 'pipe' : 'inherit', shell: false });
  if (r.error || r.status !== 0) throw new Error(`git ${args[0]} failed: ${r.error?.message || r.stderr || r.status}`);
  return r.stdout?.trim();
};
try {
  const root = resolve(destination); mkdirSync(root, { recursive: true });
  for (const name of ['omp','archify']) {
    const pin = pins[name], path = join(root, name);
    if (!existsSync(path)) run(['clone','--filter=blob:none','--no-checkout',pin.url,path], root);
    else {
      if (run(['remote','get-url','origin'], path, true) !== pin.url) throw Error(`Wrong origin at ${path}; left unchanged`);
      if (run(['status','--porcelain'], path, true)) throw Error(`Dirty checkout at ${path}; left unchanged`);
    }
    run(['fetch','--depth','1','origin',pin.revision], path);
    run(['checkout','--detach',pin.revision], path);
    if (run(['rev-parse','HEAD'], path, true) !== pin.revision) throw Error(`Revision mismatch in ${name}`);
    console.log(`${name}: ${path} @ ${pin.revision}`);
  }
  console.log('Source checkouts ready. No user agent configuration or credentials were changed.');
} catch (error) { console.error(error.message); process.exitCode = 1; }
