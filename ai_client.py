"""Ollama 로컬 API, 자동 재시도 없음."""
import httpx

URL = 'http://127.0.0.1:11434/api/generate'


def check_input(system: str, prompt: str, max_tokens: int) -> None:
    # 토크나이저 없이 입력 누락을 피하기 위한 보수적 바이트 예산.
    # 토큰 수를 정밀 추정하지 않으며 템플릿용 1024토큰을 추가로 남긴다.
    if len((system + prompt).encode('utf-8')) > 8192 - max_tokens - 1024:
        raise ValueError('로컬 모델 입력 예산을 초과합니다. 변경 범위를 줄이세요')


def generate(system: str, prompt: str, model: str, temperature: float, max_tokens: int, *, client=None) -> str:
    check_input(system, prompt, max_tokens)
    payload = {
        'model': model, 'system': system, 'prompt': prompt,
        'stream': False, 'format': 'json', 'keep_alive': 0,
        'options': {'temperature': temperature, 'num_predict': max_tokens, 'num_ctx': 8192},
    }
    try:
        if client is None:
            with httpx.Client(timeout=httpx.Timeout(300, connect=5), trust_env=False) as local:
                response = local.post(URL, json=payload)
        else:
            response = client.post(URL, json=payload)
        response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException as exc:
        raise ValueError('AI 응답 시간 초과: 입력 범위와 CPU 실행 속도를 확인하세요') from exc
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        detail = {401: '인증 실패', 403: '접근 거부', 404: '모델 미설치 또는 API 경로 오류', 429: '요청 제한'}.get(code, '모델·파라미터 또는 서버 상태 확인')
        raise ValueError(f'AI API HTTP {code}: {detail}') from exc
    except httpx.RequestError as exc:
        raise ValueError('AI 연결 실패: ollama serve 실행과 로컬 서버를 확인하세요') from exc
    except ValueError as exc:
        raise ValueError('AI API 응답 JSON 오류') from exc
    if not isinstance(data, dict) or data.get('error'):
        raise ValueError('AI 서버가 정상 응답을 반환하지 않았습니다')
    if not data.get('done') or data.get('done_reason') == 'length':
        raise ValueError('AI 출력이 완료되지 않았습니다. max-tokens 또는 입력 범위를 조정하세요')
    # Ollama는 입력이 컨텍스트를 넘으면 잘라낼 수 있으므로 한도 근처는 성공 처리하지 않는다.
    if data.get('prompt_eval_count', 0) + max_tokens >= 8192:
        raise ValueError('모델 컨텍스트 여유가 부족합니다. 변경 범위를 줄이세요')
    text = data.get('response')
    if not isinstance(text, str) or not text.strip():
        raise ValueError('AI 생성 텍스트가 없습니다')
    return text
