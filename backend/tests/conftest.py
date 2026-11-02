import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def prevent_es_index_creation_during_tests():
    """Autouse fixture ensuring test runs do not hang trying to initialize ES index on offline hosts."""
    with patch("app.elasticsearch_client.es_client.ensure_index_exists"):
        yield

