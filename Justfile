set dotenv-load := true

server_host := "127.0.0.1"
server_port := "8765"

default:
    @just --list

install:
    .venv/bin/pip install -r server/requirements.txt
    pnpm install
    pnpm --prefix app install
    pnpm --prefix admin install

migrate:
    .venv/bin/alembic upgrade head

create-user email:
    .venv/bin/python -m server.cli create-user --email {{email}}

server:
    .venv/bin/uvicorn server.app:app --reload --host {{server_host}} --port {{server_port}}

app:
    pnpm dev:app

admin:
    pnpm dev:admin

admin-lint:
    pnpm lint:admin

admin-build:
    pnpm build:admin

test:
    just test-server
    pnpm lint
    pnpm build
    pnpm lint:admin
    pnpm build:admin

test-server:
    just --no-dotenv --justfile "{{justfile()}}" --working-directory "{{justfile_directory()}}" _test-server

_test-server:
    env -u DATABASE_URL -u CORS_ORIGINS BROWN_SKIP_DOTENV=1 pnpm test:server

lint:
    pnpm lint
    pnpm lint:admin

build:
    pnpm build
    pnpm build:admin
