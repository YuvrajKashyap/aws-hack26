import type { RippleChart as RippleChartData } from "../types";

interface Props {
  chart: RippleChartData;
}

export function RippleChart({ chart }: Props) {
  return (
    <svg
      viewBox={chart.viewBox}
      role="img"
      aria-label={chart.ariaLabel}
      style={{ width: "100%", height: "auto", display: "block" }}
    >
      <line
        x1="0"
        y1={chart.thresholdY}
        x2="520"
        y2={chart.thresholdY}
        stroke="#FF6B5E"
        strokeDasharray="6 6"
      />
      <text
        x="6"
        y={chart.thresholdY - 8}
        fill="#FFB3AB"
        fontSize="12"
        fontFamily="IBM Plex Mono, monospace"
      >
        alert threshold
      </text>
      <polyline fill="none" stroke="#3DD6C3" strokeWidth="2.5" points={chart.points} />
      <polyline
        fill="none"
        stroke="#9AA4B2"
        strokeWidth="2"
        strokeDasharray="3 5"
        points={chart.projectedPoints}
      />
    </svg>
  );
}
