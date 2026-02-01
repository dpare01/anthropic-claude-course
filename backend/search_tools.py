from typing import Dict, Any, Optional, Protocol
from abc import ABC, abstractmethod
from vector_store import VectorStore, SearchResults


class Tool(ABC):
    """Abstract base class for all tools"""

    @abstractmethod
    def get_tool_definition(self) -> Dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """Execute the tool with given parameters"""
        pass


class CourseSearchTool(Tool):
    """Tool for searching course content with semantic course name matching"""

    def __init__(self, vector_store: VectorStore):
        self.store = vector_store
        self.last_sources = []  # Track sources from last search

    def get_tool_definition(self) -> Dict[str, Any]:
        """Return Anthropic tool definition for this tool"""
        return {
            "name": "search_course_content",
            "description": "Search course materials with smart course name matching and lesson filtering",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for in the course content",
                    },
                    "course_name": {
                        "type": "string",
                        "description": "Course title (partial matches work, e.g. 'MCP', 'Introduction')",
                    },
                    "lesson_number": {
                        "type": "integer",
                        "description": "Specific lesson number to search within (e.g. 1, 2, 3)",
                    },
                },
                "required": ["query"],
            },
        }

    def execute(
        self,
        query: str,
        course_name: Optional[str] = None,
        lesson_number: Optional[int] = None,
    ) -> str:
        """
        Execute the search tool with given parameters.

        Args:
            query: What to search for
            course_name: Optional course filter
            lesson_number: Optional lesson filter

        Returns:
            Formatted search results or error message
        """

        # Use the vector store's unified search interface
        results = self.store.search(
            query=query, course_name=course_name, lesson_number=lesson_number
        )

        # Handle errors
        if results.error:
            return results.error

        # Handle empty results
        if results.is_empty():
            filter_info = ""
            if course_name:
                filter_info += f" in course '{course_name}'"
            if lesson_number:
                filter_info += f" in lesson {lesson_number}"
            return f"No relevant content found{filter_info}."

        # Format and return results
        return self._format_results(results)

    def _format_results(self, results: SearchResults) -> str:
        """Format search results with course and lesson context"""
        formatted = []
        sources = []
        seen_titles = set()  # for deduplication

        for doc, meta in zip(results.documents, results.metadata):
            course_title = meta.get("course_title", "unknown")
            lesson_num = meta.get("lesson_number")

            # Build context header
            header = f"[{course_title}"
            if lesson_num is not None:
                header += f" - Lesson {lesson_num}"
            header += "]"

            # Build source title
            source_title = course_title
            if lesson_num is not None:
                source_title += f" - Lesson {lesson_num}"

            # Look up lesson link (only if not already seen)
            if source_title not in seen_titles:
                seen_titles.add(source_title)
                lesson_link = None
                if lesson_num is not None:
                    lesson_link = self.store.get_lesson_link(course_title, lesson_num)
                sources.append({"title": source_title, "url": lesson_link})

            formatted.append(f"{header}\n{doc}")

        # Store sources for retrieval
        self.last_sources = sources

        return "\n\n".join(formatted)


class CourseOutlineTool(Tool):
    """Tool for retrieving course outline including all lessons"""

    def __init__(self, vector_store: VectorStore):
        self.store = vector_store
        self.last_sources = []

    def get_tool_definition(self) -> Dict[str, Any]:
        return {
            "name": "get_course_outline",
            "description": "Get the complete outline of a course including its title, course link, and list of all lessons with their numbers and titles. Use this when users ask about course structure, what lessons are in a course, or want an overview of course content.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "course_title": {
                        "type": "string",
                        "description": "The course title to get the outline for (partial matches work, e.g. 'MCP', 'Introduction')",
                    }
                },
                "required": ["course_title"],
            },
        }

    def execute(self, course_title: str) -> str:
        """Execute the course outline tool"""
        import json

        # Resolve course name using fuzzy matching
        resolved_title = self.store._resolve_course_name(course_title)

        if not resolved_title:
            return f"No course found matching '{course_title}'. Please try a different course name."

        # Get course metadata by ID
        try:
            results = self.store.course_catalog.get(ids=[resolved_title])
            if not results or not results["metadatas"] or not results["metadatas"][0]:
                return f"Course '{resolved_title}' found but metadata unavailable."
            metadata = results["metadatas"][0]
        except Exception as e:
            return f"Error retrieving course data: {str(e)}"

        # Extract course information
        title = metadata.get("title", resolved_title)
        course_link = metadata.get("course_link")
        lessons_json = metadata.get("lessons_json", "[]")

        try:
            lessons = json.loads(lessons_json)
        except json.JSONDecodeError:
            lessons = []

        # Format output
        return self._format_outline(title, course_link, lessons)

    def _format_outline(
        self, title: str, course_link: Optional[str], lessons: list
    ) -> str:
        """Format course outline for display"""
        lines = [f"**{title}**"]
        if course_link:
            lines.append(f"Course Link: {course_link}")
        lines.append("")

        if not lessons:
            lines.append("This course has no lessons listed.")
        else:
            lines.append(f"**Lessons ({len(lessons)} total):**")
            for lesson in lessons:
                lesson_num = lesson.get("lesson_number", "?")
                lesson_title = lesson.get("lesson_title", "Untitled")
                lines.append(f"  {lesson_num}. {lesson_title}")

        # Store source for retrieval
        self.last_sources = [{"title": title, "url": course_link}]

        return "\n".join(lines)


class ToolManager:
    """Manages available tools for the AI"""

    def __init__(self):
        self.tools = {}

    def register_tool(self, tool: Tool):
        """Register any tool that implements the Tool interface"""
        tool_def = tool.get_tool_definition()
        tool_name = tool_def.get("name")
        if not tool_name:
            raise ValueError("Tool must have a 'name' in its definition")
        self.tools[tool_name] = tool

    def get_tool_definitions(self) -> list:
        """Get all tool definitions for Anthropic tool calling"""
        return [tool.get_tool_definition() for tool in self.tools.values()]

    def execute_tool(self, tool_name: str, **kwargs) -> str:
        """Execute a tool by name with given parameters"""
        if tool_name not in self.tools:
            return f"Tool '{tool_name}' not found"

        return self.tools[tool_name].execute(**kwargs)

    def get_last_sources(self) -> list:
        """Get sources from the last search operation"""
        # Check all tools for last_sources attribute
        for tool in self.tools.values():
            if hasattr(tool, "last_sources") and tool.last_sources:
                return tool.last_sources
        return []

    def reset_sources(self):
        """Reset sources from all tools that track sources"""
        for tool in self.tools.values():
            if hasattr(tool, "last_sources"):
                tool.last_sources = []
