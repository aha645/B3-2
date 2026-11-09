import json
from contextlib import nullcontext
from pathlib import Path
import subprocess

import httpx
import pytest

import ai_client
import main
import inference_server
from git_context import collect, parse_status
from safety import check_size, mask, prepare
from validation import render, validate


@pytest.fixture(autouse=True)
def local_environment(monkeypatch):
    monkeypatch.setenv('AI_API_KEY', 'test-only-not-a-real-secret')
    monkeypatch.setattr(inference_server, 'local_server', lambda *args, **kwargs: nullcontext())


def git(root, *args):
    return subprocess.run(['git', *args], cwd=root, check=True, capture_output=True).stdout


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, 'init')
    git(tmp_path, 'config', 'user.email', 'test@example.invalid')
    git(tmp_path, 'config', 'user.name', 'Test')
    (tmp_path / 'sample.py').write_text('value = 1\n')
    git(tmp_path, 'add', '.')
    git(tmp_path, 'commit', '-m', 'initial')
    return tmp_path


def result(mode='commit', title='feat: 값 변경'):
    data = {'summary': ['값 변경'], 'title': title}
    data.update({'body': ['sample.py의 값 변경']} if mode == 'commit' else {'why': ['변경 배경 확인 필요'], 'what': ['값 변경'], 'how_to_test': ['pytest를 실행하여 확인하세요']})
    return data


def test_git_states(repo):
    assert collect(repo).files == []
    (repo / 'sample.py').write_text('value = 2\n')
    assert '+value = 2' in collect(repo).unstaged
    git(repo, 'add', '.')
    (repo / 'sample.py').write_text('value = 3\n')
    context = collect(repo)
    assert context.files[0]['status'] == 'MM'
    assert '+value = 2' in context.staged and '+value = 3' in context.unstaged
    (repo / 'a space\nfile').write_text('secret content')
    context = collect(repo)
    assert any(x['path'] == 'a space\nfile' for x in context.files)
    assert 'secret content' not in context.staged + context.unstaged


def test_root_errors(repo, tmp_path):
    with pytest.raises(ValueError):
        collect(repo / 'subdir')
    fake = repo / 'fake'
    fake.mkdir()
    with pytest.raises(ValueError):
        collect(fake)


def test_rename_delete_binary(repo):
    git(repo, 'mv', 'sample.py', 'renamed.py')
    assert collect(repo).files[0]['original_path'] == 'sample.py'
    (repo / 'renamed.py').unlink()
    assert collect(repo).unstaged
    (repo / 'binary').write_bytes(b'\0abc')
    git(repo, 'add', 'binary')
    assert 'Binary files' in collect(repo).staged


def test_worktree(repo, tmp_path):
    work = tmp_path / 'linked'
    git(repo, 'worktree', 'add', '-b', 'linked', str(work))
    assert (work / '.git').is_file()
    assert collect(work).files == []


@pytest.mark.parametrize('code', ['DD', 'AU', 'UD', 'UA', 'DU', 'AA', 'UU'])
def test_conflicts(code):
    with pytest.raises(ValueError, match='충돌'):
        parse_status(f'{code} file\0'.encode())


def test_safety():
    raw = 'token="private-value" user@example.com sk-abcdefghijk github_pat_abcdefghijk'
    text, count = mask(raw)
    assert count >= 4
    for value in ('private-value', 'user@example.com', 'sk-abcdefghijk', 'github_pat_abcdefghijk'):
        assert value not in text
    text, count = prepare({'files': [{'path': 'a@example.com'}], 'reason': 'password=hidden'}, True)
    assert count == 2 and 'hidden' not in text and 'a@example.com' not in text
    assert prepare({'raw': raw}, False)[1] == 0


def test_size():
    check_size('a' * 65536)
    with pytest.raises(ValueError):
        check_size('a' * 65537)
    with pytest.raises(ValueError):
        check_size('한' * 22000)


@pytest.mark.parametrize('mode,length,valid,warning', [('commit', 50, True, False), ('commit', 51, True, True), ('commit', 72, True, True), ('commit', 73, False, False), ('pr', 80, True, False), ('pr', 81, False, False)])
def test_titles(mode, length, valid, warning):
    text = json.dumps(result(mode, '가' * length))
    if valid:
        _, warnings = validate(text, mode)
        assert bool(warnings) == warning
    else:
        with pytest.raises(ValueError):
            validate(text, mode)


@pytest.mark.parametrize('text', ['not json', '[]', '{}', '{"title":"a\\nb"}', 'null'])
def test_invalid_json(text):
    with pytest.raises(ValueError):
        validate(text, 'commit')


@pytest.mark.parametrize('field,value', [('why', []), ('what', ['']), ('how_to_test', 'test'), ('summary', [1])])
def test_invalid_sections(field, value):
    data = result('pr')
    data[field] = value
    with pytest.raises(ValueError):
        validate(json.dumps(data), 'pr')


