"""Step editor: instructions, checklist and the answers workers have to give."""

from fastapi import APIRouter, HTTPException, Request

from app.domain.process import MAX_ANSWERS
from app.models import StepTemplate
from app.services import steps
from app.services.workflow import WorkflowError
from app.web.deps import db_of, form_with_csrf, redirect, render, require

router = APIRouter(prefix="/schritte")


@router.get("")
def steps_list(request: Request):
    user, sess = require(request, "edit_steps")
    rows = [(s, steps.can_edit(user, s)) for s in steps.all_steps(db_of(request))]
    return render(request, "steps.html", user, sess, rows=rows)


def _step(request: Request, code: str) -> StepTemplate:
    step = db_of(request).get(StepTemplate, code.upper()[:10])
    if step is None:
        raise HTTPException(status_code=404)
    return step


@router.get("/{code}")
def step_edit(request: Request, code: str):
    user, sess = require(request, "edit_steps")
    step = _step(request, code)
    editable = steps.can_edit(user, step)
    answers = list(step.measurements or [])
    rows = answers + [{}] * max(0, min(MAX_ANSWERS, len(answers) + 2) - len(answers))
    return render(request, "step_edit.html", user, sess, step=step, spec=step, editable=editable, rows=rows,
                  revisions=steps.history(db_of(request), step.code))


@router.post("/{code}")
async def step_save(request: Request, code: str):
    user, sess = require(request, "edit_steps")
    form = await form_with_csrf(request, sess)
    db = db_of(request)
    step = _step(request, code)
    try:
        changed = steps.update_step(db, user, step, {k: str(v) for k, v in form.items()})
    except WorkflowError as e:
        db.rollback()
        return redirect(f"/schritte/{step.code}?err={e.key}")
    return redirect(f"/schritte/{step.code}?ok={'ok_step_saved' if changed else 'ok_no_change'}")
