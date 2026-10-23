"""Normalize approved units while keeping original readings and quality evidence."""
import hashlib
import json
from datetime import timezone
from .contracts import SensorWindow

UNITS = {'temperature': 'C', 'energy': 'kWh', 'vibration': 'mm/s', 'lubricant': 'percent'}
DOMAIN = {'temperature': (-20, 200), 'energy': (0, 10), 'vibration': (0, 100), 'lubricant': (0, 100)}


def validate_window(raw: dict) -> SensorWindow:
    window = SensorWindow.model_validate(raw)
    flags = list(window.quality_flags)
    window.start = window.start.astimezone(timezone.utc)
    window.end = window.end.astimezone(timezone.utc)
    for name, expected_unit in UNITS.items():
        channel = window.channels.get(name)
        if channel is None:
            flags.append(f'missing:{name}')
            continue
        original_unit = channel.unit
        if original_unit != expected_unit and (name, original_unit) not in {('temperature', 'F'), ('energy', 'Wh')}:
            raise ValueError(f'Unsupported unit for {name}: expected {expected_unit}')
        if not channel.samples:
            flags.append(f'missing:{name}')
            continue
        # Do not trust caller-supplied normalization metadata.
        channel.original_unit = original_unit
        channel.original_samples = [s.model_copy(deep=True) for s in channel.samples]
        for sample in channel.samples:
            sample.timestamp = sample.timestamp.astimezone(timezone.utc)
            if original_unit == 'F':
                sample.value = (sample.value - 32) * 5 / 9
            elif original_unit == 'Wh':
                sample.value /= 1000
            if not DOMAIN[name][0] <= sample.value <= DOMAIN[name][1]:
                flags.append(f'out_of_domain:{name}')
            if not window.start <= sample.timestamp <= window.end:
                flags.append(f'outside_window:{name}')
        channel.unit = expected_unit
        times = [s.timestamp for s in channel.samples]
        if len(times) < 2:
            flags.append(f'insufficient:{name}')
        if any(a >= b for a, b in zip(times, times[1:])):
            flags.append(f'out_of_order:{name}')
        if (window.end - max(times)).total_seconds() > 60:
            flags.append(f'stale:{name}')
    if window.asset_id != 'SIM-PRESS-01' or window.source_kind != 'simulated':
        flags.append('unsupported_asset_or_source')
    window.quality_flags = sorted(set(flags))
    window.window_id = ''
    canonical = json.dumps(window.model_dump(mode='json'), sort_keys=True, separators=(',', ':'))
    window.window_id = hashlib.sha256(canonical.encode()).hexdigest()[:24]
    return SensorWindow.model_validate(window.model_dump())
