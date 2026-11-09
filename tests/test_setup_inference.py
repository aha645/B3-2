import hashlib
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts import setup_inference as setup


def test_download_fixed_revision_and_hash(tmp_path, monkeypatch):
    path = tmp_path / 'model.gguf'
    path.write_bytes(b'GGUFtest')
    calls = []
    def download(**kwargs):
        calls.append(kwargs)
        return str(path)
    monkeypatch.setattr(setup, 'hf_hub_download', download)
    monkeypatch.setattr(setup, 'MODEL_SHA256', hashlib.sha256(b'GGUFtest').hexdigest())
    setup.download()
    assert calls[0]['revision'] == setup.MODEL_REVISION
    assert calls[0]['filename'] == setup.MODEL_FILE


def test_download_hash_mismatch(tmp_path, monkeypatch):
    path = tmp_path / 'model.gguf'; path.write_bytes(b'bad')
    monkeypatch.setattr(setup, 'hf_hub_download', lambda **kw: str(path))
    with pytest.raises(ValueError, match='SHA-256'):
        setup.download()


def test_build_rejects_changed_source(tmp_path, monkeypatch):
    source = tmp_path / 'source'; source.mkdir(); (source / '.git').mkdir()
    monkeypatch.setattr(setup, 'SOURCE', source)
    monkeypatch.setattr(setup.shutil, 'which', lambda name: '/cmake')
    monkeypatch.setattr(setup.subprocess, 'run', lambda *a, **kw: Mock(stdout=' M file'))
    with pytest.raises(ValueError, match='로컬 변경'):
        setup.build(4)


def test_build_pins_revision(tmp_path, monkeypatch):
    source = tmp_path / 'source'; source.mkdir(); (source / '.git').mkdir()
    monkeypatch.setattr(setup, 'SOURCE', source)
    monkeypatch.setattr(setup.shutil, 'which', lambda name: '/cmake')
    monkeypatch.setattr(setup.subprocess, 'run', lambda *a, **kw: Mock(stdout=''))
    calls = []
    monkeypatch.setattr(setup, 'run', lambda *args: calls.append(args))
    setup.build(2)
    assert calls[0][-1] == setup.REVISION
    assert calls[-1][-2:] == ('-j', '2')


def test_build_requires_cmake(monkeypatch):
    monkeypatch.setattr(setup.shutil, 'which', lambda name: None)
    with pytest.raises(ValueError, match='CMake'):
        setup.build(4)
