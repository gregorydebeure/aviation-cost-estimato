"""Menkor — account security and account e-mails (v20.4).

Pure logic with INJECTED transport (`post(url, headers=, json=, timeout=) -> response with .status_code/.text`): nothing here talks to the network by itself,
and tests never send a real e-mail.

Passwords: salted scrypt (standard library, no extra dependency). Accounts created before v20.4 hold an unsalted SHA-256 hash: they keep working and are
re-hashed with scrypt at their next successful login, so nobody is locked out. A wrong password is never stored or logged.
Lockout: 5 failed attempts lock the account for 15 minutes (needs the `failed_attempts` / `locked_until` columns of the lot-D migration; without them
the app still works but without lockout).
E-mails: the confirmation e-mail to a user needs a sender address of a domain verified at the e-mail provider (secret EMAIL_FROM); the provider's test sender
can only write to the provider account owner. Nothing is ever reported as sent unless the provider answered 2xx.
"""
from __future__ import annotations
import base64, datetime as _dt, hashlib, hmac, html as _html, os

SCRYPT_N = 2 ** 15; SCRYPT_R = 8; SCRYPT_P = 3; DKLEN = 32; MAXMEM = 128 * 1024 * 1024
PREFIX = "scrypt$"
MAX_FAILED = 5
LOCK_MINUTES = 15
TEST_SENDER = "Aviation Cost Estimator <onboarding@resend.dev>"        # provider test sender: delivers to the provider account owner only


# ───────────────────────────── passwords ─────────────────────────────
def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _kdf(pw: str, salt: bytes, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P) -> bytes:
    return hashlib.scrypt(pw.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=DKLEN, maxmem=MAXMEM)


def hash_password(pw: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    return f"{PREFIX}{int(SCRYPT_N).bit_length() - 1}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(_kdf(pw, salt))}"


def is_legacy_hash(stored) -> bool:
    s = str(stored or "")
    return len(s) == 64 and all(c in "0123456789abcdef" for c in s.lower())


def verify_password(pw: str, stored) -> tuple[bool, bool]:
    """(password is right, the stored hash should be upgraded). Constant-time comparisons."""
    s = str(stored or "")
    if s.startswith(PREFIX):
        try:
            _, logn, r, p, salt, want = s.split("$")
            got = _kdf(pw, base64.b64decode(salt), n=2 ** int(logn), r=int(r), p=int(p))
            return hmac.compare_digest(_b64(got), want), False
        except Exception:
            return False, False
    if is_legacy_hash(s):
        ok = hmac.compare_digest(hashlib.sha256(pw.encode("utf-8")).hexdigest(), s.lower())
        return ok, ok
    return False, False


_DUMMY = None


def dummy_verify(pw: str) -> None:
    """Same cost for an unknown e-mail as for a known one (no account enumeration by timing)."""
    global _DUMMY
    if _DUMMY is None:
        _DUMMY = hash_password("dummy-password-never-used")
    verify_password(pw, _DUMMY)


def admin_password_ok(pw: str, secrets) -> bool:
    """Admin secret: ADMIN_PASSWORD_HASH (scrypt hash, preferred) or ADMIN_PASSWORD (compared in constant time)."""
    h = str(secrets.get("ADMIN_PASSWORD_HASH", "") or "")
    if h:
        return verify_password(pw, h)[0]
    ap = str(secrets.get("ADMIN_PASSWORD", "") or "")
    return bool(ap) and hmac.compare_digest(pw.encode("utf-8"), ap.encode("utf-8"))


# ───────────────────────────── lockout ─────────────────────────────
def _parse(ts):
    if not ts:
        return None
    try:
        d = _dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=_dt.timezone.utc)
    except Exception:
        return None


