# ai-generated: 90% - Claude Code drafted, reviewed by me
"""A minimal RED histogram, http_server_request_duration_seconds (MONITORING-SPEC.md M-03 to M-07).

No client library: a hand-rolled exposition keeps the label set exactly {http_request_method, http_route,
http_response_status_code, le} and avoids the extra labels an OpenTelemetry Prometheus exporter would add.
"""
from bisect import bisect_left

NAME = "http_server_request_duration_seconds"

# The ladder designed from the own measurement (slo.md, section "Buckets"); ai-first-draft.md records what came
# before it. At most 30 finite boundaries (M-06), in seconds.
BUCKETS: list[float] = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]

# key -> {"counts": per-bucket landing counts (index i: value in (BUCKETS[i-1], BUCKETS[i]]; last: > BUCKETS[-1]),
#         "sum": seconds, "count": observations}
_series: dict[tuple[str, str, str], dict] = {}


def observe(method: str, route: str, status_code: int, seconds: float) -> None:
    key = (method, route, str(status_code))
    entry = _series.get(key)
    if entry is None:
        entry = {"counts": [0] * (len(BUCKETS) + 1), "sum": 0.0, "count": 0}
        _series[key] = entry
    entry["counts"][bisect_left(BUCKETS, seconds)] += 1
    entry["sum"] += seconds
    entry["count"] += 1


def render() -> str:
    lines = [f"# HELP {NAME} Duration of HTTP server requests, in seconds.", f"# TYPE {NAME} histogram"]
    for (method, route, status), entry in _series.items():
        labels = f'http_request_method="{method}",http_route="{route}",http_response_status_code="{status}"'
        cumulative = 0
        for boundary, count in zip(BUCKETS, entry["counts"]):
            cumulative += count
            lines.append(f'{NAME}_bucket{{{labels},le="{boundary}"}} {cumulative}')
        cumulative += entry["counts"][-1]
        lines.append(f'{NAME}_bucket{{{labels},le="+Inf"}} {cumulative}')
        lines.append(f'{NAME}_sum{{{labels}}} {entry["sum"]}')
        lines.append(f'{NAME}_count{{{labels}}} {entry["count"]}')
    return "\n".join(lines) + "\n"
