import pytest
import os
import tempfile
from fastapi.testclient import TestClient

# Before importing app, set temporary DATABASE_URL env var
test_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
test_db_path = test_db_file.name
test_db_file.close()

os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

# Now import app components
from app.main import app
from app.database import init_db

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    # Initialize the test database tables
    init_db()
    yield
    # Clean up the temp file
    if os.path.exists(test_db_path):
        try:
            os.remove(test_db_path)
        except Exception:
            pass

@pytest.fixture
def client():
    # Provide a FastAPI TestClient
    with TestClient(app) as c:
        yield c

@pytest.fixture(autouse=True)
def clear_tables():
    # Clear tables before each test to ensure test isolation
    from app.database import get_db_connection
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM events")
        conn.execute("DELETE FROM transactions")
        conn.commit()
    finally:
        conn.close()
    yield
