"""Outgoing email over plain SMTP (stdlib only) and the message templates.

Configured with ``SMTP_HOST`` (+ ``SMTP_PORT``, ``SMTP_USER``, ``SMTP_PASSWORD``,
``SMTP_FROM``, ``SMTP_SECURITY`` = starttls | ssl | none). Without ``SMTP_HOST`` nothing
is sent: the product keeps working and the features that need an inbox (the
"verify your email" requirement) switch themselves off, so a development machine
does not need a mail server.

Sending never blocks a request: ``send_async`` hands the message to a daemon
thread. Callers that must know whether it went out (the receipts sweep retries on
failure) use ``send``.
"""

import logging
import os
import smtplib
import threading
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
from typing import Optional

log = logging.getLogger("studio.mail")

# Tests flip this so the "background" send happens before the assertion.
SYNC = False


def enabled() -> bool:
    return bool(os.environ.get("SMTP_HOST", "").strip())


def verification_required() -> bool:
    """New password accounts must prove their inbox before they get free credits.
    Only enforced when mail can actually be delivered; ``REQUIRE_VERIFIED_EMAIL=0``
    turns it off even then."""
    return enabled() and os.environ.get("REQUIRE_VERIFIED_EMAIL", "1").strip().lower() not in ("0", "false", "no")


def _sender() -> str:
    addr = os.environ.get("SMTP_FROM", "").strip() or os.environ.get("SMTP_USER", "").strip() or "no-reply@localhost"
    name = os.environ.get("SMTP_FROM_NAME", "ViralShorts").strip()
    return formataddr((name, addr)) if "<" not in addr else addr


def _deliver(msg: EmailMessage) -> None:
    """The one place that touches the network. Tests replace it."""
    host = os.environ["SMTP_HOST"].strip()
    security = os.environ.get("SMTP_SECURITY", "starttls").strip().lower()
    port = int(os.environ.get("SMTP_PORT") or (465 if security == "ssl" else 587))
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "")
    if security == "ssl":
        server = smtplib.SMTP_SSL(host, port, timeout=15)
    else:
        server = smtplib.SMTP(host, port, timeout=15)
    try:
        if security == "starttls":
            server.starttls()
        if user:
            server.login(user, password)
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except smtplib.SMTPException:
            pass


def send(to: str, subject: str, text: str, html: Optional[str] = None) -> bool:
    """Send one message. True if the SMTP server accepted it."""
    if not enabled():
        if os.environ.get("STUDIO_DEV_MAIL_LOG", "").lower() in ("1", "true", "yes"):
            log.warning("mail not configured; would send to %s: %s\n%s", to, subject, text)
        return False
    msg = EmailMessage()
    msg["From"] = _sender()
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    try:
        _deliver(msg)
        return True
    except Exception as e:           # a mail outage must never break signup or a webhook
        log.warning("mail to %s failed: %s", to, e)
        return False


def send_async(to: str, subject: str, text: str, html: Optional[str] = None) -> None:
    if SYNC:
        send(to, subject, text, html)
        return
    threading.Thread(target=send, args=(to, subject, text, html), daemon=True).start()


# ---- templates ----------------------------------------------------------------------------
def _page(lang: str, title: str, lines: list, button: Optional[tuple] = None) -> tuple:
    """(text, html) for a short transactional message."""
    text = "\n\n".join(lines)
    if button:
        text += f"\n\n{button[0]}: {button[1]}"
    text += "\n\n-- ViralShorts"
    body = "".join(f"<p style='margin:0 0 14px'>{escape(l)}</p>" for l in lines)
    if button:
        body += (f"<p style='margin:22px 0'><a href='{escape(button[1], quote=True)}' "
                 "style='background:#111;color:#fff;padding:11px 20px;border-radius:999px;"
                 f"text-decoration:none;display:inline-block'>{escape(button[0])}</a></p>"
                 f"<p style='color:#777;font-size:12px'>{escape(button[1])}</p>")
    html = ("<div style='font-family:system-ui,Segoe UI,Arial,sans-serif;max-width:520px;margin:auto;"
            f"color:#222;line-height:1.55'><h2 style='font-weight:600'>{escape(title)}</h2>{body}"
            "<p style='color:#999;font-size:12px;margin-top:28px'>ViralShorts</p></div>")
    return text, html


def _lang(lang: str) -> str:
    return "en" if lang == "en" else "vi"


def verify_message(lang: str, name: str, link: str) -> tuple:
    if _lang(lang) == "en":
        t = _page("en", "Confirm your email", [f"Hi {name},", "Confirm this address to activate your free credits."],
                  ("Confirm email", link))
        return "Confirm your ViralShorts email", *t
    t = _page("vi", "Xác nhận email", [f"Chào {name},", "Hãy xác nhận địa chỉ email này để nhận credit miễn phí."],
              ("Xác nhận email", link))
    return "Xác nhận email ViralShorts của bạn", *t


