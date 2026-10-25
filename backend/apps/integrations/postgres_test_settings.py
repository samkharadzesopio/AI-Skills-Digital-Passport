"""Combined suite settings restricted to an explicitly configured loopback PostgreSQL."""

import os

# Keep the documented integration test entry point aligned with the shared
# foundation/authentication harness; it never loads config.settings or .env.
from config.auth_test_settings import *  # noqa: F403

DATABASES['default']['TEST']['NAME'] = os.environ.get(
    'INTEGRATION_TEST_DB_NAME', 'test_integration_candidate'
)
