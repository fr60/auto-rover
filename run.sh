#!/bin/bash
# run.sh — run any rover script with correct Python path
#
# Usage from project root:
#   ./run.sh tests/test_gps.py
#   ./run.sh tests/test_motors.py
#   ./run.sh firmware/main.py
 
export PYTHONPATH="$(pwd)"
python3 "$@"