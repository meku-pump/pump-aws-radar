"""Tests for the Pump push (pump_aws_radar.upload). No network: urlopen is stubbed."""

import io
import json
import urllib.error

import pytest

from pump_aws_radar import upload


class _FakeResp:
    def __init__(self, body=b"", status=200):
        self._body = body
        self.status = status

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_upload_csvs_exchanges_then_puts(monkeypatch, tmp_path):
    inv = tmp_path / "inventory.csv"
    inv.write_text("AccountID,Service\n1,EC2\n")
    bil = tmp_path / "billing.csv"
    bil.write_text("date,service,cost\n2026-01-01,EC2,1.0\n")

    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append(req)
        if req.method == "POST":
            role = json.loads(req.data.decode())["role"]
            return _FakeResp(json.dumps({"upload_url": f"https://s3/{role}"}).encode())
        return _FakeResp(status=200)  # PUT

    monkeypatch.setattr(upload.urllib.request, "urlopen", fake_urlopen)

    upload.upload_csvs(
        api_base="http://localhost:8001",
        token="tok",
        files={"inventory": str(inv), "billing": str(bil)},
    )

    posts = [c for c in calls if c.method == "POST"]
    puts = [c for c in calls if c.method == "PUT"]
    assert len(posts) == 2 and len(puts) == 2
    # Exchange hits the documented path with the right body.
    assert posts[0].full_url == "http://localhost:8001/api/v1/estimate/radar/urls"
    assert json.loads(posts[0].data.decode()) == {"token": "tok", "role": "inventory"}
    # PUT carries the signed content-type and targets the returned URL.
    assert puts[0].full_url == "https://s3/inventory"
    assert puts[0].headers["Content-type"] == "text/csv"


def test_expired_token_raises_clear_error(monkeypatch, tmp_path):
    inv = tmp_path / "inventory.csv"
    inv.write_text("x\n")

    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(b"expired"))

    monkeypatch.setattr(upload.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(upload.UploadError, match="expired"):
        upload.upload_csvs("http://x", "tok", {"inventory": str(inv)})


def test_unknown_role_rejected(tmp_path):
    with pytest.raises(upload.UploadError, match="Unknown upload role"):
        upload.upload_csvs("http://x", "tok", {"diagram": "nope.csv"})
