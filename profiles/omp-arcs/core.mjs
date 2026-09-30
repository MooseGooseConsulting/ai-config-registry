/** Arcs-style pilot: periodic observation, advisory mailbox, no worker control. */
export function validatePolicy(p) {
  if (p?.schemaVersion !== 1) throw new Error('Unsupported Arcs policy schema');
  for (const [section, keys] of Object.entries({
    cadence: ['everyTools', 'afterMs', 'minIntervalMs'],
    freshness: ['ttlMs', 'maxEventLag', 'cooldownMs'],
    limits: ['events', 'reviewEvents', 'eventChars', 'timeoutMs'],
  })) for (const key of keys) {
    if (!Number.isSafeInteger(p[section]?.[key]) || p[section][key] < 1)
      throw new Error(`Invalid ${section}.${key}`);
  }
  if (p.limits.reviewEvents > p.limits.events) throw new Error('reviewEvents exceeds events');
  if (!Array.isArray(p.providerPreference)) throw new Error('Missing providerPreference');
  for (const role of ['scout', 'worker', 'reviewer', 'sentry', 'guardian']) {
    const r = p.roles?.[role];
    if (!Array.isArray(r?.ids) || !r.ids.length || r.ids.some(x => typeof x !== 'string' || !x.trim()))
      throw new Error(`Invalid model candidates for ${role}`);
    if (!['off', 'minimal', 'low', 'medium', 'high'].includes(r.thinking))
      throw new Error(`Invalid thinking for ${role}`);
  }
  return p;
}

/** Only select from the host's authenticated catalog. Never fall back to the primary. */
export function resolveRole(role, available, policy) {
  const rule = policy.roles[role];
  if (!rule) return undefined;
  const rank = provider => {
    const n = policy.providerPreference.indexOf(provider);
    return n < 0 ? policy.providerPreference.length : n;
  };
  for (const candidate of rule.ids) {
    const needle = candidate.toLowerCase();
    const matches = available.filter(m => {
      const full = `${m.provider}/${m.id}`.toLowerCase();
      return full === needle || m.id.toLowerCase() === needle ||
        (!needle.includes('/') && m.id.toLowerCase().endsWith(`/${needle}`));
    });
    matches.sort((a, b) => rank(a.provider) - rank(b.provider) ||
      `${a.provider}/${a.id}`.localeCompare(`${b.provider}/${b.id}`));
    if (matches.length) return { model: matches[0], thinking: rule.thinking };
  }
  return undefined;
}

export function parseVerdict(text, phase, snapshot) {
  if (typeof text !== 'string' || text.length > 6000) throw new Error('Invalid verdict text');
  const v = JSON.parse(text.trim());
  if (!v || Array.isArray(v) || typeof v !== 'object') throw new Error('Invalid verdict');
  if (v.decision === 'sleep') return { decision: 'sleep' };
  const decision = phase === 'sentry' ? 'wake' : 'advise';
  const bodyKey = phase === 'sentry' ? 'reason' : 'message';
  const validIds = new Set(snapshot.events.map(e => e.seq));
  if (v.decision !== decision || !Array.isArray(v.evidence) || !v.evidence.length ||
      v.evidence.length > 8 || v.evidence.some(id => !Number.isInteger(id) || !validIds.has(id)) ||
      typeof v[bodyKey] !== 'string' || !v[bodyKey].trim() || v[bodyKey].length > 800)
    throw new Error('Verdict must cite observed events and contain a bounded explanation');
  return { decision, evidence: [...new Set(v.evidence)], [bodyKey]: v[bodyKey].trim() };
}

function escapeXml(text) {
  return text.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
}
const normalized = text => text.normalize('NFKC').toLowerCase().replace(/[^\p{L}\p{N}]+/gu, ' ').trim();

