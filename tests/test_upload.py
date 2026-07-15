"""Upload validation, durability and concurrency contracts."""
from __future__ import annotations

import copy
import os
import threading

import pytest

import config as configmod
import server


@pytest.mark.parametrize(
    "filename,data",
    [
        ("manual.pdf", b"%PDF-1.7\nsynthetic"),
        ("manual.docx", b"PK\x03\x04synthetic"),
        ("slides.pptx", b"PK\x03\x04synthetic"),
        ("register.xlsx", b"PK\x03\x04synthetic"),
        ("register.xlsm", b"PK\x03\x04synthetic"),
        ("notes.txt", b"synthetic notes"),
        ("notes.md", b"# Synthetic notes"),
        ("register.csv", b"tag,value\nPMP-101,1\n"),
        ("drawing.png", b"\x89PNG\r\n\x1a\nsynthetic"),
        ("photo.jpg", b"\xff\xd8\xffsynthetic"),
        ("photo.jpeg", b"\xff\xd8\xffsynthetic"),
    ],
)
def test_validate_upload_accepts_supported_types(filename, data):
    assert server.validate_upload(filename, data) == os.path.splitext(filename)[1].lower()


@pytest.mark.parametrize(
    "filename,data",
    [
        ("script.exe", b"MZ"),
        ("fake.pdf", b"not a pdf"),
        ("fake.docx", b"not a zip"),
        ("fake.png", b"not a png"),
        ("bad.txt", b"\xff\xfe\x00"),
    ],
)
def test_validate_upload_rejects_unsupported_or_mismatched_content(filename, data):
    with pytest.raises(ValueError):
        server.validate_upload(filename, data)


def _app(tmp_path):
    cfg = copy.deepcopy(configmod.DEFAULTS)
    cfg["paths"]["data_dir"] = str(tmp_path / "dashboard")
    cfg["kb"]["inbox_dir"] = str(tmp_path / "inbox")
    cfg["telemetry"]["provider"] = "none"
    return server.DashboardApp(cfg)


def test_store_upload_rejects_insufficient_disk_reserve(tmp_path, monkeypatch):
    app = _app(tmp_path)
    data = b"synthetic notes"
    reserve = app.cfg["kb"]["upload_min_free_bytes"]
    usage = type("Usage", (), {"total": reserve * 2, "used": 0, "free": reserve + len(data) - 1})
    monkeypatch.setattr(server.shutil, "disk_usage", lambda _path: usage)

    with pytest.raises(OSError, match="free space reserve"):
        app.store_upload("notes.txt", data)


def test_concurrent_same_name_uploads_remain_distinct_and_complete(tmp_path):
    app = _app(tmp_path)
    barrier = threading.Barrier(3)
    results = []
    errors = []

    def upload(data):
        try:
            barrier.wait()
            results.append(app.store_upload("notes.txt", data))
        except Exception as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    payloads = [b"first complete upload", b"second complete upload"]
    threads = [threading.Thread(target=upload, args=(payload,)) for payload in payloads]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len({result["stored"] for result in results}) == 2
    assert all(result["ingest_queued"] for result in results)
    uploaded = {
        (tmp_path / "dashboard" / "uploads" / result["stored"]).read_bytes()
        for result in results
    }
    queued = {(tmp_path / "inbox" / result["queued_as"]).read_bytes() for result in results}
    assert uploaded == queued == set(payloads)


def test_symlink_inbox_root_is_not_used_for_promotion(tmp_path):
    app = _app(tmp_path)
    real_inbox = tmp_path / "real-inbox"
    real_inbox.mkdir()
    configured = tmp_path / "inbox"
    configured.symlink_to(real_inbox, target_is_directory=True)

    result = app.store_upload("notes.txt", b"synthetic notes")

    assert result["ok"] is True
    assert result["ingest_queued"] is False
    assert list(real_inbox.iterdir()) == []
