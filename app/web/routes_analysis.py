"""Private process-analysis workbook (value stream analysis, Gemba, PDCA, KPIs)."""

import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select

from app.config import settings
from app.domain import analysis as A
from app.models import AnalysisEntry, AnalysisRevision
from app.services import analysis, metrics
from app.services.analysis import AnalysisError
from app.web.deps import db_of, form_with_csrf, redirect, render, require

router = APIRouter(prefix="/analyse")


@router.get("")
def overview(request: Request):
    user, sess = require(request, "use_analysis")
    db = db_of(request)
    steps = [e.data for e in analysis.entries(db, "step")]
    live = metrics.step_times(db)
    counts = {key: len(analysis.entries(db, key)) for key in A.SECTIONS}
    recent = list(db.scalars(select(AnalysisRevision).order_by(AnalysisRevision.id.desc()).limit(10)))
    return render(request, "analysis_overview.html", user, sess, sections=A.SECTIONS, counts=counts, kpi=A.step_kpis(steps),
                  project=analysis.single(db, "project"), target=analysis.single(db, "target"), live=live, live_total=metrics.totals(live),
                  recent=recent, ephemeral=settings.database_url.startswith("sqlite") and settings.cookie_secure)


@router.get("/export.json")
def export(request: Request):
    user, _ = require(request, "use_analysis")
    data = analysis.export(db_of(request), user)
    return Response(json.dumps(data, ensure_ascii=False, indent=2), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="prozessanalyse.json"'})


@router.get("/eintrag/{entry_id}/verlauf")
def history(request: Request, entry_id: int):
    user, sess = require(request, "use_analysis")
    entry = db_of(request).get(AnalysisEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404)
    return render(request, "analysis_history.html", user, sess, entry=entry, section=A.SECTIONS[entry.section], section_key=entry.section)


@router.post("/eintrag/{entry_id}/{action}")
async def archive(request: Request, entry_id: int, action: str):
    user, sess = require(request, "use_analysis")
    await form_with_csrf(request, sess)
    if action not in ("archivieren", "wiederherstellen"):
        raise HTTPException(status_code=404)
    try:
        entry = analysis.set_archived(db_of(request), user, entry_id, action == "archivieren")
    except AnalysisError as e:
        raise HTTPException(status_code=404) from e
    return redirect(f"/analyse/{entry.section}?ok=ok_saved")


@router.get("/{section}")
def section_page(request: Request, section: str):
    user, sess = require(request, "use_analysis")
    if section not in A.SECTIONS:
        raise HTTPException(status_code=404)
    db = db_of(request)
    cfg = A.SECTIONS[section]
    edit = None
    if cfg["single"]:
        edit = analysis.single(db, section)
    elif request.query_params.get("edit", "").isdigit():
        edit = db.get(AnalysisEntry, int(request.query_params["edit"]))
        edit = edit if edit and edit.section == section else None
    rows = analysis.entries(db, section)
    archived = analysis.entries(db, section, archived=True)
    kpi = A.step_kpis([r.data for r in rows]) if section == "step" else None
    return render(request, "analysis_section.html", user, sess, section_key=section, section=cfg, rows=rows, archived=archived, edit=edit, kpi=kpi,
                  sections=A.SECTIONS)


@router.post("/{section}")
async def section_save(request: Request, section: str):
    user, sess = require(request, "use_analysis")
    form = await form_with_csrf(request, sess)
    if section not in A.SECTIONS:
        raise HTTPException(status_code=404)
    raw_id = str(form.get("entry_id", ""))
    try:
        analysis.save(db_of(request), user, section, {k: v for k, v in form.items()}, int(raw_id) if raw_id.isdigit() else None)
    except AnalysisError as e:
        return redirect(f"/analyse/{section}?err={e.key}" + (f"&edit={raw_id}" if raw_id.isdigit() else ""))
    return redirect(f"/analyse/{section}?ok=ok_saved")
