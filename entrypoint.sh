#!/bin/sh
set -e

# Delay to make sure the database is ready
sleep 5

alembic upgrade head

python ./seed_prompts.py

uvicorn main:app --host 0.0.0.0 --port 8000
