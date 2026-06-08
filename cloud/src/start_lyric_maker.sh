#!/bin/bash
cd "$(dirname "$0")/lyric_maker"
if [ ! -d "venv" ]; then
    python -m venv venv
    source venv/Scripts/activate || source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/Scripts/activate || source venv/bin/activate
fi
python main.py
