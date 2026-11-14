"""Routes for the email-driven parts of an account: forgot/reset password and verification."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from . import auth, lifecycle, mailer
from .api import current_user


class ForgotBody(BaseModel):
    email: str


class ResetBody(BaseModel):
    token: str
    password: str


class TokenBody(BaseModel):
    token: str


def _fail(e: auth.AuthError):
    return HTTPException(status_code=e.status, detail={"error": e.code, "message": e.message})


def build_router() -> APIRouter:
    router = APIRouter()

    @router.post("/api/auth/forgot")
    def forgot(body: ForgotBody, request: Request):
        ip = request.client.host if request.client else ""
        try:
            lifecycle.request_reset(body.email, ip)
        except auth.AuthError as e:
            raise _fail(e)
        # Same answer for an unknown address, a throttled one and a real one.
        return {"ok": True}

    @router.post("/api/auth/reset")
    def reset(body: ResetBody, request: Request):
        ip = request.client.host if request.client else ""
        try:
            auth.throttle(f"reset:{ip}", 20, 3600)
            user = lifecycle.reset_password(body.token, body.password)
        except auth.AuthError as e:
            raise _fail(e)
        return {"token": auth.issue_token(user), "user": user.public()}

    @router.post("/api/auth/verify")
    def verify(body: TokenBody, request: Request):
        ip = request.client.host if request.client else ""
        try:
            auth.throttle(f"verify:{ip}", 30, 3600)
            user = lifecycle.verify_email(body.token)
        except auth.AuthError as e:
            raise _fail(e)
        return {"verified": True, "user": user.public()}

    @router.post("/api/auth/verify/resend")
    def resend_public(body: ForgotBody, request: Request):
        """For a visitor whose verification link expired and who cannot sign in to ask for a
        new one. The same quiet answer whether or not the address has an account."""
        ip = request.client.host if request.client else ""
        try:
            lifecycle.resend_verification_for(body.email, ip)
        except auth.AuthError as e:
            raise _fail(e)
        return {"ok": True}

    @router.post("/api/me/verify/resend")
    def resend(user: auth.User = Depends(current_user)):
        try:
            auth.throttle(f"resend:{user.id}", 3, 3600)
        except auth.AuthError as e:
            raise _fail(e)
        if user.email_verified:
            return {"sent": False, "reason": "already_verified"}
        if not mailer.enabled():
            return {"sent": False, "reason": "mail_off"}
        lifecycle.background(lifecycle.send_verification, user.id)
        return {"sent": True}

    return router
