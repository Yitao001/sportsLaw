#!/bin/bash
cd "$(dirname "$0")"
export USERNAME=developer
export USER=developer
echo "启动 SportsLax 服务..."
python -m uvicorn api:app --host 0.0.0.0 --port 8000
