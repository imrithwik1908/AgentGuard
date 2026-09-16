import argparse
import json
import os
from urllib import request

from agentguard import AgentGuard

from demo_agent.agent import answer_question


def fetch_dataset(
    base_url: str,
    dataset_id: str,
    api_key: str,
) -> dict:
    req = request.Request(
        f"{base_url.rstrip('/')}/api/v1/datasets/{dataset_id}",
        headers={
            "x-agentguard-api-key": api_key,
        },
    )

    with request.urlopen(
        req,
        timeout=20,
    ) as response:
        return json.loads(response.read())


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run an AgentGuard test suite against "
            "the reference AI application."
        )
    )

    parser.add_argument(
        "--dataset-id",
        required=True,
    )

    parser.add_argument(
        "--base-url",
        default=os.getenv(
            "AGENTGUARD_BASE_URL",
            "http://localhost:8000",
        ),
    )

    parser.add_argument(
        "--project",
        required=True,
    )

    parser.add_argument(
        "--version",
        required=True,
    )

    parser.add_argument(
        "--api-key",
        default=os.getenv(
            "AGENTGUARD_API_KEY"
        ),
    )

    args = parser.parse_args()

    if not args.api_key:
        raise RuntimeError(
            "AGENTGUARD_API_KEY is required"
        )

    dataset = fetch_dataset(
        args.base_url,
        args.dataset_id,
        args.api_key,
    )

    client = AgentGuard(
        base_url=args.base_url,
        project=args.project,
        version=args.version,
        api_key=args.api_key,
        raise_on_failure=False,
    )

    print(
        f"Running {len(dataset['cases'])} cases "
        f"against {args.project}/{args.version}"
    )

    for case in dataset["cases"]:
        question = case["input"].get(
            "question"
        )

        if not question:
            print(
                f"SKIP {case['name']}: "
                "no question input"
            )
            continue

        try:
            answer = answer_question(
                client,
                question,
                dataset_case_id=case["id"],
            )

            print(
                f"OK   {case['name']}: "
                f"{answer[:100]}"
            )

        except Exception as exc:
            print(
                f"FAIL {case['name']}: {exc}"
            )


if __name__ == "__main__":
    main()