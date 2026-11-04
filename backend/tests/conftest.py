import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Ensure dummy Groq key for tests if not set
if not os.environ.get("GROQ_API_KEY"):
    os.environ["GROQ_API_KEY"] = "gsk_dummy_test_key_for_unit_tests"

# Set default transport mode to MEMORY for fast isolated unit tests
if not os.environ.get("PULSE_TRANSPORT_MODE"):
    os.environ["PULSE_TRANSPORT_MODE"] = "MEMORY"
