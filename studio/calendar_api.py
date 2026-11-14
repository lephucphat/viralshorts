"""HTTP routes of the posting calendar, friend referrals and the help-center contact.

Kept in its own module and mounted from ``api.build_router`` (one ``include_router`` line), so
the account/projects router stays readable. Same conventions as ``api.py``: ``{"detail":
{"error", "message"}}`` errors, 404 for anything that belongs to someone else.
"""

import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import auth, referral, schedule
from .api import current_user, session_user


class PostBody(BaseModel):
    job_id: str
    clip_index: int = 0
    title: str = ""
    description: str = ""
    platforms: List[str]
    scheduled_for: float
    timezone: str = "UTC"


class PostPatch(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    platforms: Optional[List[str]] = None
    scheduled_for: Optional[float] = None
    timezone: Optional[str] = None

    def fields(self) -> dict:
        return self.model_dump(exclude_none=True) if hasattr(self, "model_dump") else self.dict(exclude_none=True)


class StatusBody(BaseModel):
    status: str
    vendor_job_id: Optional[str] = None
    error: str = ""


class AttachBody(BaseModel):
    code: str


def _fail(status: int, code: str, message: str):
    return HTTPException(status_code=status, detail={"error": code, "message": message})


def build_router() -> APIRouter:
    router = APIRouter()

    def _sched(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except schedule.ScheduleError as e:
            raise _fail(e.status, e.code, e.message)

    def _ref(fn, *args):
        try:
            return fn(*args)
        except referral.ReferralError as e:
            raise _fail(e.status, e.code, e.message)
        except auth.AuthError as e:                  # the attempt throttle
            raise _fail(e.status, e.code, e.message)

    # ---- posting calendar -------------------------------------------------------------
    @router.get("/api/calendar")
    def calendar_list(start: float, end: float, user: auth.User = Depends(current_user)):
        """Posts whose time falls in [start, end), as UTC epoch seconds (at most 62 days)."""
        return {"items": _sched(schedule.list_range, user.id, start, end)}

    @router.post("/api/calendar")
    def calendar_create(body: PostBody, user: auth.User = Depends(current_user)):
        return _sched(schedule.create, user.id, body.job_id, body.clip_index, body.title,
                      body.description, body.platforms, body.scheduled_for, body.timezone)

    @router.patch("/api/calendar/{post_id}")
    def calendar_update(post_id: int, body: PostPatch, user: auth.User = Depends(current_user)):
        return _sched(schedule.update, user.id, post_id, body.fields())

    @router.post("/api/calendar/{post_id}/status")
    def calendar_status(post_id: int, body: StatusBody, user: auth.User = Depends(current_user)):
        """The dashboard reports what Upload-Post said (scheduled, failed, cancelled, published)."""
        return _sched(schedule.set_status, user.id, post_id, body.status, body.vendor_job_id, body.error)

    @router.delete("/api/calendar/{post_id}")
    def calendar_delete(post_id: int, user: auth.User = Depends(current_user)):
        _sched(schedule.delete, user.id, post_id)
        return {"deleted": True}

    # ---- friend referrals --------------------------------------------------------------
    @router.get("/api/referral")
    def referral_status(user: auth.User = Depends(session_user)):
        return referral.status(user.id)

    @router.post("/api/referral/attach")
    def referral_attach(body: AttachBody, user: auth.User = Depends(session_user)):
        return _ref(referral.attach, user.id, body.code)

    # ---- help center -------------------------------------------------------------------
    @router.get("/api/help/contact")
    def help_contact():
        """Where support mail goes: the operator's SUPPORT_EMAIL (blank until it is set)."""
        return {"email": os.environ.get("SUPPORT_EMAIL", "").strip()}

    return router
