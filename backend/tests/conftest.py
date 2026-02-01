"""
Shared pytest fixtures for RAG system tests.
"""
import pytest
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass
from typing import List

import sys
from pathlib import Path

# Add backend to path for imports
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))


@dataclass
class MockConfig:
    """Test configuration that doesn't require environment variables."""
    ANTHROPIC_API_KEY: str = "test-api-key"
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100
    MAX_RESULTS: int = 5
    MAX_HISTORY: int = 2
    CHROMA_PATH: str = ":memory:"


@pytest.fixture
def mock_config():
    """Provide a test configuration."""
    return MockConfig()


@pytest.fixture
def mock_rag_system():
    """Create a mock RAG system for testing API endpoints."""
    mock = MagicMock()

    # Configure session manager
    mock.session_manager.create_session.return_value = "test_session_1"
    mock.session_manager.delete_session.return_value = True

    # Configure query response
    from models import Source
    mock.query.return_value = (
        "This is a test answer about the course content.",
        [Source(title="Test Course - Lesson 1", url="https://example.com/lesson1")]
    )

    # Configure course analytics
    mock.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Test Course 1", "Test Course 2"]
    }

    return mock


@pytest.fixture
def mock_sources():
    """Provide sample Source objects for testing."""
    from models import Source
    return [
        Source(title="Course A - Lesson 1", url="https://example.com/a/1"),
        Source(title="Course A - Lesson 2", url="https://example.com/a/2"),
        Source(title="Course B - Lesson 1", url=None),
    ]


@pytest.fixture
def sample_query_request():
    """Provide a sample query request payload."""
    return {
        "query": "What is machine learning?",
        "session_id": None
    }


@pytest.fixture
def sample_query_request_with_session():
    """Provide a sample query request with an existing session."""
    return {
        "query": "Tell me more about neural networks",
        "session_id": "existing_session_123"
    }
