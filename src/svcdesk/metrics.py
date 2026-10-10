# ai-generated: 90% - Claude Code drafted, reviewed by me
"""A minimal RED histogram, http_server_request_duration_seconds (MONITORING-SPEC.md M-03 to M-07).

No client library: a hand-rolled exposition keeps the label set exactly {http_request_method, http_route,
http_response_status_code, le} and avoids the extra labels an OpenTelemetry Prometheus exporter would add.
"""
from bisect import bisect_left

NAME = "http_server_request_duration_seconds"

# The ladder designed from the own measurement (slo.md, section "Buckets"; ai-first-draft.md records the AI
# draft that came before it). 26 of the 30 allowed finite boundaries (M-06), in seconds.
#
# Measured with ./itsmlab.sh load 3 (login krystianf3008, 10 October 2026): q (p99) = 111.9 ms, inside a narrow
# slow mode from about 96 to 134 ms that holds ~4.4 % of requests; the fast path (96 % of requests) sits below
# 46 ms. 0.005 to 0.05 covers the fast path at the same resolution the course's own worked example uses; 0.06 to
# 0.09 bridges the gap; 0.095 to 0.14 is spent at 5 ms steps around q - each such bucket is (0.005 / 0.1119) =
# 4.5 % of q, far inside the <= 20 % rule (M-11), and the banded region (0.095, 0.14) covers q from -15 % to
# +25 %, comfortably past the +-10 % band M-08's run-to-run variance calls for; 0.2, 0.5 and 1.0 close the ladder
# for the rare slower tail.
BUCKETS: list[float] = [
    0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.035, 0.04, 0.05,
    0.06, 0.07, 0.08, 0.09,
    0.095, 0.1, 0.105, 0.11, 0.115, 0.12, 0.125, 0.13, 0.135, 0.14,
    0.2, 0.5, 1.0,
]

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
