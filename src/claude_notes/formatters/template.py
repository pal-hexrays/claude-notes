"""Template-based formatter for Claude conversations."""

import html
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader, Template, select_autoescape

from claude_notes.formatters.base import BaseFormatter


class TemplateFormatter(BaseFormatter):
    """Format Claude conversations using Jinja2 templates."""

    def __init__(self, template_path: str | Path | None = None):
        """Initialize the template formatter.
        
        Args:
            template_path: Path to template file or template name
        """
        super().__init__()
        self.template_path = template_path
        self.env = None
        self.template = None
        self._setup_template()

    def _setup_template(self) -> None:
        """Set up the Jinja2 environment and load template."""
        # Get built-in templates directory
        package_dir = Path(__file__).parent.parent
        templates_dir = package_dir / "templates"
        
        # Template search paths
        search_paths = [templates_dir]
        
        if self.template_path:
            template_path = Path(self.template_path)
            if template_path.is_absolute() and template_path.exists():
                # Absolute path to specific template file
                search_paths.insert(0, template_path.parent)
                self.template_name = template_path.name
            elif (Path.cwd() / "templates" / template_path).exists():
                # Relative path in local templates directory
                search_paths.insert(0, Path.cwd() / "templates")
                self.template_name = str(template_path)
            elif (templates_dir / f"{template_path}.html").exists():
                # Built-in template by name (without .html extension)
                self.template_name = f"{template_path}.html"
            elif (templates_dir / template_path).exists():
                # Built-in template with extension
                self.template_name = str(template_path)
            else:
                # Try as filename directly
                self.template_name = str(template_path)
        else:
            # Use default template
            self.template_name = "default.html"

        # Set up Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(search_paths),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Add custom filters
        self.env.filters['humanize_date'] = self._humanize_date
        self.env.filters['format_tool_use'] = self._format_tool_use
        self.env.filters['basename'] = lambda path: Path(path).name if path else ""
        
        # Load the template
        try:
            self.template = self.env.get_template(self.template_name)
        except Exception as e:
            raise ValueError(f"Could not load template '{self.template_name}': {e}")

    def format_conversation(self, messages: list[dict[str, Any]], conversation_info: dict[str, Any]) -> str:
        """Format a single conversation using the template."""
        # Collect tool results
        self._collect_tool_results(messages)
        
        # Prepare template data for a single conversation
        template_data = {
            "conversation": {
                "info": conversation_info,
                "messages": self._prepare_messages(messages)
            },
            "metadata": {
                "title": "Claude Conversation",
                "generated_at": datetime.now().isoformat(),
                "single_conversation": True
            }
        }
        
        return self.template.render(template_data)

    def format_conversations(self, conversations: list[dict[str, Any]]) -> str:
        """Format multiple conversations using the template.
        
        This method is designed to be called from the CLI for multi-conversation rendering.
        """
        # Prepare all conversations
        prepared_conversations = []
        for conv in conversations:
            self._collect_tool_results(conv["messages"])
            prepared_conversations.append({
                "info": conv["info"],
                "messages": self._prepare_messages(conv["messages"])
            })
        
        # Prepare template data for multiple conversations
        template_data = {
            "conversations": prepared_conversations,
            "metadata": {
                "title": "Claude Conversations",
                "generated_at": datetime.now().isoformat(),
                "total_conversations": len(prepared_conversations),
                "has_multiple_conversations": len(prepared_conversations) > 1,
                "single_conversation": False
            }
        }
        
        return self.template.render(template_data)

    def _prepare_messages(self, messages: list[dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prepare messages for template rendering."""
        # Group messages by role continuity
        grouped_messages = self._group_messages(messages)
        
        prepared_groups = []
        
        for i, group in enumerate(grouped_messages):
            if not group:
                continue
                
            # Get role from first message
            first_msg = group[0]
            message_data = first_msg.get("message", {})
            role = message_data.get("role", "unknown")
            
            # Prepare message content
            content_parts = []
            tool_uses = []
            
            for msg in group:
                msg_data = msg.get("message", {})
                content = msg_data.get("content", "")
                
                if isinstance(content, str):
                    if content.strip():
                        content_parts.append({
                            "type": "text",
                            "text": content,
                            "html": self._format_text_content(content)
                        })
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            if item.get("type") == "text":
                                text_content = item.get("text", "")
                                if text_content.strip():
                                    content_parts.append({
                                        "type": "text",
                                        "text": text_content,
                                        "html": self._format_text_content(text_content)
                                    })
                            elif item.get("type") == "tool_use":
                                tool_uses.append({
                                    "name": item.get("name", "Unknown Tool"),
                                    "input": item.get("input", {}),
                                    "id": item.get("id"),
                                    "result": self._tool_results.get(msg.get("uuid", ""))
                                })
            
            # Create message group
            prepared_group = {
                "role": role,
                "role_icon": "👤" if role == "user" else "🤖" if role == "assistant" else "⚙️",
                "role_name": role.title(),
                "timestamp": group[0].get("timestamp"),
                "message_number": i + 1,
                "content_parts": content_parts,
                "tool_uses": tool_uses,
                "has_content": len(content_parts) > 0,
                "has_tools": len(tool_uses) > 0
            }
            
            prepared_groups.append(prepared_group)
        
        return prepared_groups

    def _format_text_content(self, content: str) -> str:
        """Format text content as HTML."""
        if not content.strip():
            return ""
        
        # Escape HTML first
        content = html.escape(content)
        
        # Basic markdown conversion
        import re
        
        # Bold **text**
        content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
        
        # Italic *text*
        content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', content)
        
        # Code `code`
        content = re.sub(r'`(.*?)`', r'<code>\1</code>', content)
        
        # Headers
        content = re.sub(r'^### (.*?)$', r'<h3>\1</h3>', content, flags=re.MULTILINE)
        content = re.sub(r'^## (.*?)$', r'<h2>\1</h2>', content, flags=re.MULTILINE)
        content = re.sub(r'^# (.*?)$', r'<h1>\1</h1>', content, flags=re.MULTILINE)
        
        # Line breaks
        content = content.replace('\n', '<br>\n')
        
        return content

    def _humanize_date(self, timestamp_str: str) -> str:
        """Jinja2 filter to humanize date strings."""
        if not timestamp_str:
            return "Unknown time"
            
        try:
            from datetime import timezone
            # Parse the ISO timestamp
            dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)

            # Calculate time difference
            diff = now - dt
            total_seconds = diff.total_seconds()

            if total_seconds < 60:
                return "just now"
            elif total_seconds < 3600:  # Less than 1 hour
                minutes = int(total_seconds / 60)
                return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            elif total_seconds < 86400:  # Less than 1 day
                hours = int(total_seconds / 3600)
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
            elif total_seconds < 2592000:  # Less than 30 days
                days = int(total_seconds / 86400)
                return f"{days} day{'s' if days != 1 else ''} ago"
            else:
                # For older dates, show the actual date
                local_dt = dt.astimezone()
                return local_dt.strftime("%B %d, %Y at %I:%M %p")
        except (ValueError, TypeError):
            # Fallback for unparseable dates
            return timestamp_str

    def _format_tool_use(self, tool_use: dict) -> str:
        """Jinja2 filter to format tool usage using full HTML formatters."""
        from claude_notes.formatters.html import HTML_TOOL_FORMATTERS
        
        tool_name = tool_use.get("name", "Unknown Tool")
        tool_input = tool_use.get("input", {})
        tool_result = tool_use.get("result")
        
        # Use the same formatters as the HTML formatter
        formatter = HTML_TOOL_FORMATTERS.get(tool_name)
        if formatter:
            return formatter.format({"input": tool_input}, tool_result)
        else:
            # Fallback for unknown tools
            return f'<div class="tool-use unknown-tool"><span class="tool-icon">🔧</span> <strong>{html.escape(tool_name)}</strong></div>'

    def format_tool_use(self, tool_name: str, tool_use: dict[str, Any], tool_result: str | None = None) -> str:
        """Format a tool use with its result (required by BaseFormatter)."""
        return self._format_tool_use({
            "name": tool_name,
            "input": tool_use.get("input", {}),
            "result": tool_result
        })