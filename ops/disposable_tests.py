"""Expose the shared run-owned resource manager to standalone ops scripts."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from config.disposable_tests import DisposableRun, test_database_name
