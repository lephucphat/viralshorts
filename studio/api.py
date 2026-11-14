"""HTTP surface of the studio package.

``build_router(ctx)`` receives a small context from app.py (where job files and
the live job table live) so this package never imports the app.
"""

import os
import time
from dataclasses import dataclass
from typing import Callable, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

import urllib.parse

from . import account, apikeys, auth, brand_kits, drafts, google, inbox, lifecycle, collections, mailer, onboarding, preview, progress, projects, recipes, security, usage

LOGO_URL_TTL_SECONDS = 6 * 3600
# An active row nobody is working on for this long is an interrupted job.
STALE_ACTIVE_SECONDS = 180


@dataclass
class Context:
    """What the app lends the router.

    job_status(job_id)    -> live status string, or None if the job is unknown
    cancel_job(job_id)    -> True if a queued/running job was cancelled
    remove_job_files(id)  -> delete the job's output and upload files
    """
    job_status: Callable[[str], Optional[str]]
    cancel_job: Callable[[str], bool]
    remove_job_files: Callable[[str], None]
    job_logs: Optional[Callable[[str], Optional[list]]] = None   # log lines, for the progress readout


# --- request bodies ------------------------------------------------------------
class RegisterBody(BaseModel):
    email: str
    password: str
    name: str = ""
    lang: str = "vi"
    accept_terms: bool = False


class EmailChangeBody(BaseModel):
    email: str
    password: str = ""


class KeyBody(BaseModel):
    name: str = ""


class LoginBody(BaseModel):
    email: str
    password: str


class ProfileBody(BaseModel):
    name: Optional[str] = None
    lang: Optional[str] = None


class PasswordBody(BaseModel):
    current: str
    new: str


class DeleteAccountBody(BaseModel):
    password: str


class RenameBody(BaseModel):
    title: str


class InboxReadBody(BaseModel):
    id: Optional[int] = None


class DraftBody(BaseModel):
    kind: str = "thumbnails"
    data: dict = {}


class RecipeBody(BaseModel):
    name: str
    settings: dict = {}


class FavoriteBody(BaseModel):
    favorite: bool


class CollectionBody(BaseModel):
    name: str


class CollectionAddBody(BaseModel):
    job_id: str


class KitBody(BaseModel):
    name: Optional[str] = None
    logo_position: Optional[str] = None
    logo_opacity: Optional[float] = None
    logo_scale: Optional[float] = None
    primary_color: Optional[str] = None
    secondary_color: Optional[str] = None
    caption_preset: Optional[str] = None
    hook_style: Optional[str] = None
    layout: Optional[str] = None
    output_format: Optional[str] = None
    is_default: Optional[bool] = None

    def fields(self) -> dict:
        return self.model_dump(exclude_none=True) if hasattr(self, "model_dump") else self.dict(exclude_none=True)


# --- helpers ---------------------------------------------------------------------
def _fail(status: int, code: str, message: str):
    return HTTPException(status_code=status, detail={"error": code, "message": message})


def _ip(request: Request) -> str:
    return request.client.host if request.client else ""


def current_user(request: Request) -> auth.User:
    user = auth.user_from_request(request)
    if user is None:
        raise _fail(401, "unauthenticated", "Sign in to continue.")
    return user


def session_user(request: Request) -> auth.User:
    """Like ``current_user`` but refuses an API key: managing keys, exporting data or signing
    devices out must come from a signed-in person, never from a key that might have leaked."""
    if (request.headers.get("authorization") or "").lower().startswith("bearer vsk_"):
        raise _fail(403, "session_required", "Sign in to the dashboard to do this; an API key cannot.")
    return current_user(request)


def _api_access(user: auth.User) -> bool:
    """Whether the account's plan includes API access (always true outside paid mode)."""
    from . import plans
    return (not plans.paid_mode()) or plans.has_feature(user.plan, "api_access")


def _kit_view(kit: dict) -> dict:
    """Add the signed, header-free logo URL an <img> tag can load."""
    if kit.get("has_logo"):
        exp = int(time.time()) + LOGO_URL_TTL_SECONDS
        sig = security.sign_resource("logo", kit["id"], exp)
        kit = {**kit, "logo_url": f"/api/brand-kits/{kit['id']}/logo?exp={exp}&sig={sig}"}
    else:
        kit = {**kit, "logo_url": None}
    return kit


