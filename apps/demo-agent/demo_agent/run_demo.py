import argparse
import os

from agentguard import AgentGuard

from demo_agent.agent import answer_question


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the deterministic AgentGuard demo agent.")
    parser.add_argument("--question", default="What is AgentGuard?")
    parser.add_argument("--base-url", default=os.getenv("AGENTGUARD_BASE_URL", "http://localhost:8000"))
    parser.add_argument("--project", default=os.getenv("AGENTGUARD_PROJECT", "research-agent"))
    parser.add_argument("--version", default=os.getenv("AGENTGUARD_VERSION", "v1"))
    parser.add_argument("--api-key", default=os.getenv("AGENTGUARD_API_KEY"))
    parser.add_argument("--raise-on-failure", action="store_true")
    args = parser.parse_args()

    client = AgentGuard(
        base_url=args.base_url,
        project=args.project,
        version=args.version,
        api_key=args.api_key,
        raise_on_failure=args.raise_on_failure,
    )
    answer = answer_question(client, args.question)
    print(answer)


if __name__ == "__main__":
    main()
