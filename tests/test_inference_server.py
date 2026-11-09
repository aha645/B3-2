from pathlib import Path
import subprocess
from unittest.mock import Mock

import httpx
import pytest

import inference_server as server


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv('AI_API_KEY', 'test-only-server-key')


@pytest.mark.parametrize('value', ['', '   ', 'key\nvalue', 'a,b', '한글', ' leading'])
def test_invalid_key(value, monkeypatch):
    monkeypatch.setenv('AI_API_KEY', value)
    with pytest.raises(ValueError, match='AI_API_KEY'):
        server.api_key()


def client(monkeypatch, handler):
    instance = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(server.httpx, 'Client', lambda **kw: instance)
    return instance


def test_reuse_existing_does_not_start_or_stop(monkeypatch):
    def handler(request):
        if request.url.path == '/health':
            return httpx.Response(200, json={'status': 'ok'})
        if 'Authorization' not in request.headers:
            return httpx.Response(401)
        assert request.headers['Authorization'] == 'Bearer test-only-server-key'
        return httpx.Response(200, json={'data': [{'id': 'test-model'}]})
    client(monkeypatch, handler)
    monkeypatch.setattr(server.subprocess, 'Popen', lambda *a, **kw: pytest.fail('must not launch'))
    with server.local_server('test-model'):
        pass


@pytest.mark.parametrize('status', [401, 403])
def test_auth_failure(monkeypatch, status):
    def handler(request):
        return httpx.Response(200, json={'status': 'ok'}) if request.url.path == '/health' else httpx.Response(status)
    client(monkeypatch, handler)
    with pytest.raises(ValueError, match='인증 실패'):
        with server.local_server('test-model'):
            pytest.fail('must not run')


def test_alias_mismatch(monkeypatch):
    def handler(request):
        if request.url.path == '/health':
            return httpx.Response(200, json={'status': 'ok'})
        if 'Authorization' not in request.headers:
            return httpx.Response(401)
        return httpx.Response(200, json={'data': [{'id': 'other'}]})
    client(monkeypatch, handler)
    with pytest.raises(ValueError, match='alias'):
        with server.local_server('test-model'):
            pass


def offline(request):
    raise httpx.ConnectError('offline', request=request)


def test_reject_unauthenticated_server(monkeypatch):
    client(monkeypatch, lambda r: httpx.Response(200, json={'status': 'ok'}))
    with pytest.raises(ValueError, match='인증이 적용되지 않은'):
        with server.local_server('test-model'):
            pass


def test_existing_missing(monkeypatch):
    client(monkeypatch, offline)
    with pytest.raises(ValueError, match='실행 중인'):
        with server.local_server('test-model', existing_only=True):
            pass


def test_missing_binary(monkeypatch, tmp_path):
    client(monkeypatch, offline)
    with pytest.raises(ValueError, match='llama-server가 없습니다'):
        with server.local_server('test-model', server_path=tmp_path / 'missing'):
            pass


def test_missing_model(monkeypatch, tmp_path):
    client(monkeypatch, offline)
    binary = tmp_path / 'server'
    binary.touch()
    with pytest.raises(ValueError, match='GGUF'):
        with server.local_server('test-model', tmp_path / 'missing', binary):
            pass


def test_owned_process_cleanup_on_body_error(monkeypatch, tmp_path):
    client(monkeypatch, offline)
    ready = iter([False, True])
    monkeypatch.setattr(server, 'health', lambda c: next(ready))
    monkeypatch.setattr(server, 'verify_server', lambda *a: None)
    binary = tmp_path / 'server'
    model = tmp_path / 'model.gguf'
    binary.touch(); model.touch()
    process = Mock()
    process.poll.return_value = None
    launched = []
    def launch(command, **kwargs):
        launched.append((command, kwargs))
        return process
    monkeypatch.setattr(server.subprocess, 'Popen', launch)
    with pytest.raises(ValueError, match='body error'):
        with server.local_server('test-model', model, binary):
            raise ValueError('body error')
    process.terminate.assert_called_once()
    process.wait.assert_called_once()
    command, kwargs = launched[0]
    assert 'test-only-server-key' not in ' '.join(command)
    assert kwargs['env']['LLAMA_API_KEY'] == 'test-only-server-key'
    assert '--no-webui' in command and '--no-context-shift' in command


def test_startup_timeout_cleanup(monkeypatch, tmp_path):
    client(monkeypatch, offline)
    path = tmp_path / 'file'; path.touch()
    process = Mock(); process.poll.return_value = None
    monkeypatch.setattr(server.subprocess, 'Popen', lambda *a, **kw: process)
    with pytest.raises(ValueError, match='시작 시간 초과'):
        with server.local_server('test-model', path, path, startup_timeout=0):
            pass
    process.terminate.assert_called_once()


def test_crash_before_ready(monkeypatch, tmp_path):
    client(monkeypatch, offline)
    path = tmp_path / 'file'; path.touch()
    process = Mock(); process.poll.return_value = 1
    monkeypatch.setattr(server.subprocess, 'Popen', lambda *a, **kw: process)
    with pytest.raises(ValueError, match='준비 전에 종료'):
        with server.local_server('test-model', path, path):
            pass
    process.terminate.assert_not_called()


def test_kill_on_shutdown_timeout():
    process = Mock()
    process.poll.return_value = None
    process.wait.side_effect = [subprocess.TimeoutExpired('server', 10), 0]
    server.stop(process)
    process.kill.assert_called_once()


def test_non_server_health(monkeypatch):
    instance = client(monkeypatch, lambda r: httpx.Response(200, text='not JSON'))
    with pytest.raises(ValueError, match='상태 응답'):
        server.health(instance)