def build_router(ctx: Context) -> APIRouter:
    router = APIRouter()

    def _guard(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except auth.AuthError as e:
            raise _fail(e.status, e.code, e.message)
        except brand_kits.KitError as e:
            raise _fail(e.status, e.code, e.message)

    # ---- accounts ---------------------------------------------------------------
    @router.post("/api/auth/register")
    def register(body: RegisterBody, request: Request):
        if auth.terms_required() and not body.accept_terms:
            raise _fail(422, "terms_required", "Accept the terms of service to create an account.")
        user = _guard(auth.register, body.email, body.password, body.name, body.lang, _ip(request),
                      auth.terms_version() if body.accept_terms else "")
        lifecycle.background(lifecycle.send_verification, user.id)
        lifecycle.background(lifecycle.send_welcome, user.id)   # waits for verification when required
        return {"token": auth.issue_token(user), "user": user.public()}

    @router.post("/api/auth/login")
    def login(body: LoginBody, request: Request):
        user = _guard(auth.login, body.email, body.password, _ip(request))
        return {"token": auth.issue_token(user), "user": user.public()}

    # ---- Google sign-in ---------------------------------------------------------
    def _back(path: str) -> RedirectResponse:
        return RedirectResponse(google.frontend_url() + path, status_code=302)

    @router.get("/api/auth/google")
    def google_start(request: Request):
        if not google.enabled():
            raise _fail(404, "google_off", "Google sign-in is not configured.")
        try:
            auth.throttle(f"google:{_ip(request)}", 30, 600)
        except auth.AuthError:
            return _back("/#/login?error=too_many_attempts")
        state = google.make_state()
        response = RedirectResponse(google.authorize_url(request, state), status_code=302)
        secure = (request.url.scheme == "https"
                  or request.headers.get("x-forwarded-proto") == "https")
        response.set_cookie(google.STATE_COOKIE, state, max_age=google.STATE_TTL_SECONDS,
                            httponly=True, samesite="lax", secure=secure)
        return response

    @router.get("/api/auth/google/callback")
    def google_callback(request: Request, code: str = "", state: str = "", error: str = ""):
        if not google.enabled():
            raise _fail(404, "google_off", "Google sign-in is not configured.")
        if error:
            # The person pressed "Cancel" on Google's consent screen, usually.
            return _back("/#/login?error=google_denied")
        if not google.check_state(state, request.cookies.get(google.STATE_COOKIE, "")):
            return _back("/#/login?error=google_failed")
        try:
            profile = google.fetch_profile(code, google.redirect_uri(request))
            user = auth.login_with_google(
                profile["sub"], profile["email"], profile.get("name", ""),
                profile.get("picture", ""), profile.get("locale", ""))
        except google.GoogleError as e:
            return _back("/#/login?error=" + e.code)
        except auth.AuthError as e:
            return _back("/#/login?error=" + ("account_disabled" if e.code == "account_disabled"
                                              else "google_failed"))
        response = _back("/#/auth/callback?token=" + urllib.parse.quote(auth.issue_token(user)))
        response.delete_cookie(google.STATE_COOKIE)
        return response

    @router.get("/api/me")
    def me(user: auth.User = Depends(current_user)):
        return {"user": user.public(), "usage": usage.summary(user.id),
                "verification_required": mailer.verification_required()}

    @router.patch("/api/me")
    def update_me(body: ProfileBody, user: auth.User = Depends(current_user)):
        updated = _guard(auth.update_profile, user.id, body.name, body.lang)
        return {"user": updated.public()}

    @router.post("/api/me/password")
    def change_password(body: PasswordBody, user: auth.User = Depends(current_user)):
        updated = _guard(auth.change_password, user.id, body.current, body.new)
        lifecycle.background(lifecycle.send_password_changed, user.id)
        # Every older token just stopped working; hand back a fresh one.
        return {"token": auth.issue_token(updated), "user": updated.public()}

    @router.post("/api/me/logout-all")
    def logout_all(user: auth.User = Depends(session_user)):
        """Sign out every device (including leaked sessions); this one gets a fresh token."""
        updated = auth.logout_everywhere(user.id)
        return {"token": auth.issue_token(updated), "user": updated.public()}

    # ---- onboarding checklist ---------------------------------------------------------
    def _onboarding(fn, *args):
        try:
            return fn(*args)
        except onboarding.OnboardingError as e:
            raise _fail(e.status, e.code, e.message)

    @router.get("/api/me/onboarding")
    def onboarding_status(user: auth.User = Depends(current_user)):
        return _onboarding(onboarding.status, user.id)

    @router.post("/api/me/onboarding/dismiss")
    def onboarding_dismiss(user: auth.User = Depends(current_user)):
        return _onboarding(onboarding.dismiss, user.id)

    @router.post("/api/me/onboarding/{step}")
    def onboarding_report(step: str, user: auth.User = Depends(current_user)):
        return _onboarding(onboarding.report, user.id, step)

    @router.get("/api/me/export")
    def export_me(user: auth.User = Depends(session_user)):
        data = account.export_data(user.id)
        return JSONResponse(data, headers={
            "Content-Disposition": 'attachment; filename="viralshorts-my-data.json"'})

    @router.post("/api/me/email")
    def change_email(body: EmailChangeBody, user: auth.User = Depends(session_user)):
        """Ask to move the account to a new address. The old password (or, for a Google-only
        account, the typed current email) must be right; the new address gets a link."""
        _guard(auth.confirm_identity, user.id, body.password)
        _guard(lifecycle.request_email_change, user.id, body.email)
        return {"ok": True}

    # ---- API keys (programmatic API and MCP) ------------------------------------------
    def _keys_guard(fn, *args):
        try:
            return fn(*args)
        except apikeys.ApiKeyError as e:
            raise _fail(e.status, e.code, e.message)

    @router.get("/api/keys")
    def list_keys(user: auth.User = Depends(session_user)):
        return {"items": apikeys.list_for_user(user.id), "allowed": _api_access(user)}

    @router.post("/api/keys")
    def create_key(body: KeyBody, user: auth.User = Depends(session_user)):
        if not _api_access(user):
            raise HTTPException(status_code=402, detail={
                "error": "plan_required", "feature": "api_access",
                "message": "Your plan does not include API access. Upgrade to create keys."})
        return _keys_guard(apikeys.create, user.id, body.name)

    @router.delete("/api/keys/{key_id}")
    def delete_key(key_id: int, user: auth.User = Depends(session_user)):
        if not apikeys.revoke(user.id, key_id):
            raise _fail(404, "not_found", "Key not found.")
        return {"deleted": True}

    @router.delete("/api/me")
    def delete_me(body: DeleteAccountBody, user: auth.User = Depends(current_user)):
        # Prove it is the owner first, so a stolen token alone cannot cancel anything.
        _guard(auth.confirm_identity, user.id, body.password)
        # A card subscription renews itself: deleting the row would leave the card being
        # charged for an account that no longer exists. Cancel at Stripe first and refuse to
        # delete if that fails, so nobody pays for nothing.
        from .payments import service as billing, stripe_provider
        cancelled = False
        if stripe_provider.secret_key():
            for sub_id in billing.live_subscription_refs(user.id, "stripe"):
                try:
                    stripe_provider.cancel_subscription(sub_id)
                    cancelled = True
                except stripe_provider.StripeError:
                    raise _fail(502, "cancel_failed",
                                "We could not cancel your subscription with the payment provider, so "
                                "your account was not deleted. Try again in a moment or contact support.")
        job_ids = projects.job_ids_for_user(user.id)
        who = _guard(auth.delete_account, user.id, body.password)
        for job_id in job_ids:
            ctx.cancel_job(job_id)
            ctx.remove_job_files(job_id)
        lifecycle.background(lifecycle.send_account_deleted, who, cancelled)
        return {"deleted": True}

    @router.get("/api/usage")
    def get_usage(user: auth.User = Depends(current_user)):
        return usage.summary(user.id)

    # ---- projects ------------------------------------------------------------------
    def _with_progress(project: dict) -> dict:
        if ctx.job_logs is None:
            return project
        try:
            logs = ctx.job_logs(project["job_id"])
        except Exception:
            return project
        return {**project, "progress": progress.read(logs)} if logs is not None else project

    def _reconcile(project: dict) -> dict:
        """Bring a stale active row in line with what the job table says."""
        if project["status"] not in projects.ACTIVE:
            return project
        project = _with_progress(project)
        live = ctx.job_status(project["job_id"])
        if live in projects.TERMINAL:
            projects.set_status(project["job_id"], live)
            return {**project, "status": live}
        if live is None and time.time() - project["updated_at"] > STALE_ACTIVE_SECONDS:
            projects.set_status(project["job_id"], "failed")
            return {**project, "status": "failed"}
        if live and live != project["status"]:
            projects.set_status(project["job_id"], live)
            return {**project, "status": live}
        return project

    # ---- the bell ---------------------------------------------------------------------
    @router.get("/api/inbox")
    def get_inbox(user: auth.User = Depends(current_user)):
        return inbox.list_for_user(user.id)

    @router.post("/api/inbox/read")
    def read_inbox(body: InboxReadBody, user: auth.User = Depends(current_user)):
        return {"changed": inbox.mark_read(user.id, body.id)}

    # ---- tool drafts (unfinished work in a tool, listed under it) ---------------------
    @router.get("/api/drafts")
    def list_drafts(kind: str = "", user: auth.User = Depends(current_user)):
        return {"items": drafts.list_for_user(user.id, kind or None)}

    @router.get("/api/drafts/{draft_id}")
    def get_draft(draft_id: str, user: auth.User = Depends(current_user)):
        found = drafts.get(user.id, draft_id) if drafts.valid_id(draft_id) else None
        if found is None:
            raise _fail(404, "not_found", "Draft not found.")
        return found

    @router.put("/api/drafts/{draft_id}")
    def save_draft(draft_id: str, body: DraftBody, user: auth.User = Depends(current_user)):
        try:
            drafts.save(user.id, draft_id, body.kind, body.data)
        except drafts.DraftError as e:
            raise _fail(422 if str(e) == "too_big" else 400, str(e), "The draft was not saved.")
        return {"saved": True}

    @router.delete("/api/drafts/{draft_id}")
    def delete_draft(draft_id: str, user: auth.User = Depends(current_user)):
        if not drafts.valid_id(draft_id) or not drafts.delete(user.id, draft_id):
            raise _fail(404, "not_found", "Draft not found.")
        return {"deleted": True}

    # ---- recipes (saved create-project settings) --------------------------------------
    @router.get("/api/recipes")
    def list_recipes(user: auth.User = Depends(current_user)):
        return {"items": recipes.list_for_user(user.id)}

    @router.post("/api/recipes")
    def create_recipe(body: RecipeBody, user: auth.User = Depends(current_user)):
        try:
            return recipes.create(user.id, body.name, body.settings)
        except recipes.RecipeError as e:
            raise _fail(409 if e.code == "exists" else 400, e.code, str(e))

    @router.delete("/api/recipes/{recipe_id}")
    def delete_recipe(recipe_id: int, user: auth.User = Depends(current_user)):
        if not recipes.delete(user.id, recipe_id):
            raise _fail(404, "not_found", "Recipe not found.")
        return {"deleted": True}

    @router.get("/api/source/preview")
    def source_preview(request: Request, url: str = "", user: auth.User = Depends(current_user)):
        _guard(auth.throttle, f"preview:{user.id}", 40, 600)
        try:
            from security_utils import assert_public_url
        except Exception:                     # the module sits next to app.py, absent in unit tests
            assert_public_url = None
        try:
            return preview.fetch(url, check_url=assert_public_url)
        except preview.PreviewError as e:
            raise _fail(400 if e.code == "bad_url" else 422, e.code, str(e))

    @router.get("/api/projects")
    def list_projects(q: str = "", status: str = "", sort: str = "newest",
                      limit: int = 60, offset: int = 0,
                      favorite: bool = False, collection: Optional[int] = None,
                      user: auth.User = Depends(current_user)):
        page = projects.list_for_user(user.id, q=q, status=status, sort=sort,
                                      limit=limit, offset=offset, favorite=favorite,
                                      collection_id=collection)
        page["items"] = [_reconcile(p) for p in page["items"]]
        return page

    @router.get("/api/projects/{job_id}")
    def get_project(job_id: str, user: auth.User = Depends(current_user)):
        project = projects.get_for_user(user.id, job_id)
        if project is None:
            raise _fail(404, "not_found", "Project not found.")
        return _reconcile(project)

    @router.patch("/api/projects/{job_id}")
    def rename_project(job_id: str, body: RenameBody, user: auth.User = Depends(current_user)):
        project = projects.rename(user.id, job_id, body.title)
        if project is None:
            raise _fail(404, "not_found", "Project not found.")
        return project

    @router.put("/api/projects/{job_id}/favorite")
    def favorite_project(job_id: str, body: FavoriteBody, user: auth.User = Depends(current_user)):
        project = projects.set_favorite(user.id, job_id, body.favorite)
        if project is None:
            raise _fail(404, "not_found", "Project not found.")
        return project

    # ---- collections (named folders) -------------------------------------------------
    def _collection_guard(fn, *args):
        try:
            return fn(*args)
        except collections.CollectionError as e:
            status = 409 if e.code == "exists" else 400
            raise _fail(status, e.code, str(e))

    @router.get("/api/collections")
    def list_collections(user: auth.User = Depends(current_user)):
        return {"items": collections.list_for_user(user.id)}

    @router.post("/api/collections")
    def create_collection(body: CollectionBody, user: auth.User = Depends(current_user)):
        return _collection_guard(collections.create, user.id, body.name)

    @router.patch("/api/collections/{collection_id}")
    def rename_collection(collection_id: int, body: CollectionBody, user: auth.User = Depends(current_user)):
        found = _collection_guard(collections.rename, user.id, collection_id, body.name)
        if found is None:
            raise _fail(404, "not_found", "Collection not found.")
        return found

    @router.delete("/api/collections/{collection_id}")
    def delete_collection(collection_id: int, user: auth.User = Depends(current_user)):
        if not collections.delete(user.id, collection_id):
            raise _fail(404, "not_found", "Collection not found.")
        return {"deleted": True}

    @router.post("/api/collections/{collection_id}/projects")
    def add_to_collection(collection_id: int, body: CollectionAddBody, user: auth.User = Depends(current_user)):
        if not collections.add(user.id, collection_id, body.job_id):
            raise _fail(404, "not_found", "Collection or project not found.")
        return {"added": True}

    @router.delete("/api/collections/{collection_id}/projects/{job_id}")
    def remove_from_collection(collection_id: int, job_id: str, user: auth.User = Depends(current_user)):
        if not collections.remove(user.id, collection_id, job_id):
            raise _fail(404, "not_found", "Project not found.")
        return {"removed": True}

    @router.get("/api/projects/{job_id}/collections")
    def project_collections(job_id: str, user: auth.User = Depends(current_user)):
        if projects.get_for_user(user.id, job_id) is None:
            raise _fail(404, "not_found", "Project not found.")
        return {"ids": collections.for_project(user.id, job_id)}

    @router.delete("/api/projects/{job_id}")
    def delete_project(job_id: str, user: auth.User = Depends(current_user)):
        row = projects.delete(user.id, job_id)
        if row is None:
            raise _fail(404, "not_found", "Project not found.")
        ctx.cancel_job(job_id)
        ctx.remove_job_files(job_id)
        return {"deleted": True}

    @router.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str, user: auth.User = Depends(current_user)):
        if projects.get_for_user(user.id, job_id) is None:
            raise _fail(404, "not_found", "Project not found.")
        cancelled = ctx.cancel_job(job_id)
        if cancelled:
            projects.set_status(job_id, "cancelled")
        return {"cancelled": cancelled}

    # ---- brand kits ------------------------------------------------------------------
    @router.get("/api/brand-kits")
    def list_kits(user: auth.User = Depends(current_user)):
        return {"items": [_kit_view(k) for k in brand_kits.list_for_user(user.id)]}

    @router.post("/api/brand-kits")
    def create_kit(body: KitBody, user: auth.User = Depends(current_user)):
        return _kit_view(_guard(brand_kits.create, user.id, body.fields()))

    @router.patch("/api/brand-kits/{kit_id}")
    def update_kit(kit_id: int, body: KitBody, user: auth.User = Depends(current_user)):
        kit = _guard(brand_kits.update, user.id, kit_id, body.fields())
        if kit is None:
            raise _fail(404, "not_found", "Brand kit not found.")
        return _kit_view(kit)

    @router.delete("/api/brand-kits/{kit_id}")
    def delete_kit(kit_id: int, user: auth.User = Depends(current_user)):
        if not brand_kits.delete(user.id, kit_id):
            raise _fail(404, "not_found", "Brand kit not found.")
        return {"deleted": True}

    @router.post("/api/brand-kits/{kit_id}/logo")
    async def upload_logo(kit_id: int, file: UploadFile = File(...),
                          user: auth.User = Depends(current_user)):
        raw = await file.read(brand_kits.MAX_LOGO_BYTES + 1)
        kit = _guard(brand_kits.save_logo, user.id, kit_id, raw)
        if kit is None:
            raise _fail(404, "not_found", "Brand kit not found.")
        return _kit_view(kit)

    @router.delete("/api/brand-kits/{kit_id}/logo")
    def delete_logo(kit_id: int, user: auth.User = Depends(current_user)):
        kit = brand_kits.remove_logo(user.id, kit_id)
        if kit is None:
            raise _fail(404, "not_found", "Brand kit not found.")
        return _kit_view(kit)

    @router.get("/api/brand-kits/{kit_id}/logo")
    def get_logo(kit_id: int, exp: int = 0, sig: str = ""):
        # An <img> cannot send an Authorization header, so access is proven by
        # the short-lived signature that _kit_view put in the URL.
        if not security.check_resource("logo", kit_id, exp, sig):
            raise _fail(404, "not_found", "Logo not found.")
        path = brand_kits.logo_path_any(kit_id)
        if not path or not os.path.exists(path):
            raise _fail(404, "not_found", "Logo not found.")
        return FileResponse(path, media_type="image/png",
                            headers={"Cache-Control": "private, max-age=300"})

    # Posting calendar, friend referrals, help contact (module imports this one, so import late).
    from . import calendar_api
    router.include_router(calendar_api.build_router())

    return router
