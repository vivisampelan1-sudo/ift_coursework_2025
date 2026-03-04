"""Shared test fixtures and path setup for Pipeline B tests."""
import os
import sys

# Ensure team_RUSSEL/coursework_one/ is on the path so b_pipeline is importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
