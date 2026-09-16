.PHONY: api-test sdk-test demo-test web-test test lint reset-db migrate demo-success demo-failure

api-test:
	cd apps/api && PYTHONPATH=. python -m pytest

sdk-test:
	cd packages/python-sdk && PYTHONPATH=. python -m pytest

demo-test:
	cd apps/demo-agent && PYTHONPATH=.:../../packages/python-sdk python -m pytest

web-test:
	cd apps/web && npm test

test: api-test sdk-test demo-test web-test

lint:
	cd apps/api && ruff check agentguard_api tests
	cd packages/python-sdk && ruff check agentguard tests
	cd apps/demo-agent && ruff check demo_agent tests
	cd apps/web && npm run lint

migrate:
	cd apps/api && alembic upgrade head

reset-db:
	docker compose down -v
	docker compose up -d postgres
	cd apps/api && alembic upgrade head

demo-success:
	cd apps/demo-agent && PYTHONPATH=../../packages/python-sdk python -m demo_agent.run_demo --question "What is AgentGuard?"

demo-failure:
	cd apps/demo-agent && PYTHONPATH=../../packages/python-sdk python -m demo_agent.run_demo --question "please fail generation"
