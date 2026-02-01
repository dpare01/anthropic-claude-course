import anthropic
from typing import List, Optional, Dict, Any


class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    # Maximum number of sequential tool call rounds per query
    MAX_TOOL_ROUNDS = 2

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to tools for searching and exploring course information.

Available Tools:
1. **search_course_content** - Search within course materials for specific information, concepts, or topics
2. **get_course_outline** - Get the complete structure of a course including all lesson titles

Tool Selection Guidelines:
- Use **get_course_outline** when users ask about:
  - Course structure or overview
  - What lessons are in a course
  - List of topics covered in a course
  - Course table of contents

- Use **search_course_content** when users ask about:
  - Specific concepts, definitions, or explanations
  - Detailed information from lesson content
  - Questions that require searching through course text

- **Sequential tool calls**: You may make up to 2 tool calls per query if needed. After reviewing results from your first tool call, you can make a second call if additional information is required.
- **When to use multiple calls**: Use a second tool call when the first search did not return sufficient information, you need to search a different course/lesson, or you need both outline and content details.
- **Efficiency**: If the first tool call provides a complete answer, respond directly without additional calls.
- If a tool yields no results, state this clearly without offering alternatives

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without tools
- **Course-specific questions**: Use appropriate tool first, then answer
- **No meta-commentary**:
  - Provide direct answers only - no reasoning process, search explanations, or question-type analysis
  - Do not mention "based on the search results" or "based on the outline"

All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        # Pre-build base API parameters
        self.base_params = {"model": self.model, "temperature": 0, "max_tokens": 800}

    def generate_response(
        self,
        query: str,
        conversation_history: Optional[str] = None,
        tools: Optional[List] = None,
        tool_manager=None,
    ) -> str:
        """
        Generate AI response with optional tool usage and conversation context.

        Args:
            query: The user's question or request
            conversation_history: Previous messages for context
            tools: Available tools the AI can use
            tool_manager: Manager to execute tools

        Returns:
            Generated response as string
        """

        # Build system content efficiently - avoid string ops when possible
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        # Prepare API call parameters efficiently
        api_params = {
            **self.base_params,
            "messages": [{"role": "user", "content": query}],
            "system": system_content,
        }

        # Add tools if available
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}

        # Get response from Claude
        response = self.client.messages.create(**api_params)

        # Handle tool execution if needed
        if response.stop_reason == "tool_use" and tool_manager:
            return self._handle_tool_execution(response, api_params, tool_manager)

        # Return direct response
        return response.content[0].text

    def _handle_tool_execution(
        self, initial_response, base_params: Dict[str, Any], tool_manager
    ):
        """
        Handle execution of tool calls with support for sequential tool calling.

        Supports up to MAX_TOOL_ROUNDS sequential tool calls, allowing Claude to
        reason about previous results before deciding on the next action.

        Args:
            initial_response: The response containing tool use requests
            base_params: Base API parameters (includes tools)
            tool_manager: Manager to execute tools

        Returns:
            Final response text after tool execution(s)
        """
        messages = base_params["messages"].copy()
        current_response = initial_response
        rounds_completed = 0

        while rounds_completed < self.MAX_TOOL_ROUNDS:
            # Add assistant's tool use response to messages
            messages.append({"role": "assistant", "content": current_response.content})

            # Execute all tool calls and collect results
            tool_results = []
            for content_block in current_response.content:
                if content_block.type == "tool_use":
                    try:
                        tool_result = tool_manager.execute_tool(
                            content_block.name, **content_block.input
                        )
                    except Exception as e:
                        tool_result = f"Tool execution failed: {str(e)}"

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": tool_result,
                        }
                    )

            # Add tool results to messages
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

            rounds_completed += 1

            # Make next API call WITH tools preserved for potential follow-up
            next_params = {
                **self.base_params,
                "messages": messages,
                "system": base_params["system"],
                "tools": base_params.get("tools", []),
                "tool_choice": {"type": "auto"},
            }

            next_response = self.client.messages.create(**next_params)

            # Check if Claude wants another tool call
            if next_response.stop_reason != "tool_use":
                return self._extract_text_response(next_response)

            # Continue loop with new response
            current_response = next_response

        # Max rounds reached - make final call WITHOUT tools to force text response
        final_params = {
            **self.base_params,
            "messages": messages,
            "system": base_params["system"],
        }
        final_response = self.client.messages.create(**final_params)
        return self._extract_text_response(final_response)

    def _extract_text_response(self, response) -> str:
        """Extract text content from response blocks."""
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""
