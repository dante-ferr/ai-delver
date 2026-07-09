import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "..", "src"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "..", "src", "core"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "..", "src", "core", "state_managers"))
