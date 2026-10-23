export type RackStatus = "healthy" | "watch" | "critical";

export interface Rack {
  /** Rack identifier, e.g. "C7". */
  id: string;
  status: RackStatus;
}

export interface Kpi {
  label: string;
  value: string;
  sub: string;
  /** Optional accent color for the value (e.g. risk highlight). */
  valueColor?: string;
}

export type RiskLevel = "critical" | "watch";

/** Hardware category of a monitored component, used for filtering. */
export type ComponentType = "psu" | "nvme" | "fan" | "dimm";

/** Time window the dashboard scopes its risk view to. */
export type TimeRangeId = "7d" | "14d" | "30d";

export interface ReplacementItem {
  /** Failure-risk percentage shown in the ranked queue. */
  riskPct: number;
  level: RiskLevel;
  component: string;
  evidence: string;
  /** Hardware category, used by the component-type filter. */
  componentType: ComponentType;
}

/** Active dashboard filter selections. */
export interface DashboardFilters {
  /** Selected hall id (scope), e.g. "hall-2". */
  hallId: string;
  /** Selected time range. */
  timeRange: TimeRangeId;
  /**
   * Selected component types. An empty set means "all types" (no filtering),
   * which keeps the default view showing everything.
   */
  componentTypes: ReadonlySet<ComponentType>;
}

export interface RippleChart {
  /** Accessible description of the SVG chart. */
  ariaLabel: string;
  viewBox: string;
  /** Y position of the dashed alert-threshold line. */
  thresholdY: number;
  /** Measured ripple polyline points. */
  points: string;
  /** Projected (dashed) continuation points. */
  projectedPoints: string;
  caption: string;
}

export interface SelectedComponent {
  title: string;
  riskNote: string;
  chart: RippleChart;
  cause: string;
}

/** Remediation actions an operator can take on an at-risk component. */
export type ActionKind =
  | "dispatch_tech"
  | "order_part"
  | "hire_contractor"
  | "work_order"
  | "schedule_window"
  | "check_inventory";

/** A single action taken against a component, with its display badge. */
export interface ActionRecord {
  kind: ActionKind;
  /** Short status label shown on the queue row. Empty string = no row badge. */
  badgeLabel: string;
  /** Chosen maintenance window, only set for `schedule_window`. */
  scheduledWindow?: string;
}

/** Map of component id (e.g. "C7") to the actions taken against it. */
export type ComponentActionState = Record<string, ActionRecord[]>;
