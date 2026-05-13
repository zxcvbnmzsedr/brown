set dotenv-load := true

backend_host := "127.0.0.1"
backend_port := "8765"

default:
    @just --list

install:
    .venv/bin/pip install -r backend/requirements.txt
    pnpm install
    pnpm --prefix renderer install

migrate:
    .venv/bin/alembic upgrade head

create-user email:
    .venv/bin/python -m backend.cli create-user --email {{email}}

backend:
    .venv/bin/uvicorn backend.app:app --reload --host {{backend_host}} --port {{backend_port}}

frontend:
    pnpm dev:renderer

electron:
    pnpm dev:electron

test:
    just test-backend
    pnpm lint
    pnpm build
    pnpm exec tsc -p electron/tsconfig.json

test-backend:
    just --no-dotenv --justfile "{{justfile()}}" --working-directory "{{justfile_directory()}}" _test-backend

_test-backend:
    env -u DATABASE_URL -u CORS_ORIGINS BROWN_SKIP_DOTENV=1 pnpm test:backend

lint:
    pnpm lint

build:
    pnpm build
