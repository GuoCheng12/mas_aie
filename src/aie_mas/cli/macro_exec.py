from __future__ import annotations

import json
import sys

from aie_mas.macro_harness.backend import execute_macro_payload


def main() -> None:
    payload = json.loads(sys.stdin.read() or "{}")
    result = execute_macro_payload(payload)
    sys.stdout.write(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