def reset_message(lang: str, name: str, link: str) -> tuple:
    if _lang(lang) == "en":
        t = _page("en", "Reset your password",
                  [f"Hi {name},", "Use the button to choose a new password. The link works once and expires in 1 hour.",
                   "If you did not ask for this, ignore this email: your password has not changed."],
                  ("Choose a new password", link))
        return "Reset your ViralShorts password", *t
    t = _page("vi", "Đặt lại mật khẩu",
              [f"Chào {name},", "Bấm nút để chọn mật khẩu mới. Liên kết chỉ dùng được một lần và hết hạn sau 1 giờ.",
               "Nếu bạn không yêu cầu, hãy bỏ qua email này: mật khẩu của bạn chưa bị đổi."],
              ("Chọn mật khẩu mới", link))
    return "Đặt lại mật khẩu ViralShorts", *t


def receipt_message(lang: str, name: str, what: str, amount: str, credits: int, date: str, link: str) -> tuple:
    if _lang(lang) == "en":
        t = _page("en", "Payment received",
                  [f"Hi {name},", f"Thanks. We received your payment for {what}.",
                   f"Amount: {amount}", f"Credits added: {credits}", f"Date: {date}"],
                  ("Open your account", link))
        return "Your ViralShorts receipt", *t
    t = _page("vi", "Đã nhận thanh toán",
              [f"Chào {name},", f"Cảm ơn bạn. Chúng tôi đã nhận thanh toán cho {what}.",
               f"Số tiền: {amount}", f"Credit được cộng: {credits}", f"Ngày: {date}"],
              ("Mở tài khoản", link))
    return "Biên nhận thanh toán ViralShorts", *t


def payment_failed_message(lang: str, name: str, plan: str, link: str) -> tuple:
    if _lang(lang) == "en":
        t = _page("en", "Your payment did not go through",
                  [f"Hi {name},", f"We could not renew your {plan} plan: the card payment failed.",
                   "Your plan stays active for a few days while the bank retries. Update your card to avoid losing it."],
                  ("Update payment method", link))
        return "ViralShorts: your payment failed", *t
    t = _page("vi", "Thanh toán chưa thành công",
              [f"Chào {name},", f"Chúng tôi chưa gia hạn được gói {plan}: thanh toán bằng thẻ bị từ chối.",
               "Gói của bạn vẫn dùng được trong vài ngày trong lúc ngân hàng thử lại. Hãy cập nhật thẻ để không bị mất gói."],
              ("Cập nhật thẻ", link))
    return "ViralShorts: thanh toán của bạn chưa thành công", *t


def plan_expiring_message(lang: str, name: str, plan: str, date: str, link: str) -> tuple:
    if _lang(lang) == "en":
        t = _page("en", "Your plan ends soon",
                  [f"Hi {name},", f"Your {plan} plan ends on {date}. It does not renew by itself.",
                   "Buy it again before then to keep your plan features and get the next credits."],
                  ("Renew plan", link))
        return "ViralShorts: your plan ends soon", *t
    t = _page("vi", "Gói sắp hết hạn",
              [f"Chào {name},", f"Gói {plan} của bạn hết hạn vào {date} và không tự gia hạn.",
               "Hãy mua lại trước thời điểm đó để giữ tính năng của gói và nhận credit kỳ tiếp theo."],
              ("Gia hạn gói", link))
    return "ViralShorts: gói của bạn sắp hết hạn", *t


def plan_ended_message(lang: str, name: str, plan: str, link: str) -> tuple:
    if _lang(lang) == "en":
        t = _page("en", "Your plan has ended",
                  [f"Hi {name},", f"Your {plan} plan has ended and your account is back on the free plan.",
                   "Your projects are kept. Choose a plan to get your features and credits back."],
                  ("See plans", link))
        return "ViralShorts: your plan has ended", *t
    t = _page("vi", "Gói đã hết hạn",
              [f"Chào {name},", f"Gói {plan} của bạn đã hết hạn, tài khoản đã về gói miễn phí.",
               "Các dự án vẫn được giữ. Hãy chọn một gói để lấy lại tính năng và credit."],
              ("Xem các gói", link))
    return "ViralShorts: gói của bạn đã hết hạn", *t


