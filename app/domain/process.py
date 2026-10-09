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
        if d.get("kind") == "text":  # free text answer, e.g. a software version: required, no range
            answer = str(raw.get(d["key"], "")).strip()[:200]
            if answer:
                values[d["key"]] = answer
            else:
                invalid.append(d["key"])
            continue
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


def in_range(definition: dict, value) -> bool | None:
    if value is None:
        return None
    if definition.get("kind") == "text":
        return bool(value)
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


MAX_CHECKLIST, MAX_ANSWERS = 12, 8


def _slug(text: str, used: set[str]) -> str:
    text = text.lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(a, b)
    base = "".join(c if c.isascii() and c.isalnum() else "_" for c in text).strip("_")[:24] or "wert"
    key, n = base, 2
    while key in used:
        key, n = f"{base}_{n}", n + 1
    used.add(key)
    return key


def parse_step_spec(form: Mapping[str, str], current: list[dict]) -> tuple[dict, list[str]]:
    """Validates what a team lead entered in the step editor.
    Returns (spec, errors). Existing answer keys are kept so stored values stay comparable."""
    errors: list[str] = []
    instr_de = str(form.get("instructions_de", "")).strip()[:1000]
    instr_en = str(form.get("instructions_en", "")).strip()[:1000] or instr_de
    if not instr_de:
        errors.append("err_step_instructions")
    lines = lambda name: [x.strip()[:200] for x in str(form.get(name, "")).splitlines() if x.strip()]  # noqa: E731
    check_de, check_en = lines("checklist_de"), lines("checklist_en")
    if not check_de or len(check_de) > MAX_CHECKLIST:
        errors.append("err_step_checklist")
    if check_en and len(check_en) != len(check_de):
        errors.append("err_step_checklist_en")
    check_en = check_en or list(check_de)
    used: set[str] = set()
    answers: list[dict] = []
    for i in range(MAX_ANSWERS):
        label_de = str(form.get(f"a{i}_label_de", "")).strip()[:80]
        if not label_de:
            continue
        kind = "text" if form.get(f"a{i}_kind") == "text" else "number"
        old_key = str(form.get(f"a{i}_key", ""))
        key = old_key if old_key and old_key in {c["key"] for c in current} and old_key not in used else _slug(label_de, used)
        used.add(key)
        answer = {"key": key, "label_de": label_de, "label_en": str(form.get(f"a{i}_label_en", "")).strip()[:80] or label_de, "kind": kind,
                  "unit": str(form.get(f"a{i}_unit", "")).strip()[:12]}
        if kind == "number":
            try:
                lo = float(str(form.get(f"a{i}_min", "")).replace(",", "."))
                hi = float(str(form.get(f"a{i}_max", "")).replace(",", "."))
            except ValueError:
                errors.append("err_step_range")
                continue
            if not lo < hi:
                errors.append("err_step_range")
                continue
            answer.update({"min": lo, "max": hi})
        answers.append(answer)
    spec = {"instructions_de": instr_de, "instructions_en": instr_en, "checklist_de": check_de, "checklist_en": check_en, "measurements": answers}
    return spec, sorted(set(errors))