def test_render():
    rendered = render(result('pr'), 'pr')
    for heading in ('Why', 'What', 'How to Test'):
        assert f'## {heading}\n- ' in rendered


def request_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_api_success():
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        assert request.headers['Authorization'] == 'Bearer test-only-not-a-real-secret'
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]})
    with request_client(handler) as client:
        assert ai_client.generate('system', 'prompt', 'model', 0.3, 100, client=client) == '{}'
    assert len(calls) == 1
    assert calls[0]['max_tokens'] == 100
    assert calls[0]['temperature'] == 0.3
    assert calls[0]['response_format'] == {'type': 'json_object'}


@pytest.mark.parametrize('status', [401, 403, 404, 429, 500])
def test_http_errors(status):
    with request_client(lambda r: httpx.Response(status, text='secret error body')) as client:
        with pytest.raises(ValueError, match=str(status)) as error:
            ai_client.generate('', '', 'model', 0.2, 10, client=client)
        assert 'secret' not in str(error.value)


@pytest.mark.parametrize('kind', ['timeout', 'connection', 'badjson', 'missing', 'length', 'empty'])
def test_api_failures(kind):
    def handler(request):
        if kind == 'timeout':
            raise httpx.ReadTimeout('secret', request=request)
        if kind == 'connection':
            raise httpx.ConnectError('secret', request=request)
        if kind == 'badjson':
            return httpx.Response(200, text='invalid')
        data = {'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]}
        if kind == 'missing':
            data['choices'] = []
        if kind == 'length':
            data['choices'][0]['finish_reason'] = 'length'
        if kind == 'empty':
            data['choices'][0]['message']['content'] = ''
        return httpx.Response(200, json=data)
    with request_client(handler) as client:
        with pytest.raises(ValueError):
            ai_client.generate('', '', 'model', 0.2, 10, client=client)


@pytest.mark.parametrize('mode', ['commit', 'pr'])
def test_cli_success(repo, monkeypatch, capsys, mode):
    monkeypatch.chdir(repo)
    (repo / 'sample.py').write_text('token="private-value"\n')
    seen = []
    def fake(system, prompt, model, temperature, max_tokens):
        seen.append(prompt)
        assert 'private-value' not in prompt and 'user@example.com' not in prompt
        return json.dumps(result(mode))
    monkeypatch.setattr(ai_client, 'generate', fake)
    assert main.main([mode, '--reason', 'user@example.com']) == 0
    output = capsys.readouterr()
    assert 'AI API 요청 횟수: 1' in output.err
    assert '--- 변경 요약 ---' in output.out and len(seen) == 1


def test_cli_no_changes(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    monkeypatch.delenv('AI_API_KEY')
    monkeypatch.setattr(ai_client, 'generate', lambda *a: pytest.fail('unexpected API'))
    assert main.main(['commit']) == 0
    output = capsys.readouterr()
    assert '변경 사항이 없습니다' in output.out and '요청 횟수: 0' in output.err


def test_cli_size_and_invalid(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    (repo / 'sample.py').write_text('a' * 70000)
    monkeypatch.setattr(ai_client, 'generate', lambda *a: pytest.fail('unexpected API'))
    assert main.main(['commit']) == 1
    assert '요청 횟수: 0' in capsys.readouterr().err
    assert main.main(['pr', '--temperature', 'nan']) == 1


def test_local_budget_blocks_before_request(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    (repo / 'sample.py').write_text('x' * 8000)
    monkeypatch.setattr(ai_client, 'generate', lambda *a: pytest.fail('unexpected API'))
    assert main.main(['pr']) == 1
    assert '요청 횟수: 0' in capsys.readouterr().err


def test_cli_outside_repo(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main.main(['pr']) == 1
    assert '요청 횟수: 0' in capsys.readouterr().err


def test_cli_api_error(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    (repo / 'sample.py').write_text('changed')
    def fail(*args):
        raise ValueError('AI 연결 실패')
    monkeypatch.setattr(ai_client, 'generate', fail)
    assert main.main(['commit']) == 1
    output = capsys.readouterr()
    assert not output.out and 'AI 연결 실패' in output.err and '요청 횟수: 1' in output.err


def test_cli_missing_key(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    monkeypatch.delenv('AI_API_KEY')
    monkeypatch.setattr(inference_server, 'local_server', lambda *a, **kw: inference_server.api_key())
    (repo / 'sample.py').write_text('changed')
    assert main.main(['commit']) == 1
    output = capsys.readouterr()
    assert 'AI_API_KEY' in output.err and '요청 횟수: 0' in output.err


def test_cli_bad_response(repo, monkeypatch, capsys):
    monkeypatch.chdir(repo)
    (repo / 'sample.py').write_text('changed')
    monkeypatch.setattr(ai_client, 'generate', lambda *a: '{}')
    assert main.main(['commit']) == 1
    output = capsys.readouterr()
    assert not output.out and '요청 횟수: 1' in output.err
