import {
  componentTypeOptions,
  hallOptions,
  timeRangeOptions,
} from "../data";
import { PageHeader } from "./PageHeader";
import type { ComponentType, DashboardFilters, TimeRangeId } from "../types";

interface Props {
  filters: DashboardFilters;
  onChange: (next: DashboardFilters) => void;
}

/**
 * Dashboard filter bar: a hall select (scope), a time-range segmented
 * control, and a component-type multi-select. Replaces the old static
 * pill row. Each control is a distinct, accessible input matched to its job.
 */
export function FilterBar({ filters, onChange }: Props) {
  function setHall(hallId: string) {
    onChange({ ...filters, hallId });
  }

  function setTimeRange(timeRange: TimeRangeId) {
    onChange({ ...filters, timeRange });
  }

  function toggleType(type: ComponentType) {
    const next = new Set(filters.componentTypes);
    if (next.has(type)) next.delete(type);
    else next.add(type);
    onChange({ ...filters, componentTypes: next });
  }

  function clearTypes() {
    onChange({ ...filters, componentTypes: new Set() });
  }

  const selectedCount = filters.componentTypes.size;
  const typeSummary =
    selectedCount === 0
      ? "All component types"
      : `${selectedCount} type${selectedCount > 1 ? "s" : ""} selected`;

  return (
    <div className="top">
      <PageHeader />

      <div className="filters" role="group" aria-label="Dashboard filters">
        {/* Hall scope: single choice from a set -> select. */}
        <label className="filter-field">
          <span className="filter-label">Hall</span>
          <select
            className="filter-select"
            value={filters.hallId}
            onChange={(e) => setHall(e.target.value)}
          >
            {hallOptions.map((h) => (
              <option key={h.id} value={h.id}>
                {h.label}
              </option>
            ))}
          </select>
        </label>

        {/* Time range: a few discrete options -> segmented control. */}
        <div
          className="segmented"
          role="radiogroup"
          aria-label="Time range"
        >
          {timeRangeOptions.map((t) => {
            const active = filters.timeRange === t.id;
            return (
              <button
                key={t.id}
                type="button"
                role="radio"
                aria-checked={active}
                className={`seg${active ? " seg--active" : ""}`}
                onClick={() => setTimeRange(t.id)}
              >
                {t.label}
              </button>
            );
          })}
        </div>

        {/* Component type: any-of selection -> multi-select dropdown. */}
        <details className="multiselect">
          <summary className="multiselect__summary" aria-label="Component types">
            {typeSummary}
          </summary>
          <div className="multiselect__menu">
            {componentTypeOptions.map((c) => (
              <label key={c.id} className="multiselect__option">
                <input
                  type="checkbox"
                  checked={filters.componentTypes.has(c.id)}
                  onChange={() => toggleType(c.id)}
                />
                <span>{c.label}</span>
              </label>
            ))}
            {selectedCount > 0 && (
              <button
                type="button"
                className="multiselect__clear"
                onClick={clearTypes}
              >
                Clear
              </button>
            )}
          </div>
        </details>
      </div>
    </div>
  );
}
