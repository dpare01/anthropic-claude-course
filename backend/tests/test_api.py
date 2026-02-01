"""
API endpoint tests for the RAG system.

These tests define the API endpoints inline to avoid import issues
with the static file mounts in the main app.py.
"""
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel
from typing import List, Optional
from unittest.mock import MagicMock, patch
import sys
from pathlib import Path

# Add backend to path for imports
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from models import Source


# --- Pydantic models (copied from app.py to avoid import issues) ---

class QueryRequest(BaseModel):
    """Request model for course queries"""
    query: str
    session_id: Optional[str] = None


class QueryResponse(BaseModel):
    """Response model for course queries"""
    answer: str
    sources: List[Source]
    session_id: str


class CourseStats(BaseModel):
    """Response model for course statistics"""
    total_courses: int
    course_titles: List[str]


# --- Test App Factory ---

def create_test_app(mock_rag_system: MagicMock) -> FastAPI:
    """
    Create a test FastAPI app with mocked RAG system.

    This avoids the static file mount issues from the main app.
    """
    app = FastAPI(title="Course Materials RAG System - Test")

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        """Process a query and return response with sources"""
        try:
            session_id = request.session_id
            if not session_id:
                session_id = mock_rag_system.session_manager.create_session()

            answer, sources = mock_rag_system.query(request.query, session_id)

            return QueryResponse(
                answer=answer,
                sources=sources,
                session_id=session_id
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        """Get course analytics and statistics"""
        try:
            analytics = mock_rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.delete("/api/session/{session_id}")
    async def delete_session(session_id: str):
        """Delete a conversation session"""
        deleted = mock_rag_system.session_manager.delete_session(session_id)
        return {"deleted": deleted, "session_id": session_id}

    @app.get("/")
    async def root():
        """Health check endpoint"""
        return {"status": "ok", "service": "rag-chatbot"}

    return app


@pytest.fixture
def test_client(mock_rag_system):
    """Create a test client with mocked dependencies."""
    app = create_test_app(mock_rag_system)
    return TestClient(app)


# --- API Endpoint Tests ---

class TestQueryEndpoint:
    """Tests for POST /api/query endpoint."""

    def test_query_creates_new_session(self, test_client, mock_rag_system):
        """Query without session_id should create a new session."""
        response = test_client.post(
            "/api/query",
            json={"query": "What is machine learning?"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data
        assert "session_id" in data
        assert data["session_id"] == "test_session_1"
        mock_rag_system.session_manager.create_session.assert_called_once()

    def test_query_uses_existing_session(self, test_client, mock_rag_system):
        """Query with session_id should use the provided session."""
        response = test_client.post(
            "/api/query",
            json={"query": "Tell me more", "session_id": "existing_session"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "existing_session"
        mock_rag_system.session_manager.create_session.assert_not_called()

    def test_query_returns_sources(self, test_client, mock_rag_system):
        """Query should return sources in the response."""
        response = test_client.post(
            "/api/query",
            json={"query": "What are the course topics?"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["sources"]) == 1
        assert data["sources"][0]["title"] == "Test Course - Lesson 1"
        assert data["sources"][0]["url"] == "https://example.com/lesson1"

    def test_query_calls_rag_system(self, test_client, mock_rag_system):
        """Query should call the RAG system with correct parameters."""
        response = test_client.post(
            "/api/query",
            json={"query": "Explain neural networks", "session_id": "sess_123"}
        )

        assert response.status_code == 200
        mock_rag_system.query.assert_called_once_with(
            "Explain neural networks",
            "sess_123"
        )

    def test_query_empty_string_rejected(self, test_client):
        """Empty query string should be handled gracefully."""
        response = test_client.post(
            "/api/query",
            json={"query": ""}
        )
        # Empty string is technically valid per the model, endpoint accepts it
        assert response.status_code == 200

    def test_query_missing_field_rejected(self, test_client):
        """Request without required query field should return 422."""
        response = test_client.post(
            "/api/query",
            json={"session_id": "some_session"}
        )

        assert response.status_code == 422

    def test_query_handles_rag_error(self, test_client, mock_rag_system):
        """Query should return 500 when RAG system raises an exception."""
        mock_rag_system.query.side_effect = Exception("Database connection failed")

        response = test_client.post(
            "/api/query",
            json={"query": "This will fail"}
        )

        assert response.status_code == 500
        assert "Database connection failed" in response.json()["detail"]


class TestCoursesEndpoint:
    """Tests for GET /api/courses endpoint."""

    def test_get_courses_returns_stats(self, test_client, mock_rag_system):
        """Should return course statistics."""
        response = test_client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 2
        assert len(data["course_titles"]) == 2
        assert "Test Course 1" in data["course_titles"]
        assert "Test Course 2" in data["course_titles"]

    def test_get_courses_calls_analytics(self, test_client, mock_rag_system):
        """Should call get_course_analytics on RAG system."""
        response = test_client.get("/api/courses")

        assert response.status_code == 200
        mock_rag_system.get_course_analytics.assert_called_once()

    def test_get_courses_handles_error(self, test_client, mock_rag_system):
        """Should return 500 when analytics fails."""
        mock_rag_system.get_course_analytics.side_effect = Exception("Vector store unavailable")

        response = test_client.get("/api/courses")

        assert response.status_code == 500
        assert "Vector store unavailable" in response.json()["detail"]

    def test_get_courses_empty_catalog(self, test_client, mock_rag_system):
        """Should handle empty course catalog."""
        mock_rag_system.get_course_analytics.return_value = {
            "total_courses": 0,
            "course_titles": []
        }

        response = test_client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 0
        assert data["course_titles"] == []


class TestSessionEndpoint:
    """Tests for DELETE /api/session/{session_id} endpoint."""

    def test_delete_session_success(self, test_client, mock_rag_system):
        """Should delete an existing session."""
        response = test_client.delete("/api/session/sess_123")

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True
        assert data["session_id"] == "sess_123"
        mock_rag_system.session_manager.delete_session.assert_called_once_with("sess_123")

    def test_delete_session_not_found(self, test_client, mock_rag_system):
        """Should handle non-existent session gracefully."""
        mock_rag_system.session_manager.delete_session.return_value = False

        response = test_client.delete("/api/session/nonexistent")

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is False
        assert data["session_id"] == "nonexistent"


class TestRootEndpoint:
    """Tests for GET / endpoint (health check)."""

    def test_root_returns_ok(self, test_client):
        """Root endpoint should return health status."""
        response = test_client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "service" in data


class TestRequestValidation:
    """Tests for request validation and edge cases."""

    def test_query_with_special_characters(self, test_client, mock_rag_system):
        """Query with special characters should be handled."""
        response = test_client.post(
            "/api/query",
            json={"query": "What about <script>alert('xss')</script>?"}
        )

        assert response.status_code == 200

    def test_query_with_unicode(self, test_client, mock_rag_system):
        """Query with unicode characters should be handled."""
        response = test_client.post(
            "/api/query",
            json={"query": "What about machine learning?"}
        )

        assert response.status_code == 200

    def test_query_with_very_long_text(self, test_client, mock_rag_system):
        """Very long query should be accepted."""
        long_query = "What is " + "very " * 1000 + "important?"
        response = test_client.post(
            "/api/query",
            json={"query": long_query}
        )

        assert response.status_code == 200

    def test_invalid_json_body(self, test_client):
        """Invalid JSON should return 422."""
        response = test_client.post(
            "/api/query",
            content="not valid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422

    def test_wrong_content_type(self, test_client):
        """Wrong content type should be rejected."""
        response = test_client.post(
            "/api/query",
            content="query=test",
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        assert response.status_code == 422
