#!/bin/sh
# DarkStore Ops Tracker quick start: create venv, install deps, seed demo
# data, print the daily summary, then start the web app.
set -e
cd "$(dirname "$0")"
python3 -m venv .venv 2>/dev/null || true
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -m darkstore.cli seed
.venv/bin/python -m darkstore.cli demo
echo ""
echo "Starting the web app at http://127.0.0.1:5000 ..."
.venv/bin/python -m darkstore.cli serve
