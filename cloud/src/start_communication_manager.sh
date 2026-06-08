#!/bin/bash
cd "$(dirname "$0")/communication_manager"
if [ ! -d "venv" ]; then
    python -m venv venv
    source venv/Scripts/activate || source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/Scripts/activate || source venv/bin/activate
fi
python server.py
