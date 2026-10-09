"""Pure process rules: dependencies, readiness, progress. No framework or database imports."""

from collections.abc import Iterable, Mapping

WAITING, READY, IN_PROGRESS, PASS, FAIL, BLOCKED = "WAITING", "READY", "IN_PROGRESS", "PASS", "FAIL", "BLOCKED"
ALL_STATUSES = (WAITING, READY, IN_PROGRESS, PASS, FAIL, BLOCKED)
RESULT_STATUSES = (PASS, FAIL, BLOCKED)
OPEN_STATUSES = (READY, IN_PROGRESS, FAIL, BLOCKED)
STARTED_STATUSES = (IN_PROGRESS, PASS, FAIL, BLOCKED)


def dependents(deps: Mapping[str, Iterable[str]], step: str) -> list[str]:
    """Steps that directly depend on `step`."""
    return sorted(s for s, d in deps.items() if step in d)


def downstream(deps: Mapping[str, Iterable[str]], step: str) -> list[str]:
    """All steps that (directly or indirectly) wait for `step`."""
    seen: set[str] = set()
    todo = [step]
    while todo:
        for nxt in dependents(deps, todo.pop()):
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    return sorted(seen)


def newly_ready(deps: Mapping[str, Iterable[str]], statuses: Mapping[str, str], finished: str) -> list[str]:
    """Steps that become startable because `finished` passed: all their dependencies are PASS
    and they are still WAITING. Handles parallel branches (a join waits for every branch)."""
    return [
        s
        for s in dependents(deps, finished)
        if statuses.get(s) == WAITING and all(statuses.get(d) == PASS for d in deps[s])
    ]


def initial_ready(deps: Mapping[str, Iterable[str]]) -> list[str]:
    return sorted(s for s, d in deps.items() if not list(d))


def progress_pct(statuses: Iterable[str]) -> int:
    values = list(statuses)
    return round(100 * sum(1 for s in values if s == PASS) / len(values)) if values else 0


def is_released(statuses: Iterable[str]) -> bool:
    values = list(statuses)
    return bool(values) and all(s == PASS for s in values)


def validate_dependencies(deps: Mapping[str, Iterable[str]]) -> None:
    """Raise ValueError for unknown references or cycles (protects the process configuration)."""
    for step, d in deps.items():
        for ref in d:
            if ref not in deps:
                raise ValueError(f"{step} depends on unknown step {ref}")
    state: dict[str, int] = {}

    def visit(node: str) -> None:
        if state.get(node) == 1:
            raise ValueError(f"cycle at {node}")
        if state.get(node) == 2:
            return
        state[node] = 1
        for ref in deps[node]:
            visit(ref)
        state[node] = 2

    for step in deps:
        visit(step)


def can_reopen(deps: Mapping[str, Iterable[str]], statuses: Mapping[str, str], step: str) -> bool:
    """A passed step may be reopened only while no following step has been started."""
    return statuses.get(step) == PASS and not any(statuses.get(s) in STARTED_STATUSES for s in downstream(deps, step))


def check_values(definitions: list[dict], raw: Mapping[str, str]) -> tuple[dict[str, float], list[str], list[str]]:
    """Parses measured values against their definitions.
    Returns (values, out_of_range_keys, missing_or_invalid_keys). Accepts "1,5" and "1.5"."""
    values: dict[str, float] = {}
    out_of_range: list[str] = []
    invalid: list[str] = []
    for d in definitions:
        text = str(raw.get(d["key"], "")).strip().replace(",", ".")
        try:
            number = float(text)
        except ValueError:
            invalid.append(d["key"])
            continue
        if number != number or number in (float("inf"), float("-inf")):  # NaN / inf
            invalid.append(d["key"])
            continue
        values[d["key"]] = number
        if not (d["min"] <= number <= d["max"]):
            out_of_range.append(d["key"])
    return values, out_of_range, invalid


def in_range(definition: dict, value: float | None) -> bool | None:
    if value is None:
        return None
    return definition["min"] <= value <= definition["max"]


def working_seconds(started, finished, paused_seconds: int, paused_at, now) -> int | None:
    """Active working time: from start to finish (or now), minus pauses."""
    if started is None:
        return None
    end = finished or now
    pause = paused_seconds + (int((now - paused_at).total_seconds()) if paused_at and not finished else 0)
    return max(0, int((end - started).total_seconds()) - pause)


def waiting_seconds(ready, started, now) -> int | None:
    """Waiting time: from 'ready' until somebody started (or until now if still waiting)."""
    if ready is None:
        return None
    return max(0, int(((started or now) - ready).total_seconds()))


def flow_ratio(processing: float, waiting: float) -> float | None:
    """Flussgrad = processing time / lead time (processing + waiting)."""
    total = processing + waiting
    return processing / total if total > 0 else None
