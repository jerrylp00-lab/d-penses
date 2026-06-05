#!/bin/bash
# SCI Dashboard — lance le serveur local
# Usage : ./run.sh

cd "$(dirname "$0")"
uvicorn main:app --reload --port 8000
