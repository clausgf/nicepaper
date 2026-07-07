import bcrypt

from app.config import app_config
from app.auth.password import PasswordAuthProvider


def make_provider(tmp_path, monkeypatch, lines):
    htpasswd = tmp_path / "htpasswd"
    htpasswd.write_text("\n".join(lines) + "\n")
    monkeypatch.setattr(app_config, "auth_htpasswd_file", str(htpasswd))
    return PasswordAuthProvider()


def test_verify_accepts_correct_password(tmp_path, monkeypatch):
    stored = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()
    provider = make_provider(tmp_path, monkeypatch, [f"finn:{stored}"])
    assert provider.verify("finn", "secret")
    assert not provider.verify("finn", "wrong")
    assert not provider.verify("unknown", "secret")


def test_verify_accepts_htpasswd_2y_prefix(tmp_path, monkeypatch):
    stored = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()
    stored = "$2y$" + stored[4:]  # htpasswd -B writes the $2y$ prefix
    provider = make_provider(tmp_path, monkeypatch, [f"finn:{stored}"])
    assert provider.verify("finn", "secret")


def test_load_users_skips_comments_and_non_bcrypt(tmp_path, monkeypatch):
    stored = bcrypt.hashpw(b"secret", bcrypt.gensalt()).decode()
    provider = make_provider(tmp_path, monkeypatch, [
        "# a comment",
        "",
        "not-a-valid-line",
        "md5user:$apr1$abcdefgh$0123456789abcdef",
        f"finn:{stored}",
    ])
    users = provider._load_users()
    assert list(users.keys()) == ["finn"]
    assert not provider.verify("md5user", "anything")


def test_missing_htpasswd_file_rejects_everyone(tmp_path, monkeypatch):
    monkeypatch.setattr(app_config, "auth_htpasswd_file", str(tmp_path / "missing"))
    provider = PasswordAuthProvider()
    assert not provider.verify("finn", "secret")