def email_change_message(lang: str, name: str, new_email: str, link: str) -> tuple:
    if _lang(lang) == "en":
        t = _page("en", "Confirm your new email",
                  [f"Hi {name},", f"Confirm {new_email} as the email address of your ViralShorts account.",
                   "The link works once and expires in 1 hour. You will be signed out on all devices afterwards.",
                   "If you did not ask for this, ignore this email: nothing changes."],
                  ("Confirm new email", link))
        return "Confirm your new ViralShorts email", *t
    t = _page("vi", "Xác nhận email mới",
              [f"Chào {name},", f"Hãy xác nhận {new_email} là địa chỉ email của tài khoản ViralShorts.",
               "Liên kết chỉ dùng được một lần và hết hạn sau 1 giờ. Sau đó bạn sẽ bị đăng xuất khỏi mọi thiết bị.",
               "Nếu bạn không yêu cầu, hãy bỏ qua email này: không có gì thay đổi."],
              ("Xác nhận email mới", link))
    return "Xác nhận email mới cho ViralShorts", *t


def email_changed_notice(lang: str, name: str, new_email: str) -> tuple:
    if _lang(lang) == "en":
        t = _page("en", "Your email was changed",
                  [f"Hi {name},", f"The email address of your ViralShorts account was changed to {new_email}.",
                   "If this was not you, contact support right away."])
        return "Your ViralShorts email address was changed", *t
    t = _page("vi", "Email tài khoản đã thay đổi",
              [f"Chào {name},", f"Địa chỉ email của tài khoản ViralShorts đã được đổi thành {new_email}.",
               "Nếu đó không phải bạn, hãy liên hệ hỗ trợ ngay."])
    return "Email tài khoản ViralShorts đã được đổi", *t


def password_changed_message(lang: str, name: str, link: str) -> tuple:
    if _lang(lang) == "en":
        t = _page("en", "Your password was changed",
                  [f"Hi {name},", "The password of your ViralShorts account was just changed and you were signed out of other devices.",
                   "If this was not you, reset your password now and contact support."],
                  ("Reset password", link))
        return "Your ViralShorts password was changed", *t
    t = _page("vi", "Mật khẩu đã thay đổi",
              [f"Chào {name},", "Mật khẩu tài khoản ViralShorts vừa được đổi và các thiết bị khác đã bị đăng xuất.",
               "Nếu đó không phải bạn, hãy đặt lại mật khẩu ngay và liên hệ hỗ trợ."],
              ("Đặt lại mật khẩu", link))
    return "Mật khẩu ViralShorts đã được đổi", *t


def account_deleted_message(lang: str, name: str, subscription_cancelled: bool) -> tuple:
    if _lang(lang) == "en":
        lines = [f"Hi {name},", "Your ViralShorts account and its projects have been deleted."]
        if subscription_cancelled:
            lines.append("Your card subscription was cancelled, so you will not be charged again.")
        lines.append("Records of past payments are kept for accounting, without your profile.")
        t = _page("en", "Account deleted", lines)
        return "Your ViralShorts account was deleted", *t
    lines = [f"Chào {name},", "Tài khoản ViralShorts của bạn và các dự án đã được xoá."]
    if subscription_cancelled:
        lines.append("Gói thanh toán bằng thẻ của bạn đã được huỷ, bạn sẽ không bị trừ tiền thêm.")
    lines.append("Chúng tôi chỉ giữ lại bản ghi các khoản thanh toán đã qua để phục vụ kế toán, không kèm hồ sơ cá nhân của bạn.")
    t = _page("vi", "Đã xoá tài khoản", lines)
    return "Tài khoản ViralShorts của bạn đã được xoá", *t


def low_credit_message(lang: str, name: str, left: int, link: str) -> tuple:
    if _lang(lang) == "en":
        t = _page("en", "Your credits are running low",
                  [f"Hi {name},", f"You have {left} credits left. A new project may stop for lack of credits."],
                  ("Top up or upgrade", link))
        return "ViralShorts: your credits are running low", *t
    t = _page("vi", "Credit sắp hết",
              [f"Chào {name},", f"Bạn còn {left} credit. Dự án mới có thể không chạy được vì thiếu credit."],
              ("Nạp credit hoặc nâng cấp", link))
    return "ViralShorts: credit của bạn sắp hết", *t


def welcome_message(lang: str, name: str, link: str) -> tuple:
    if _lang(lang) == "en":
        t = _page("en", "Welcome to ViralShorts",
                  [f"Hi {name},",
                   "Your account is ready. Paste a video link or upload a file and ViralShorts will cut it "
                   "into vertical clips, with captions, a hook and a score for each one.",
                   "A short checklist on your projects page walks you through the first steps."],
                  ("Create your first clips", link))
        return "Welcome to ViralShorts", *t
    t = _page("vi", "Chào mừng đến với ViralShorts",
              [f"Chào {name},",
               "Tài khoản của bạn đã sẵn sàng. Dán link video hoặc tải file lên, ViralShorts sẽ cắt thành "
               "các clip dọc, kèm phụ đề, hook và điểm cho từng clip.",
               "Trang Dự án có một danh sách việc nhỏ dẫn bạn qua các bước đầu tiên."],
              ("Tạo clip đầu tiên", link))
    return "Chào mừng đến với ViralShorts", *t
