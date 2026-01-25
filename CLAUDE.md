# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a RAG (Retrieval-Augmented Generation) chatbot that answers questions about course materials using semantic search and Claude AI. It's a full-stack application with a Python/FastAPI backend and vanilla HTML/CSS/JS frontend.

## Commands

### Run the application
```bash
cd backend && uv run uvicorn app:app --reload --port 8000
```
Or use the shell script: `./run.sh`

### Install dependencies
```bash
uv sync
```

### Access points
- Web UI: http://localhost:8000
- API docs: http://localhost:8000/docs

## Architecture

### Query Flow
```
Frontend (script.js) → FastAPI (app.py) → RAGSystem (rag_system.py)
                                                    ↓
                                          AIGenerator (ai_generator.py)
                                                    ↓
                                              Claude API
                                                    ↓
                                          (tool_use response)
                                                    ↓
                                    ToolManager → CourseSearchTool
                                                    ↓
                                    VectorStore → ChromaDB
                                                    ↓
                                    (results back to Claude for synthesis)
```

### Key Components

**RAGSystem** (`backend/rag_system.py`) - Main orchestrator that coordinates all components. Entry point for query processing.

**AIGenerator** (`backend/ai_generator.py`) - Handles Claude API calls with tool-calling support. Makes two API calls when tools are used: first to get tool request, second with tool results.

**VectorStore** (`backend/vector_store.py`) - ChromaDB wrapper with two collections:
- `course_catalog`: Course metadata for fuzzy name matching
- `course_content`: Chunked text with embeddings (all-MiniLM-L6-v2)

**DocumentProcessor** (`backend/document_processor.py`) - Parses course files with expected format:
```
Course Title: [title]
Course Link: [url]
Course Instructor: [instructor]

Lesson N: [title]
Lesson Link: [url]
[content...]
```
Chunks text into ~800 char segments with 100 char overlap.

**CourseSearchTool** (`backend/search_tools.py`) - Claude tool definition for `search_course_content`. Accepts query, optional course_name, and optional lesson_number filters.

**SessionManager** (`backend/session_manager.py`) - Maintains conversation history per session (max 2 exchanges).

### Configuration

Settings in `backend/config.py`:
- `CHUNK_SIZE`: 800 chars
- `CHUNK_OVERLAP`: 100 chars
- `MAX_RESULTS`: 5 search results
- `MAX_HISTORY`: 2 conversation exchanges
- `ANTHROPIC_MODEL`: claude-sonnet-4-20250514
- `EMBEDDING_MODEL`: all-MiniLM-L6-v2

### API Endpoints

- `POST /api/query` - Submit question, returns `{answer, sources, session_id}`
- `GET /api/courses` - Get course statistics

### Data Storage

- Course documents: `docs/*.txt`
- Vector database: `chroma_db/` (auto-created)
- Environment: `.env` (requires `ANTHROPIC_API_KEY`)