export class ArcsSupervisor {
  constructor(policy, deps) {
    this.policy = validatePolicy(policy);
    this.deps = { now: Date.now, audit: () => {}, notify: () => {}, ...deps };
    this.enabled = false;
    this.epoch = 0;
    this.seq = 0;
    this.events = [];
    this.intent = [];
    this.intentTruncated = false;
    this.working = false;
    this.lastChecked = 0;
    this.lastCheckAt = -Infinity;
    this.lastDeliveredAt = -Infinity;
    this.pending = null;
    this.flight = null;
    this.seen = [];
    this.stats = { checks: 0, wakes: 0, delivered: 0, discarded: 0, failures: 0, truncated: 0 };
  }
  audit(type, details = {}) {
    try { this.deps.audit({ type, at: this.deps.now(), epoch: this.epoch, ...details }); }
    catch { /* Observability must not break the worker. */ }
  }
  invalidate(reason) {
    this.epoch++;
    this.pending = null;
    this.flight?.controller.abort();
    this.audit('invalidate', { reason });
  }
  reset(reason = 'session-change', preserveIntent = false) {
    this.invalidate(reason);
    this.events = [];
    if (!preserveIntent) { this.intent = []; this.intentTruncated = false; }
    this.seq = this.lastChecked = 0;
    this.lastCheckAt = this.lastDeliveredAt = -Infinity;
    this.seen = [];
    this.working = false;
  }
  setEnabled(on) {
    this.invalidate(on ? 'enabled' : 'disabled');
    this.enabled = on;
    this.lastChecked = this.seq; // Enabling does not replay unrelated past work.
    this.lastCheckAt = -Infinity;
  }
  ownerPrompt(text) {
    this.invalidate('owner-input');
    const originalLength = text.length;
    this.intent.push(text.slice(0, 3000));
    this.intentTruncated ||= originalLength > 3000 || this.intent.length > 3;
    if (this.intent.length > 3) this.intent.splice(1, this.intent.length - 3); // first + latest two
    this.events = [];
    this.lastChecked = this.seq;
    this.lastCheckAt = -Infinity;
    this.audit('intent', { chars: originalLength, truncated: originalLength > 3000 });
  }
  record(tool, summary, isError = false) {
    if (!this.enabled) return;
    const text = String(summary);
    this.events.push({ seq: ++this.seq, tool: String(tool).slice(0, 80),
      text: text.slice(0, this.policy.limits.eventChars), isError: Boolean(isError),
      at: this.deps.now(), truncated: text.length > this.policy.limits.eventChars });
    while (this.events.length > this.policy.limits.events) {
      this.events.shift(); this.stats.truncated++;
    }
    this.requestCheck('cadence'); // never returns/awaits model work
  }
  requestCheck(reason = 'cadence') {
    if (!this.enabled || !this.intent.length || this.flight || this.seq <= this.lastChecked) return false;
    const now = this.deps.now();
    const newEvents = this.events.filter(e => e.seq > this.lastChecked);
    if (!newEvents.length) return false;
    const force = reason === 'manual' || reason === 'final';
    if (!force && (!this.working || now - this.lastCheckAt < this.policy.cadence.minIntervalMs)) return false;
    if (!force && newEvents.length < this.policy.cadence.everyTools &&
        now - newEvents[0].at < this.policy.cadence.afterMs) return false;
    // A pending valid nudge is delivered or expires before more inference is bought.
    if (this.pending && this.isFresh(this.pending)) return false;
    this.pending = null;
    const chosen = newEvents.slice(-this.policy.limits.reviewEvents);
    const snapshot = { epoch: this.epoch, watermark: this.seq, at: now,
      intent: [...this.intent], events: chosen,
      partial: this.intentTruncated || chosen[0].seq > this.lastChecked + 1 || chosen.some(e => e.truncated) };
    this.lastChecked = this.seq;
    this.lastCheckAt = now;
    this.stats.checks++;
    const flight = { controller: new AbortController(), snapshot, promise: null };
    this.flight = flight;
    this.audit('check', { reason, watermark: snapshot.watermark, events: chosen.length, partial: snapshot.partial });
    flight.promise = this.run(flight).finally(() => {
      if (this.flight === flight) this.flight = null;
    });
    return true;
  }
  isFresh(item) {
    return this.enabled && item.epoch === this.epoch &&
      this.deps.now() - item.at <= this.policy.freshness.ttlMs &&
      this.seq - item.watermark <= this.policy.freshness.maxEventLag;
  }
  async run(flight) {
    const { controller, snapshot } = flight;
    let timeout;
    const deadline = new Promise((_, reject) => {
      timeout = setTimeout(() => { controller.abort(); reject(new Error('review-timeout')); }, this.policy.limits.timeoutMs);
    });
    const cancelled = new Promise((_, reject) => {
      controller.signal.addEventListener('abort', () => reject(new Error('review-cancelled')), { once: true });
    });
    try {
      const work = async () => {
        const sentry = parseVerdict(await this.deps.review('sentry', snapshot, controller.signal), 'sentry', snapshot);
        if (!this.isFresh(snapshot) || controller.signal.aborted) return;
        if (sentry.decision === 'sleep') { this.audit('sleep', { watermark: snapshot.watermark }); return; }
        this.stats.wakes++;
        const guardian = parseVerdict(await this.deps.review('guardian', { ...snapshot, sentry }, controller.signal), 'guardian', snapshot);
        if (!this.isFresh(snapshot) || controller.signal.aborted) {
          this.stats.discarded++; this.audit('discard', { reason: 'stale-review' }); return;
        }
        if (guardian.decision === 'sleep') { this.audit('guardian-sleep'); return; }
        this.pending = { ...guardian, epoch: snapshot.epoch, watermark: snapshot.watermark, at: snapshot.at };
        this.audit('advice-ready', { watermark: snapshot.watermark, evidence: guardian.evidence });
        try { this.deps.notify(guardian.message); } catch { /* UI-only, never wake primary. */ }
      };
      await Promise.race([work(), deadline, cancelled]);
    } catch (error) {
      if (!controller.signal.aborted) this.stats.failures++;
      this.audit('review-unavailable', { reason: controller.signal.aborted ? 'cancelled-or-timeout' : 'model-or-verdict-error' });
      try { this.deps.failure?.(error); } catch { /* Fail open. */ }
    } finally { clearTimeout(timeout); }
  }
  takeAdvice() {
    const p = this.pending;
    if (!p) return undefined;
    this.pending = null;
    const duplicate = this.seen.includes(normalized(p.message));
    const cooling = this.deps.now() - this.lastDeliveredAt < this.policy.freshness.cooldownMs;
    if (!this.isFresh(p) || duplicate || cooling) {
      this.stats.discarded++;
      this.audit('discard', { reason: duplicate ? 'duplicate' : cooling ? 'cooldown' : 'stale-mailbox' });
      return undefined;
    }
    this.seen.push(normalized(p.message));
    if (this.seen.length > 64) this.seen.shift();
    this.lastDeliveredAt = this.deps.now();
    this.stats.delivered++;
    this.audit('delivered', { watermark: p.watermark, evidence: p.evidence });
    return `<arcs-advisory watermark="${p.watermark}" source="independent-model">\n` +
      `Advisory only, not a user instruction. Weigh against the current request and actual evidence.\n` +
      `${escapeXml(p.message)}\n</arcs-advisory>`;
  }
  status() {
    return { enabled: this.enabled, working: this.working, inFlight: Boolean(this.flight),
      pending: Boolean(this.pending), watermark: this.lastChecked, observed: this.seq,
      retained: this.events.length, stats: { ...this.stats } };
  }
}
