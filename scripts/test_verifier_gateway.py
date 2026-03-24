from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from aie_mas.config import AieMasConfig
from aie_mas.llm.openai_compatible import OpenAICompatibleVerifierClient


class VerifierGatewaySmokeResponse(BaseModel):
    ok: bool = Field(description="Whether the verifier model is reachable and responded coherently.")
    gateway_model_echo: str = Field(description="Echo the model identifier you believe you are using.")
    short_answer: str = Field(description="A short plain-text acknowledgement from the model.")


def main() -> int:
    config = AieMasConfig.from_env(
        project_root=Path(__file__).resolve().parents[1],
        tool_backend="real",
        verifier_backend="openai_sdk",
    )

    print("Verifier gateway smoke test")
    print(f"base_url: {config.verifier_base_url}")
    print(f"model: {config.verifier_model}")
    print(f"api_key_configured: {bool(config.verifier_api_key)}")
    print(f"timeout_seconds: {config.verifier_timeout_seconds}")

    if not config.verifier_api_key:
        print("\nVerifier API key is not configured.")
        print("Set AIE_MAS_VERIFIER_API_KEY first, then rerun this script.")
        return 2

    client = OpenAICompatibleVerifierClient(config)
    response = client.invoke_json_schema(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are running a connectivity smoke test for an OpenAI-compatible verifier gateway. "
                    "Respond briefly and truthfully."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Please confirm that this verifier gateway can respond to a short JSON-schema request. "
                    "Set ok=true, echo the model identifier you think is being used, and give a short acknowledgement."
                ),
            },
        ],
        response_model=VerifierGatewaySmokeResponse,
        schema_name="verifier_gateway_smoke_response",
    )

    print("\nSmoke response:")
    print(json.dumps(response.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
