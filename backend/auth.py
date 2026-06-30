"""
AOI Tool - Authentication & authorization.

Self-contained, dependency-free (stdlib only):
  - PBKDF2-HMAC-SHA256 password hashing with per-user random salt.
  - HS256 JSON Web Tokens signed with a persistent server secret.
  - Role-based permissions (per-role only for v1).
  - A small JSON user store with atomic writes.
  - FastAPI dependencies: `current_user` and `require(<perm>)`.

Credentials live in a single gitignored file (config.AUTH_FILE), kept
separate from the inspection SQLite DB because that DB is truncated and
rebuilt on every sync — auth must survive those rebuilds.

The default super user (admin / adminpwd) is created on first run with
`must_change_pw=True`; the frontend should force a password change.
"""

import os
import json
import time
import hmac
import base64
import hashlib
import secrets
import logging
import threading
from typing import Optional

from fastapi import Depends, Query, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config import AUTH_FILE, JWT_SECRET_FILE, JWT_TTL_SECONDS

logger = logging.getLogger(__name__)

# ─── Roles & permissions ──────────────────────────────────────────────────────
# The full registry of gateable capabilities. Keep these strings in sync with
# the dependencies wired onto routes.
PERMISSIONS: tuple[str, ...] = (
    "inspection.run",   # run AP / VB / text inspection
    "ap.refresh",       # trigger AP refresh from intranet
    "sync.run",         # manual PP+CLI / AP sync
    "search.pm",        # PM search tab
    "ideas.view",       # see ALL ideas (not just your own)
    "ideas.edit",       # submit a new idea
    "ideas.manage",     # mark ideas done / delete  (admin)
    "mode.switch",      # toggle live / test mode
    "users.manage",     # create / edit / delete users  (admin only)
)

ROLES: tuple[str, ...] = ("admin", "aoiteam", "visitor")

# admin is implicitly all-permissions and is NOT stored or editable, so an
# admin can never strip their own users.manage and lock everyone out.
_ADMIN_PERMS = set(PERMISSIONS)

# Default permission sets for the editable roles.
#   aoiteam : everything except user- and idea-management
#   visitor : may submit ideas but not see others' (no ideas.view), and no
#             user- or idea-management
_AOITEAM_EXCLUDE = {"users.manage", "ideas.manage"}
_VISITOR_EXCLUDE = {"users.manage", "ideas.manage", "ideas.view"}
_DEFAULT_ROLE_PERMS: dict[str, list[str]] = {
    "aoiteam": [p for p in PERMISSIONS if p not in _AOITEAM_EXCLUDE],
    "visitor": [p for p in PERMISSIONS if p not in _VISITOR_EXCLUDE],
}

DEFAULT_ADMIN_USER = "admin"
DEFAULT_ADMIN_PW   = "adminpwd"

PBKDF2_ITERATIONS = 200_000

_lock = threading.RLock()


# ─── Password hashing (PBKDF2-HMAC-SHA256) ─────────────────────────────────────

def hash_password(password: str, *, iterations: int = PBKDF2_ITERATIONS,
                  salt: Optional[bytes] = None) -> dict:
    """Return a self-describing hash record (no plaintext is ever stored)."""
    if salt is None:
        salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return {
        "algo":       "pbkdf2_sha256",
        "iterations": iterations,
        "salt":       base64.b64encode(salt).decode("ascii"),
        "hash":       base64.b64encode(dk).decode("ascii"),
    }


def verify_password(password: str, rec: dict) -> bool:
    """Constant-time verify a password against a stored hash record."""
    try:
        salt = base64.b64decode(rec["salt"])
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 salt, int(rec["iterations"]))
        expected = base64.b64encode(dk).decode("ascii")
        return hmac.compare_digest(expected, rec["hash"])
    except Exception:
        return False


# ─── JWT (HS256, stdlib) ───────────────────────────────────────────────────────

def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(seg: str) -> bytes:
    pad = "=" * (-len(seg) % 4)
    return base64.urlsafe_b64decode(seg + pad)


def _jwt_secret() -> bytes:
    """
    Load the signing secret. Prefer the AOI_JWT_SECRET env var; otherwise read
    (or create once) a persistent secret file so tokens survive restarts.
    """
    env = os.environ.get("AOI_JWT_SECRET")
    if env:
        return env.encode("utf-8")
    with _lock:
        try:
            with open(JWT_SECRET_FILE, "r", encoding="utf-8") as fh:
                val = fh.read().strip()
            if val:
                return val.encode("utf-8")
        except FileNotFoundError:
            pass
        val = secrets.token_hex(32)
        os.makedirs(os.path.dirname(JWT_SECRET_FILE) or ".", exist_ok=True)
        _atomic_write(JWT_SECRET_FILE, val)
        logger.info("auth: generated new JWT secret at %s", JWT_SECRET_FILE)
        return val.encode("utf-8")


