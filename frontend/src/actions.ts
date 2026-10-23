import type {
  ActionKind,
  ActionRecord,
  ComponentActionState,
} from "./types";

/** Payload accepted by actions that carry extra data (e.g. a chosen window). */
export interface ActionPayload {
  window?: string;
}

/** Human-readable status badge for a performed action. */
export function badgeLabelFor(kind: ActionKind, payload?: ActionPayload): string {
  switch (kind) {
    case "dispatch_tech":
      return "Tech dispatched";
    case "order_part":
      return "Part ordered";
    case "hire_contractor":
      return "Contractor hired";
    case "work_order":
      return "Work order drafted";
    case "schedule_window":
      return payload?.window ? `Scheduled ${payload.window}` : "Scheduled";
    case "check_inventory":
      // Inventory checks are informational and produce no row badge.
      return "";
  }
}

/** Badge label for an already-recorded action. */
export function badgeFor(record: ActionRecord): string {
  return record.badgeLabel;
}

/**
 * Records an action against a component, returning a new state object (never
 * mutates the input). Re-taking the same action kind replaces the prior record
 * for that kind so badges/windows stay current without duplicating entries.
 */
export function addAction(
  state: ComponentActionState,
  componentId: string,
  kind: ActionKind,
  payload?: ActionPayload,
): ComponentActionState {
  const record: ActionRecord = {
    kind,
    badgeLabel: badgeLabelFor(kind, payload),
    ...(kind === "schedule_window" && payload?.window
      ? { scheduledWindow: payload.window }
      : {}),
  };

  const existing = state[componentId] ?? [];
  const withoutKind = existing.filter((r) => r.kind !== kind);

  return {
    ...state,
    [componentId]: [...withoutKind, record],
  };
}

/** Kinds that represent a committed unit of remediation work. */
const WORK_ORDER_KINDS: ReadonlySet<ActionKind> = new Set<ActionKind>([
  "work_order",
  "dispatch_tech",
  "hire_contractor",
]);

/**
 * Derives the "Open work orders" count: the static baseline plus every
 * work-order-generating action recorded across all components.
 */
export function openWorkOrderCount(
  baseCount: number,
  state: ComponentActionState,
): number {
  let count = baseCount;
  for (const records of Object.values(state)) {
    for (const record of records) {
      if (WORK_ORDER_KINDS.has(record.kind)) count += 1;
    }
  }
  return count;
}

/** Returns the badge labels (non-empty) for a component, for row display. */
export function badgesForComponent(
  state: ComponentActionState,
  componentId: string,
): string[] {
  return (state[componentId] ?? [])
    .map((r) => r.badgeLabel)
    .filter((label) => label.length > 0);
}

/** Returns the non-empty badge labels for a set of action records. */
export function badgesForComponentRecords(records: ActionRecord[]): string[] {
  return records.map((r) => r.badgeLabel).filter((label) => label.length > 0);
}

/** True if the given action kind has already been taken for the component. */
export function hasAction(
  state: ComponentActionState,
  componentId: string,
  kind: ActionKind,
): boolean {
  return (state[componentId] ?? []).some((r) => r.kind === kind);
}