def lock_minutes_left(rec: dict, now: _dt.datetime) -> int:
    until = _parse((rec or {}).get("locked_until"))
    if not until or until <= now:
        return 0
    return int((until - now).total_seconds() // 60) + 1


def failure_fields(rec: dict, now: _dt.datetime) -> dict:
    n = int((rec or {}).get("failed_attempts") or 0) + 1
    if n >= MAX_FAILED:
        return dict(failed_attempts=0, locked_until=(now + _dt.timedelta(minutes=LOCK_MINUTES)).isoformat())
    return dict(failed_attempts=n)


def success_fields(rec: dict) -> dict:
    if int((rec or {}).get("failed_attempts") or 0) or (rec or {}).get("locked_until"):
        return dict(failed_attempts=0, locked_until=None)
    return {}


def authenticate(rec: dict | None, pw: str, now: _dt.datetime):
    """Returns (ok, message, fields_to_store, new_hash_or_None). Never stores or returns the password."""
    if not rec:
        dummy_verify(pw)
        return False, "Incorrect email or password.", {}, None
    left = lock_minutes_left(rec, now)
    if left:
        return False, f"Too many failed attempts. Try again in about {left} minute(s).", {}, None
    ok, upgrade = verify_password(pw, rec.get("pwd_hash"))
    if not ok:
        return False, "Incorrect email or password.", failure_fields(rec, now), None
    return True, "", success_fields(rec), (hash_password(pw) if upgrade else None)


# ───────────────────────────── e-mails ─────────────────────────────
PLAN_TEXT = {"essentiel": ("Essentiel", "€15 per month", "Dashboard for any aircraft, Profitability and Sensitivity"),
             "pro": ("Pro", "€50 per month", "everything in Essentiel plus Cost Master, PDF report and CSV export, Quotation, comparison and saved scenarios")}


def _e(x) -> str:
    return _html.escape(str(x or ""))


def _wrap(title: str, body: str) -> str:
    return (f"<div style='font-family:Segoe UI,Arial,sans-serif;max-width:560px;margin:auto;color:#112244'>"
            f"<h2 style='color:#112244;border-bottom:2px solid #C9A84C;padding-bottom:.4rem'>{_e(title)}</h2>{body}"
            f"<p style='font-size:12px;color:#5A6B85;margin-top:2rem'>Menkor Aviation — figures are estimates for simulation purposes only.</p></div>")


def welcome_email(email: str, app_url: str):
    body = (f"<p>Your account <b>{_e(email)}</b> has been created.</p>"
            f"<p>The free plan gives you the Dashboard demo. You can subscribe at any time from the sidebar to unlock more aircraft, "
            f"your own hours and fuel price, profitability and more.</p>"
            f"<p><a href='{_e(app_url)}' style='background:#C9A84C;color:#0B1629;padding:8px 16px;border-radius:4px;text-decoration:none;font-weight:700'>Open Aviation Cost Estimator</a></p>"
            f"<p style='font-size:13px'>If you did not create this account, you can ignore this message.</p>")
    return "Welcome to Aviation Cost Estimator — account created", _wrap("Account created", body)


def admin_signup_email(email: str, now: _dt.datetime):
    body = f"<p>A new account was just created:</p><p style='font-size:1.1rem;font-weight:700'>{_e(email)}</p><p>{_e(now.strftime('%Y-%m-%d %H:%M UTC'))}</p>"
    return "✈ New user registered — Aviation Cost Estimator", _wrap("New registration", body)


def subscription_email(plan: str, app_url: str, renewal_date: str | None = None):
    name, price, includes = PLAN_TEXT.get(plan, (plan.capitalize(), "", ""))
    body = (f"<p>Thank you: your <b>{_e(name)}</b> subscription{(' (' + _e(price) + ')') if price else ''} is active.</p>"
            + (f"<p>Included: {_e(includes)}.</p>" if includes else "")
            + (f"<p>Next renewal: {_e(renewal_date)}.</p>" if renewal_date else "")
            + f"<p><a href='{_e(app_url)}' style='background:#C9A84C;color:#0B1629;padding:8px 16px;border-radius:4px;text-decoration:none;font-weight:700'>Open Aviation Cost Estimator</a></p>"
            + "<p style='font-size:13px'>Log in with the e-mail address of your account to use your plan.</p>")
    return f"Your {name} subscription is active — Aviation Cost Estimator", _wrap("Subscription confirmed", body)


def send_email(post, key, sender, to, subject, html_body):
    """(ok, detail). ok only when the provider answered 2xx."""
    if not key:
        return False, "RESEND_API_KEY is missing/empty in this app's secrets."
    if not sender:
        return False, "EMAIL_FROM is missing: a sender address of a verified domain is required to write to users."
    if not to:
        return False, "No recipient configured."
    try:
        r = post("https://api.resend.com/emails", headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                 json={"from": sender, "to": [to] if isinstance(to, str) else list(to), "subject": subject, "html": html_body}, timeout=8)
        if r.status_code in (200, 201):
            return True, ""
        return False, f"HTTP {r.status_code}: {str(r.text)[:300]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def notify_signup(post, secrets, email: str, app_url: str, now: _dt.datetime | None = None) -> dict:
    """After a registration: confirmation e-mail to the user + notification to the owner. Both best-effort and independent: a failure never blocks the signup."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    key = secrets.get("RESEND_API_KEY"); sender = secrets.get("EMAIL_FROM")
    admin_to = secrets.get("SIGNUP_NOTIFY_TO") or secrets.get("ADMIN_EMAIL")
    s, h = welcome_email(email, app_url)
    welcome = send_email(post, key, sender, email, s, h)
    s2, h2 = admin_signup_email(email, now)
    admin = send_email(post, key, sender or TEST_SENDER, admin_to, s2, h2)           # the provider test sender is enough to reach the owner
    return dict(welcome=welcome, admin=admin)