def make_token(username: str, role: str, ttl: int = JWT_TTL_SECONDS) -> str:
    header  = {"alg": "HS256", "typ": "JWT"}
    now     = int(time.time())
    payload = {"sub": username, "role": role, "iat": now, "exp": now + ttl}
    signing_input = (
        _b64url(json.dumps(header,  separators=(",", ":")).encode()) + "." +
        _b64url(json.dumps(payload, separators=(",", ":")).encode())
    )
    sig = hmac.new(_jwt_secret(), signing_input.encode("ascii"), hashlib.sha256).digest()
    return signing_input + "." + _b64url(sig)


def verify_token(token: str) -> Optional[dict]:
    """Return the payload if the signature is valid and not expired, else None."""
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
        signing_input = f"{header_b64}.{payload_b64}"
        expected = _b64url(hmac.new(_jwt_secret(), signing_input.encode("ascii"),
                                    hashlib.sha256).digest())
        if not hmac.compare_digest(expected, sig_b64):
            return None
        payload = json.loads(_b64url_decode(payload_b64))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


# ─── User store (atomic JSON) ──────────────────────────────────────────────────

def _atomic_write(path: str, text: str) -> None:
    """Write to a temp file in the same dir, then os.replace (atomic on POSIX & Windows)."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    tmp = os.path.join(directory, f".{os.path.basename(path)}.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _empty_store() -> dict:
    return {"version": 1, "roles": dict(_DEFAULT_ROLE_PERMS), "users": {}}


def _load() -> dict:
    try:
        with open(AUTH_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return _empty_store()
    except Exception as e:
        logger.error("auth: failed to read %s (%s) — refusing to overwrite", AUTH_FILE, e)
        raise
    data.setdefault("version", 1)
    data.setdefault("roles", dict(_DEFAULT_ROLE_PERMS))
    data.setdefault("users", {})
    return data


def _save(data: dict) -> None:
    _atomic_write(AUTH_FILE, json.dumps(data, indent=2, ensure_ascii=False))


def ensure_default_admin() -> None:
    """Create the default super user on first run (idempotent)."""
    with _lock:
        data = _load()
        if not data["users"]:
            data["users"][DEFAULT_ADMIN_USER] = {
                "role": "admin",
                **hash_password(DEFAULT_ADMIN_PW),
                "must_change_pw": True,
                "created_at": int(time.time()),
            }
            _save(data)
            logger.warning(
                "auth: created default super user '%s' (must change password)",
                DEFAULT_ADMIN_USER,
            )


# ─── Permission resolution ─────────────────────────────────────────────────────

def permissions_for(role: str) -> set[str]:
    if role == "admin":
        return set(_ADMIN_PERMS)
    with _lock:
        data = _load()
    return {p for p in data["roles"].get(role, []) if p in PERMISSIONS}


def role_permissions() -> dict[str, list[str]]:
    """All role -> permission lists, for the admin UI (admin shown as full set)."""
    with _lock:
        data = _load()
    out = {"admin": list(PERMISSIONS)}
    for r in ("aoiteam", "visitor"):
        out[r] = [p for p in data["roles"].get(r, []) if p in PERMISSIONS]
    return out


def set_role_permissions(role: str, perms: list[str]) -> dict[str, list[str]]:
    if role == "admin":
        raise ValueError("admin permissions are fixed and cannot be edited")
    if role not in ("aoiteam", "visitor"):
        raise ValueError(f"unknown role: {role}")
    clean = [p for p in perms if p in PERMISSIONS]
    with _lock:
        data = _load()
        data["roles"][role] = clean
        _save(data)
    return role_permissions()


# ─── User CRUD ─────────────────────────────────────────────────────────────────

def get_user(username: str) -> Optional[dict]:
    with _lock:
        return _load()["users"].get(username)


def list_users() -> list[dict]:
    with _lock:
        data = _load()
    return [
        {"username": u, "role": rec.get("role", "visitor"),
         "must_change_pw": bool(rec.get("must_change_pw", False)),
         "created_at": rec.get("created_at")}
        for u, rec in sorted(data["users"].items())
    ]


def create_user(username: str, password: str, role: str) -> dict:
    username = (username or "").strip()
    if not username:
        raise ValueError("username is required")
    if role not in ROLES:
        raise ValueError(f"invalid role: {role}")
    if not password:
        raise ValueError("password is required")
    with _lock:
        data = _load()
        if username in data["users"]:
            raise ValueError(f"user '{username}' already exists")
        data["users"][username] = {
            "role": role,
            **hash_password(password),
            "must_change_pw": False,
            "created_at": int(time.time()),
        }
        _save(data)
    logger.info("auth: created user '%s' (role=%s)", username, role)
    return {"username": username, "role": role}


def delete_user(username: str, *, acting_user: str) -> None:
    with _lock:
        data = _load()
        if username not in data["users"]:
            raise ValueError(f"user '{username}' not found")
        if username == acting_user:
            raise ValueError("you cannot delete your own account")
        # never allow removing the last admin
        admins = [u for u, r in data["users"].items() if r.get("role") == "admin"]
        if data["users"][username].get("role") == "admin" and len(admins) <= 1:
            raise ValueError("cannot delete the last admin")
        del data["users"][username]
        _save(data)
    logger.info("auth: deleted user '%s'", username)


def update_user(username: str, *, role: Optional[str] = None,
                password: Optional[str] = None) -> dict:
    with _lock:
        data = _load()
        rec = data["users"].get(username)
        if rec is None:
            raise ValueError(f"user '{username}' not found")
        if role is not None:
            if role not in ROLES:
                raise ValueError(f"invalid role: {role}")
            # don't demote the last admin
            if rec.get("role") == "admin" and role != "admin":
                admins = [u for u, r in data["users"].items() if r.get("role") == "admin"]
                if len(admins) <= 1:
                    raise ValueError("cannot demote the last admin")
            rec["role"] = role
        if password is not None:
            if not password:
                raise ValueError("password cannot be empty")
            rec.update(hash_password(password))
            rec["must_change_pw"] = False
        data["users"][username] = rec
        _save(data)
    logger.info("auth: updated user '%s'", username)
    return {"username": username, "role": rec["role"]}


def change_password(username: str, old_password: str, new_password: str) -> None:
    if not new_password:
        raise ValueError("new password cannot be empty")
    with _lock:
        data = _load()
        rec = data["users"].get(username)
        if rec is None or not verify_password(old_password, rec):
            raise ValueError("current password is incorrect")
        rec.update(hash_password(new_password))
        rec["must_change_pw"] = False
        data["users"][username] = rec
        _save(data)
    logger.info("auth: password changed for '%s'", username)


def authenticate(username: str, password: str) -> Optional[dict]:
    """Return a public user dict on success, else None."""
    rec = get_user(username)
    if rec is None or not verify_password(password, rec):
        return None
    role = rec.get("role", "visitor")
    return {
        "username":       username,
        "role":           role,
        "permissions":    sorted(permissions_for(role)),
        "must_change_pw": bool(rec.get("must_change_pw", False)),
    }


# ─── FastAPI dependencies ──────────────────────────────────────────────────────

# HTTPBearer gives Swagger the "Authorize" lock button (paste the raw token once;
# the Bearer prefix is applied automatically). auto_error=False lets us return
# our own 401 and also support the SSE query-token fallback.
_bearer = HTTPBearer(auto_error=False)


def _resolve_user_from_token(token: Optional[str]) -> dict:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    rec = get_user(payload["sub"])
    if rec is None:
        raise HTTPException(status_code=401, detail="User no longer exists")
    role = rec.get("role", "visitor")
    return {
        "username":       payload["sub"],
        "role":           role,
        "permissions":    permissions_for(role),
        "must_change_pw": bool(rec.get("must_change_pw", False)),
    }


def current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    """FastAPI dependency: require a valid Bearer token (Authorization header)."""
    return _resolve_user_from_token(creds.credentials if creds else None)


def current_user_flex(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    token: Optional[str] = Query(default=None),
) -> dict:
    """
    Like current_user, but also accepts a `?token=` query param. Needed for the
    AP-refresh SSE endpoint, since EventSource cannot send custom headers.
    """
    tok = creds.credentials if creds else (token or None)
    return _resolve_user_from_token(tok)


def require(permission: str):
    """Dependency factory: require a specific permission (header token)."""
    if permission not in PERMISSIONS:
        raise ValueError(f"unknown permission: {permission}")

    def _dep(user: dict = Depends(current_user)) -> dict:
        if permission not in user["permissions"]:
            raise HTTPException(status_code=403,
                                detail=f"Missing permission: {permission}")
        return user

    return _dep


def require_flex(permission: str):
    """Like require(), but also accepts a `?token=` query param (for SSE)."""
    if permission not in PERMISSIONS:
        raise ValueError(f"unknown permission: {permission}")

    def _dep(user: dict = Depends(current_user_flex)) -> dict:
        if permission not in user["permissions"]:
            raise HTTPException(status_code=403,
                                detail=f"Missing permission: {permission}")
        return user

    return _dep
