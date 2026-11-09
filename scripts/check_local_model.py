"""로컬 모델과 생성 옵션을 1회 요청으로 확인한다. Git 데이터는 전송하지 않는다."""

import argparse
import json
import sys
import time

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen2.5-coder:7b")
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=int, default=64)
    args = parser.parse_args()
    if not 0 <= args.temperature <= 2 or args.max_tokens <= 0:
        parser.error("temperature는 0~2, max-tokens는 양수여야 합니다")
    started = time.monotonic()
    print("[INFO] AI API 요청 횟수: 1", file=sys.stderr)
    try:
        # 환경 프록시를 거치지 않고 loopback 서버에만 연결한다.
        with httpx.Client(timeout=180, trust_env=False) as client:
            response = client.post(
                "http://127.0.0.1:11434/api/generate",
                json={
                    "model": args.model,
                    "prompt": '한국어로 짧게 답하세요. {"message":"로컬 모델 연결 확인"} 형태의 JSON만 출력하세요.',
                    "stream": False,
                    "format": "json",
                    "keep_alive": 0,
                    "options": {
                        "temperature": args.temperature,
                        "num_predict": args.max_tokens,
                        "num_ctx": 2048,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
        if not data.get("done") or data.get("done_reason") == "length":
            raise ValueError("응답이 완료되지 않았거나 출력 토큰 한도에 도달했습니다")
        generated = json.loads(data["response"])
        if not isinstance(generated, dict) or not isinstance(generated.get("message"), str) or not generated["message"].strip():
            raise ValueError("message 문자열이 포함된 JSON 응답이 아닙니다")
        print(json.dumps(generated, ensure_ascii=False))
        print(f"[INFO] 출력 토큰: {data.get('eval_count')}, 소요 시간: {time.monotonic() - started:.1f}초", file=sys.stderr)
        return 0
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        print(f"[ERROR] 로컬 모델 확인 실패: {type(exc).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
