import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";

/**
 * Runtime no-op by design.
 *
 * Loading this package makes its sibling agents directory discoverable.
 * Periodic Arcs supervision is staged as an OMP-core patch under native/.
 */
export default function ompArcsProfile(_pi: ExtensionAPI): void {}
