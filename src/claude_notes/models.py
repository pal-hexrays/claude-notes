"""Pydantic models for Claude Code transcript messages."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Role of the message sender."""

    USER = "user"
    ASSISTANT = "assistant"


class ContentType(str, Enum):
    """Type of content in a message."""

    TEXT = "text"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"


class EntryType(str, Enum):
    """Type of transcript entry."""

    USER = "user"
    ASSISTANT = "assistant"
    SUMMARY = "summary"
    SYSTEM = "system"


class TextContent(BaseModel):
    """Text content in a message."""

    type: str = Field(default="text")
    text: str


class ToolUseContent(BaseModel):
    """Tool use content in an assistant message."""

    type: str = Field(default="tool_use")
    id: str
    name: str
    input: Dict[str, Any]


class ToolResultContent(BaseModel):
    """Tool result content in a user message."""

    type: str = Field(default="tool_result")
    content: str
    is_error: bool
    tool_use_id: str


class CacheCreationInfo(BaseModel):
    """Cache creation information."""

    ephemeral_5m_input_tokens: Optional[int] = None
    ephemeral_1h_input_tokens: Optional[int] = None


class UsageInfo(BaseModel):
    """Token usage information for assistant messages."""

    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cache_creation_input_tokens: Optional[int] = None
    cache_read_input_tokens: Optional[int] = None
    cache_creation: Optional[CacheCreationInfo] = None
    service_tier: Optional[str] = None


class Message(BaseModel):
    """Message content from user or assistant."""

    role: MessageRole
    content: Union[
        str,  # Simple string content (typically user messages)
        List[Union[TextContent, ToolUseContent, ToolResultContent, Dict[str, Any]]],  # Complex content
    ]
    # Assistant-specific fields
    id: Optional[str] = None
    type: Optional[str] = None
    model: Optional[str] = None
    stop_reason: Optional[str] = None
    stop_sequence: Optional[str] = None
    usage: Optional[UsageInfo] = None

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class CompactMetadata(BaseModel):
    """Metadata for conversation compaction."""

    trigger: Optional[str] = None
    preTokens: Optional[int] = None


class TranscriptEntry(BaseModel):
    """Single entry in a Claude Code transcript."""

    type: str  # "user", "assistant", "summary", "system"
    uuid: Optional[str] = None  # Make optional for summary entries
    timestamp: Optional[Union[datetime, str]] = None  # Can be ISO string or datetime, optional for summaries

    # Common fields
    parentUuid: Optional[str] = None
    sessionId: Optional[str] = None
    cwd: Optional[str] = None
    version: Optional[str] = None
    gitBranch: Optional[str] = None
    userType: Optional[str] = None
    isSidechain: Optional[bool] = None

    # Message content (for user/assistant entries)
    message: Optional[Message] = None
    requestId: Optional[str] = None  # For assistant messages

    # Summary entry fields
    summary: Optional[str] = None
    leafUuid: Optional[str] = None

    # System entry fields
    subtype: Optional[str] = None
    content: Optional[str] = None
    level: Optional[str] = None
    isMeta: Optional[bool] = None
    compactMetadata: Optional[CompactMetadata] = None

    # Tool result field for user messages
    toolUseResult: Optional[Union[str, Dict[str, Any], List[Any]]] = None

    # Additional fields
    logicalParentUuid: Optional[str] = None
    isVisibleInTranscriptOnly: Optional[bool] = None
    isCompactSummary: Optional[bool] = None

    class Config:
        """Pydantic configuration."""

        extra = "allow"  # Allow extra fields we haven't mapped yet

    def is_user_message(self) -> bool:
        """Check if this is a user message."""
        return self.type == "user" and self.message is not None

    def is_assistant_message(self) -> bool:
        """Check if this is an assistant message."""
        return self.type == "assistant" and self.message is not None

    def is_summary(self) -> bool:
        """Check if this is a summary entry."""
        return self.type == "summary"

    def is_system(self) -> bool:
        """Check if this is a system entry."""
        return self.type == "system"

    def get_text_content(self) -> Optional[str]:
        """Extract text content from the message if available."""
        if not self.message:
            return None

        content = self.message.content

        # Simple string content
        if isinstance(content, str):
            return content

        # Complex content array
        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                elif isinstance(item, TextContent):
                    text_parts.append(item.text)
            return "\n".join(text_parts) if text_parts else None

        return None
