"""llama-server OpenAI 호환 로컬 API, 생성 요청 자동 재시도 없음."""
import httpx

from inference_server import BASE_URL, api_key

URL = BASE_URL + '/v1/chat/completions'


def check_input(system: str, prompt: str, max_tokens: int) -> None:
    # 정확한 토큰 추정 대신 보수적인 UTF-8 바이트 예산 + 템플릿 여유.
    if len((system + prompt).encode('utf-8')) > 8192 - max_tokens - 1024:
        raise ValueError('로컬 모델 입력 예산을 초과합니다. 변경 범위를 줄이세요')


def generate(system: str, prompt: str, model: str, temperature: float, max_tokens: int, *, client=None) -> str:
    check_input(system, prompt, max_tokens)
    key = api_key()
    payload = {
        'model': model,
        'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': prompt}],
        'stream': False, 'response_format': {'type': 'json_object'},
        'temperature': temperature, 'max_tokens': max_tokens,
    }
    headers = {'Authorization': f'Bearer {key}'}
    try:
        if client is None:
            with httpx.Client(timeout=httpx.Timeout(300, connect=5), trust_env=False) as local:
                response = local.post(URL, json=payload, headers=headers)
        else:
            response = client.post(URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException as exc:
        raise ValueError('AI 응답 시간 초과: 입력 범위와 CPU 실행 속도를 확인하세요') from exc
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        detail = {401: '인증 실패', 403: '접근 거부', 404: '모델 alias 또는 API 경로 오류', 429: '요청 제한'}.get(code, '모델·파라미터 또는 서버 상태 확인')
        raise ValueError(f'AI API HTTP {code}: {detail}') from exc
    except httpx.RequestError as exc:
        raise ValueError('AI 연결 실패: llama-server와 포트 8080을 확인하세요') from exc
    except ValueError as exc:
        raise ValueError('AI API 응답 JSON 오류') from exc
    try:
        choice = data['choices'][0]
        text = choice['message']['content']
        finish = choice['finish_reason']
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError('AI API 응답 필수 항목이 없습니다') from exc
    if finish != 'stop':
        raise ValueError('AI 출력이 완료되지 않았습니다. max-tokens 또는 입력 범위를 조정하세요')
    if not isinstance(text, str) or not text.strip():
        raise ValueError('AI 생성 텍스트가 없습니다')
    return text
