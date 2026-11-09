"""llama-server의 인증·생성 옵션을 실제 생성 요청 1회로 확인한다."""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai_client
from inference_server import MODEL_NAME, MODEL_PATH, local_server


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default=MODEL_NAME)
    parser.add_argument('--model-path', type=Path, default=MODEL_PATH)
    parser.add_argument('--temperature', type=float, default=0.2)
    parser.add_argument('--max-tokens', type=int, default=64)
    args = parser.parse_args()
    if not 0 <= args.temperature <= 2 or not 1 <= args.max_tokens <= 4096:
        parser.error('temperature는 0~2, max-tokens는 1~4096이어야 합니다')
    started = time.monotonic()
    calls = 0
    try:
        with local_server(args.model, args.model_path):
            calls += 1
            text = ai_client.generate('한국어로 답하고 JSON 객체만 출력하세요.',
                                      '{"message":"로컬 모델 연결 확인"}을 출력하세요.',
                                      args.model, args.temperature, args.max_tokens)
        data = json.loads(text)
        if not isinstance(data, dict) or not isinstance(data.get('message'), str) or not data['message'].strip():
            raise ValueError('message 문자열이 포함된 JSON 응답이 아닙니다')
        print(json.dumps(data, ensure_ascii=False))
        print(f'[INFO] 서버 시작·종료 포함 소요 시간: {time.monotonic() - started:.1f}초', file=sys.stderr)
        return 0
    except ValueError as exc:
        print(f'[ERROR] {exc}', file=sys.stderr)
        return 1
    finally:
        print(f'[INFO] AI 생성 API 요청 횟수: {calls}', file=sys.stderr)


if __name__ == '__main__':
    raise SystemExit(main())
