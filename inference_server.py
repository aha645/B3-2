"""프로젝트 로컬 llama-server의 준비 확인 및 소유 프로세스 관리."""
from contextlib import contextmanager
from pathlib import Path
import os
import platform
import subprocess
import time

import httpx

ROOT = Path(__file__).resolve().parent
BASE_URL = 'http://127.0.0.1:8080'
MODEL_PATH = ROOT / 'models/qwen2.5-coder-7b/qwen2.5-coder-7b-instruct-q4_k_m.gguf'
MODEL_NAME = 'qwen2.5-coder-7b-instruct'


def binary_path() -> Path:
    folder = ROOT / '.build/llama.cpp/bin'
    if platform.system() == 'Windows':
        release = folder / 'Release/llama-server.exe'
        return release if release.exists() else folder / 'llama-server.exe'
    return folder / 'llama-server'


def api_key() -> str:
    key = os.environ.get('AI_API_KEY', '')
    if not key.strip():
        raise ValueError('AI_API_KEY 환경변수를 설정하세요. 로컬 서버 인증에도 같은 키를 사용합니다')
    if key != key.strip() or any(c in key for c in '\r\n,') or not key.isascii():
        raise ValueError('AI_API_KEY는 공백으로 시작/끝나지 않는 ASCII 값이며 줄바꿈과 쉼표를 포함할 수 없습니다')
    return key


def health(client) -> bool:
    try:
        response = client.get(BASE_URL + '/health')
    except httpx.RequestError:
        return False
    if response.status_code == 503:
        return False
    if response.status_code != 200:
        raise ValueError('포트 8080에 호환되지 않는 서버가 있습니다')
    try:
        data = response.json()
    except ValueError as exc:
        raise ValueError('포트 8080의 서버가 llama-server 상태 응답을 반환하지 않습니다') from exc
    if not isinstance(data, dict) or data.get('status') != 'ok':
        raise ValueError('포트 8080의 서버 상태가 올바르지 않습니다')
    return True


def verify_server(client, key: str, model: str) -> None:
    try:
        unauthenticated = client.get(BASE_URL + '/v1/models')
        if unauthenticated.status_code not in (401, 403):
            raise ValueError('인증이 적용되지 않은 서버 또는 호환되지 않는 서비스입니다. LLAMA_API_KEY를 설정해 재시작하세요')
        response = client.get(BASE_URL + '/v1/models', headers={'Authorization': f'Bearer {key}'})
        response.raise_for_status()
        data = response.json()
        models = data['data']
        if not isinstance(models, list) or not any(isinstance(x, dict) and x.get('id') == model for x in models):
            raise ValueError('서버에 요청한 모델 alias가 없습니다. model 옵션과 서버 alias를 확인하세요')
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (401, 403):
            raise ValueError('로컬 서버 인증 실패: AI_API_KEY와 서버 키가 같은지 확인하세요') from exc
        raise ValueError(f'로컬 서버 모델 확인 실패: HTTP {exc.response.status_code}') from exc
    except (httpx.RequestError, KeyError, TypeError) as exc:
        raise ValueError('로컬 서버 모델 확인에 실패했습니다') from exc


def stop(process) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


@contextmanager
def local_server(model: str, model_path: Path = MODEL_PATH, server_path: Path | None = None, *, existing_only: bool = False, startup_timeout: float = 120):
    key = api_key()
    process = None
    with httpx.Client(timeout=2, trust_env=False) as client:
        try:
            if health(client):
                verify_server(client, key, model)
                yield
                return
            if existing_only:
                raise ValueError('실행 중인 llama-server가 없습니다. 서버를 시작하거나 auto 모드를 사용하세요')
            executable = (server_path or binary_path()).resolve()
            model_path = model_path.resolve()
            if not executable.is_file():
                raise ValueError('llama-server가 없습니다. uv run python scripts/setup_inference.py --build를 실행하세요')
            if not model_path.is_file():
                raise ValueError('GGUF 모델이 없습니다. uv run python scripts/setup_inference.py --download를 실행하세요')
            env = os.environ.copy()
            env['LLAMA_API_KEY'] = key
            # 키는 인자나 파일에 넣지 않고 자식 프로세스 환경으로만 전달한다.
            command = [str(executable), '--model', str(model_path), '--alias', model,
                       '--host', '127.0.0.1', '--port', '8080', '--ctx-size', '8192',
                       '--parallel', '1', '--no-context-shift', '--no-webui']
            try:
                process = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL,
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError as exc:
                raise ValueError('llama-server 실행 실패: 실행 권한과 빌드 라이브러리를 확인하세요') from exc
            deadline = time.monotonic() + startup_timeout
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise ValueError('llama-server가 준비 전에 종료됐습니다. 모델·메모리·포트 충돌을 확인하세요')
                if health(client):
                    verify_server(client, key, model)
                    yield
                    return
                time.sleep(0.25)
            raise ValueError('llama-server 시작 시간 초과: 모델 크기와 실행 환경을 확인하세요')
        finally:
            if process is not None:
                stop(process)
