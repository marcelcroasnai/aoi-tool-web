"""
Standalone verification for auth.py — run directly:

    python tests/test_auth.py

Uses a throwaway temp credential file (via AOI_AUTH_FILE / AOI_JWT_SECRET_FILE
env vars) so it never touches the real auth_users.json.
"""

import os
import sys
import time
import tempfile

# Point auth/config at a throwaway location BEFORE importing them.
_tmp = tempfile.mkdtemp(prefix="aoi_auth_test_")
os.environ["AOI_AUTH_FILE"]       = os.path.join(_tmp, "auth_users.json")
os.environ["AOI_JWT_SECRET_FILE"] = os.path.join(_tmp, ".jwt_secret")
os.environ["AOI_JWT_TTL"]         = "3600"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import auth  # noqa: E402

_passed = 0
_failed = 0

def check(name, cond):
    global _passed, _failed
    if cond:
        _passed += 1
        print(f"  PASS  {name}")
    else:
        _failed += 1
        print(f"  FAIL  {name}")


def main():
    # ── hashing ──
    rec = auth.hash_password("hunter2")
    check("hash record has no plaintext", "hunter2" not in str(rec))
    check("verify correct password", auth.verify_password("hunter2", rec))
    check("reject wrong password", not auth.verify_password("nope", rec))
    rec2 = auth.hash_password("hunter2")
    check("salts differ between hashes", rec["salt"] != rec2["salt"])

    # ── JWT ──
    tok = auth.make_token("alice", "aoiteam")
    payload = auth.verify_token(tok)
    check("valid token verifies", payload and payload["sub"] == "alice")
    check("tampered token rejected", auth.verify_token(tok[:-2] + "xx") is None)
    expired = auth.make_token("bob", "visitor", ttl=-10)
    check("expired token rejected", auth.verify_token(expired) is None)
    check("garbage token rejected", auth.verify_token("not.a.jwt") is None)

    # ── default admin ──
    auth.ensure_default_admin()
    admin = auth.authenticate("admin", "adminpwd")
    check("default admin login works", admin is not None)
    check("admin role is admin", admin and admin["role"] == "admin")
    check("admin must change pw", admin and admin["must_change_pw"] is True)
    check("admin has users.manage", admin and "users.manage" in admin["permissions"])
    auth.ensure_default_admin()  # idempotent
    check("ensure_default_admin idempotent", len(auth.list_users()) == 1)

    # ── role permissions ──
    aoi = auth.permissions_for("aoiteam")
    check("aoiteam lacks users.manage", "users.manage" not in aoi)
    check("aoiteam can run inspection", "inspection.run" in aoi)
    check("admin has all perms", auth.permissions_for("admin") == set(auth.PERMISSIONS))

    # ── user CRUD ──
    auth.create_user("tom", "tompw", "aoiteam")
    check("create user", auth.get_user("tom") is not None)
    check("new user login", auth.authenticate("tom", "tompw") is not None)
    try:
        auth.create_user("tom", "x", "visitor"); dup = False
    except ValueError:
        dup = True
    check("duplicate user rejected", dup)
    try:
        auth.create_user("bad", "x", "wizard"); badrole = False
    except ValueError:
        badrole = True
    check("invalid role rejected", badrole)

    auth.update_user("tom", role="visitor")
    check("role updated", auth.get_user("tom")["role"] == "visitor")
    auth.update_user("tom", password="newpw")
    check("password updated", auth.authenticate("tom", "newpw") is not None)
    check("old password no longer works", auth.authenticate("tom", "tompw") is None)

    # ── change own password ──
    auth.change_password("admin", "adminpwd", "S3cret!")
    check("admin pw changed", auth.authenticate("admin", "S3cret!") is not None)
    check("must_change_pw cleared", auth.authenticate("admin", "S3cret!")["must_change_pw"] is False)
    try:
        auth.change_password("admin", "wrong", "x"); badold = False
    except ValueError:
        badold = True
    check("change pw with wrong old rejected", badold)

    # ── last-admin protection ──
    try:
        auth.delete_user("admin", acting_user="tom"); last = False
    except ValueError:
        last = True
    check("cannot delete last admin", last)
    try:
        auth.update_user("admin", role="visitor"); demote = False
    except ValueError:
        demote = True
    check("cannot demote last admin", demote)

    # ── editable role perms ──
    auth.set_role_permissions("visitor", ["search.pm", "ideas.view"])
    vis = auth.permissions_for("visitor")
    check("visitor perms narrowed", vis == {"search.pm", "ideas.view"})
    try:
        auth.set_role_permissions("admin", []); editadmin = False
    except ValueError:
        editadmin = True
    check("admin perms not editable", editadmin)

    # ── persistence: file actually on disk and hashed ──
    with open(os.environ["AOI_AUTH_FILE"], "r", encoding="utf-8") as fh:
        raw = fh.read()
    check("store persisted to disk", "users" in raw and "admin" in raw)
    check("no plaintext password in store", "adminpwd" not in raw and "S3cret!" not in raw)

    print(f"\n{_passed} passed, {_failed} failed")
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
