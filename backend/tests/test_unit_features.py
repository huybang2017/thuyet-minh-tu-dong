from datetime import datetime, timedelta, timezone

from app import security
from app.analytics.router import _csv_cell
from app.content.seed import build_menu_seed
from app.media.router import IMAGE_URL_RE, sniff


def test_image_sniff_by_magic_bytes():
    assert sniff(b"\xff\xd8\xff\xe0" + b"\0" * 12) == "jpg"
    assert sniff(b"\x89PNG\r\n\x1a\n" + b"\0" * 8) == "png"
    assert sniff(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "webp"
    assert sniff(b"<svg xmlns=...") is None
    assert sniff(b"GIF89a") is None
    assert sniff(b"") is None


def test_image_url_whitelist():
    assert IMAGE_URL_RE.match("/static/images/" + "a" * 24 + ".png")
    for bad in ("https://x.example/a.png", "/static/images/../main.py", "/static/images/" + "a" * 24 + ".svg",
                "javascript:alert(1)", "/static/images/" + "A" * 24 + ".png"):
        assert not IMAGE_URL_RE.match(bad), bad


def test_csv_formula_injection_guard():
    assert _csv_cell("=HYPERLINK(\"x\")") == "'=HYPERLINK(\"x\")"
    assert _csv_cell("+1") == "'+1" and _csv_cell("@x") == "'@x" and _csv_cell("-2") == "'-2"
    assert _csv_cell("Ốc Oanh") == "Ốc Oanh" and _csv_cell(None) == "" and _csv_cell(5) == "5"


def test_issued_before_and_reset_token():
    now = datetime.now(timezone.utc)
    tok = security.decode_token(security.create_token({"sub": "u"}, "refresh"), "refresh")
    assert "iat" in tok
    assert security.issued_before(tok, None) is False
    assert security.issued_before(tok, now + timedelta(seconds=5)) is True
    assert security.issued_before(tok, now - timedelta(seconds=5)) is False
    # Mongo trả datetime naive (UTC)
    assert security.issued_before(tok, (now + timedelta(seconds=5)).replace(tzinfo=None)) is True
    raw, digest = security.new_reset_token()
    assert len(raw) >= 40 and raw != digest and security.hash_reset_token(raw) == digest


def test_menu_seed_only_for_existing_pois():
    docs = build_menu_seed({"poi-oc-oanh"})
    assert docs and {d["poi_id"] for d in docs} == {"poi-oc-oanh"}
    assert len({d["_id"] for d in docs}) == len(docs) and all(d["price"] > 0 for d in docs)
    assert build_menu_seed(set()) == []
