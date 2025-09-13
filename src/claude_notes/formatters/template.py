"""Template-based formatter for Claude conversations."""

import html
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader, Template, select_autoescape

from claude_notes.formatters.base import BaseFormatter
from claude_notes.models import TranscriptEntry


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
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Add custom filters
        self.env.filters["humanize_date"] = self._humanize_date
        self.env.filters["format_tool_use"] = self._format_tool_use
        self.env.filters["basename"] = lambda path: Path(path).name if path else ""
        self.env.filters["format_text_html"] = self._format_text_content
        self.env.filters["get_text_content"] = lambda msg: msg.get_text_content() if hasattr(msg, 'get_text_content') else ""
        self.env.filters["is_user_message"] = lambda msg: msg.is_user_message() if hasattr(msg, 'is_user_message') else False
        self.env.filters["is_assistant_message"] = lambda msg: msg.is_assistant_message() if hasattr(msg, 'is_assistant_message') else False
        self.env.filters["format_time_only"] = self._format_time_only
        self.env.filters["format_date_header"] = self._format_date_header
        self.env.filters["get_message_date"] = self._get_message_date

        # Load the template
        try:
            self.template = self.env.get_template(self.template_name)
        except Exception as e:
            raise ValueError(f"Could not load template '{self.template_name}': {e}")

    def format_conversation(self, messages: list[TranscriptEntry], conversation_info: dict[str, Any]) -> str:
        """Format a single conversation using the template."""
        # Collect tool results
        self._collect_tool_results(messages)

        # Group messages for easier template rendering
        grouped_messages = self._group_messages(messages)

        # Pass TranscriptEntry objects directly to template
        template_data = {
            "conversation": {
                "info": conversation_info, 
                "messages": messages,  # Raw TranscriptEntry objects
                "grouped_messages": grouped_messages  # Grouped by role
            },
            "metadata": {
                "title": "Claude Conversation",
                "generated_at": datetime.now().isoformat(),
                "single_conversation": True,
            },
            "tool_results": self._tool_results,  # Pass tool results mapping
        }

        return self.template.render(template_data)

    def format_conversations(self, conversations: list[dict[str, Any]]) -> str:
        """Format multiple conversations using the template.

        This method is designed to be called from the CLI for multi-conversation rendering.
        """
        # Collect tool results for all conversations
        all_tool_results = {}
        prepared_conversations = []
        
        for conv in conversations:
            self._collect_tool_results(conv["messages"])
            all_tool_results.update(self._tool_results)
            
            # Group messages for this conversation
            grouped_messages = self._group_messages(conv["messages"])
            
            prepared_conversations.append({
                "info": conv["info"], 
                "messages": conv["messages"],  # Raw TranscriptEntry objects
                "grouped_messages": grouped_messages  # Grouped by role
            })

        # Pass TranscriptEntry objects directly to template
        template_data = {
            "conversations": prepared_conversations,
            "metadata": {
                "title": "Claude Conversations",
                "generated_at": datetime.now().isoformat(),
                "total_conversations": len(prepared_conversations),
                "has_multiple_conversations": len(prepared_conversations) > 1,
                "single_conversation": False,
            },
            "tool_results": all_tool_results,  # Pass all tool results
        }

        return self.template.render(template_data)


    def _format_text_content(self, content: str) -> str:
        """Format text content as HTML."""
        if not content.strip():
            return ""

        # Escape HTML first
        content = html.escape(content)

        # Basic markdown conversion
        import re
        
        # Handle Claude's special XML-style tags (after HTML escape, they're now &lt; and &gt;)
        # Remove command-message tags but keep content in italic
        content = re.sub(r"&lt;command-message&gt;(.*?)&lt;/command-message&gt;", r"<em>\1</em>", content, flags=re.DOTALL)
        
        # Remove command-name tags but keep content in bold
        content = re.sub(r"&lt;command-name&gt;(.*?)&lt;/command-name&gt;", r"<strong>\1</strong>", content, flags=re.DOTALL)
        
        # Remove command-args tags but keep content in code
        content = re.sub(r"&lt;command-args&gt;(.*?)&lt;/command-args&gt;", r"<code>\1</code>", content, flags=re.DOTALL)
        
        # Remove local-command-stdout tags but keep content
        content = re.sub(r"&lt;local-command-stdout&gt;(.*?)&lt;/local-command-stdout&gt;", r"<pre>\1</pre>", content, flags=re.DOTALL)
        
        # Remove any other unmatched XML-style tags
        content = re.sub(r"&lt;/?(command-\w+|local-\w+)&gt;", "", content)

        # Bold **text**
        content = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", content)

        # Italic *text*
        content = re.sub(r"\*(.*?)\*", r"<em>\1</em>", content)

        # Code `code`
        content = re.sub(r"`(.*?)`", r"<code>\1</code>", content)

        # Headers
        content = re.sub(r"^### (.*?)$", r"<h3>\1</h3>", content, flags=re.MULTILINE)
        content = re.sub(r"^## (.*?)$", r"<h2>\1</h2>", content, flags=re.MULTILINE)
        content = re.sub(r"^# (.*?)$", r"<h1>\1</h1>", content, flags=re.MULTILINE)

        # Line breaks
        content = content.replace("\n", "<br>\n")

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
                if minutes == 1:
                    return "1 minute ago"
                elif minutes < 5:
                    return f"{minutes} minutes ago"
                elif minutes < 10:
                    return "5 minutes ago"
                elif minutes < 15:
                    return "10 minutes ago"
                elif minutes < 20:
                    return "15 minutes ago"
                elif minutes < 30:
                    return "20 minutes ago"
                elif minutes < 45:
                    return "30 minutes ago"
                else:
                    return "45 minutes ago"
            elif total_seconds < 86400:  # Less than 1 day
                hours = int(total_seconds / 3600)
                minutes = int((total_seconds % 3600) / 60)

                if hours == 1:
                    if minutes < 30:
                        return "1 hour ago"
                    else:
                        return "1.5 hours ago"
                elif hours < 6:
                    # Show half-hour precision for recent hours
                    if minutes >= 30:
                        return f"{hours}.5 hours ago"
                    else:
                        return f"{hours} hours ago"
                elif hours < 12:
                    return f"{hours} hours ago"
                elif hours < 18:
                    return "today"
                else:
                    return f"{hours} hours ago"
            elif total_seconds < 172800:  # Less than 2 days
                return "yesterday"
            elif total_seconds < 604800:  # Less than 1 week
                days = int(total_seconds / 86400)
                return f"{days} days ago"
            elif total_seconds < 2419200:  # Less than 4 weeks
                weeks = int(total_seconds / 604800)
                if weeks == 1:
                    return "1 week ago"
                else:
                    return f"{weeks} weeks ago"
            elif total_seconds < 5184000:  # Less than 60 days
                weeks = int(total_seconds / 604800)
                if weeks <= 4:
                    return "1 month ago"
                else:
                    return f"{weeks // 4} months ago"
            elif total_seconds < 31536000:  # Less than 1 year
                months = int(total_seconds / 2592000)
                if months == 1:
                    return "1 month ago"
                else:
                    return f"{months} months ago"
            else:
                # For older dates, show the actual date
                local_dt = dt.astimezone()
                # Show year only if it's different from current year
                current_year = datetime.now().year
                if local_dt.year == current_year:
                    return local_dt.strftime("%B %d at %I:%M %p")
                else:
                    return local_dt.strftime("%B %d, %Y")
        except (ValueError, TypeError):
            # Fallback for unparseable dates
            return timestamp_str

    def _format_tool_use(self, tool_use) -> str:
        """Jinja2 filter to format tool usage."""
        import html
        from pathlib import Path

        # Handle both dict and Pydantic objects
        if hasattr(tool_use, 'name'):
            # Pydantic object
            tool_name = tool_use.name if hasattr(tool_use, 'name') else "Unknown Tool"
            tool_input = tool_use.input if hasattr(tool_use, 'input') else {}
            tool_result = None  # Result comes separately in templates
        else:
            # Dictionary
            tool_name = tool_use.get("name", "Unknown Tool")
            tool_input = tool_use.get("input", {})
            tool_result = tool_use.get("result")

        # Simple HTML formatting for tools
        output = f'<div class="tool-use"><strong>🔧 {html.escape(tool_name)}</strong>'
        
        # Format specific tools specially
        if tool_name == "Bash" and isinstance(tool_input, dict):
            command = tool_input.get("command", "")
            # Generate unique ID for this bash command
            import hashlib
            tool_id = hashlib.md5(f"{tool_name}{command}{id(tool_use)}".encode()).hexdigest()[:8]
            output += f'''<div class="bash-collapsible">
                <button class="bash-toggle" onclick="toggleBash('{tool_id}')" aria-expanded="false">
                    <span class="toggle-icon">▶</span> Show command
                </button>
                <pre id="bash-{tool_id}" class="bash-command" style="display: none;">$ {html.escape(command)}</pre>
            </div>'''
        elif tool_name == "Read" and isinstance(tool_input, dict):
            file_path = tool_input.get("file_path", "")
            output += f'<div>📄 {html.escape(Path(file_path).name)}</div>'
        elif tool_name == "Edit" and isinstance(tool_input, dict):
            file_path = tool_input.get("file_path", "")
            output += f'<div>✏️ Editing {html.escape(Path(file_path).name)}</div>'
        elif tool_name == "Write" and isinstance(tool_input, dict):
            file_path = tool_input.get("file_path", "")
            output += f'<div>📝 Writing {html.escape(Path(file_path).name)}</div>'
        elif tool_name == "ExitPlanMode" and isinstance(tool_input, dict):
            plan = tool_input.get("plan", "")
            output += f'<div>📋 Planning Mode</div>'
            if plan:
                # Convert markdown to HTML-safe format with basic formatting
                plan_html = html.escape(plan)
                # Preserve line breaks and basic markdown formatting
                plan_html = plan_html.replace('\n', '<br>')
                plan_html = plan_html.replace('### ', '<strong>')
                plan_html = plan_html.replace('## ', '<strong>')
                plan_html = plan_html.replace('# ', '<strong>')
                # Close strong tags at line end
                lines = []
                for line in plan_html.split('<br>'):
                    if '<strong>' in line and '</strong>' not in line:
                        line += '</strong>'
                    lines.append(line)
                plan_html = '<br>'.join(lines)
                output += f'<div class="tool-plan">{plan_html}</div>'
        elif tool_name == "TodoWrite" and isinstance(tool_input, dict):
            todos = tool_input.get("todos", [])
            output += f'<div>📝 Managing {len(todos)} todos</div>'
            if todos:
                output += '<ul class="tool-todos">'
                for todo in todos[:5]:  # Show first 5 todos
                    status = todo.get("status", "pending")
                    content = todo.get("content", "")
                    status_icon = "✅" if status == "completed" else "🔄" if status == "in_progress" else "⏳"
                    output += f'<li>{status_icon} {html.escape(content)}</li>'
                if len(todos) > 5:
                    output += f'<li>... and {len(todos) - 5} more</li>'
                output += '</ul>'
        elif tool_name == "Grep" and isinstance(tool_input, dict):
            pattern = tool_input.get("pattern", "")
            path = tool_input.get("path", ".")
            output += f'<div>🔍 Searching for "{html.escape(pattern)}" in {html.escape(str(path))}</div>'
        elif tool_name == "Glob" and isinstance(tool_input, dict):
            pattern = tool_input.get("pattern", "")
            output += f'<div>📁 Finding files matching "{html.escape(pattern)}"</div>'
        elif tool_name == "MultiEdit" and isinstance(tool_input, dict):
            file_path = tool_input.get("file_path", "")
            edits = tool_input.get("edits", [])
            output += f'<div>✏️ Making {len(edits)} edits to {html.escape(Path(file_path).name)}</div>'
        elif tool_name == "Task" and isinstance(tool_input, dict):
            description = tool_input.get("description", "")
            subagent_type = tool_input.get("subagent_type", "")
            output += f'<div>🤖 Launching {html.escape(subagent_type)} agent: {html.escape(description)}</div>'
        elif tool_name == "WebFetch" and isinstance(tool_input, dict):
            url = tool_input.get("url", "")
            output += f'<div>🌐 Fetching {html.escape(url)}</div>'
        elif tool_name == "WebSearch" and isinstance(tool_input, dict):
            query = tool_input.get("query", "")
            output += f'<div>🔎 Searching web for "{html.escape(query)}"</div>'
        elif tool_name == "BashOutput" and isinstance(tool_input, dict):
            bash_id = tool_input.get("bash_id", "")
            output += f'<div>📊 Getting output from bash session {html.escape(bash_id)}</div>'
        elif tool_name == "KillBash" and isinstance(tool_input, dict):
            shell_id = tool_input.get("shell_id", "")
            output += f'<div>⛔ Killing bash session {html.escape(shell_id)}</div>'
        elif tool_name == "LS" and isinstance(tool_input, dict):
            path = tool_input.get("path", ".")
            output += f'<div>📂 Listing directory {html.escape(str(path))}</div>'
        elif tool_name.startswith("mcp__"):
            # MCP tools
            clean_name = tool_name.replace("mcp__", "").replace("_", " ").title()
            output += f'<div>🔌 MCP: {html.escape(clean_name)}</div>'
        else:
            # Fallback for other tools
            output += f'<div>{html.escape(tool_name)}</div>'
            
        if tool_result:
            output += f'<div class="tool-result">{html.escape(str(tool_result)[:500])}</div>'
        output += "</div>"
        return output

    def _format_time_only(self, timestamp_str: str) -> str:
        """Format timestamp to show only time (HH:MM format)."""
        if not timestamp_str:
            return ""
        
        try:
            from datetime import timezone
            dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            local_dt = dt.astimezone()
            return local_dt.strftime("%H:%M")
        except (ValueError, TypeError):
            return ""
    
    def _format_date_header(self, timestamp_str: str) -> str:
        """Format timestamp for date separator (e.g., 'Today', 'Yesterday', 'January 15, 2024')."""
        if not timestamp_str:
            return "Unknown Date"
        
        try:
            from datetime import timezone, timedelta
            dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            local_dt = dt.astimezone()
            now = datetime.now(timezone.utc).astimezone()
            
            # Calculate days difference
            date_diff = (now.date() - local_dt.date()).days
            
            if date_diff == 0:
                return "Today"
            elif date_diff == 1:
                return "Yesterday"
            elif date_diff < 7:
                return local_dt.strftime("%A")  # Day name (e.g., "Monday")
            else:
                # Show full date for older messages
                if local_dt.year == now.year:
                    return local_dt.strftime("%B %d")
                else:
                    return local_dt.strftime("%B %d, %Y")
        except (ValueError, TypeError):
            return "Unknown Date"
    
    def _get_message_date(self, timestamp_str: str) -> str:
        """Get the date part of a timestamp (YYYY-MM-DD format for comparison)."""
        if not timestamp_str:
            return ""
        
        try:
            dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            local_dt = dt.astimezone()
            return local_dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return ""

    def format_tool_use(self, tool_name: str, tool_use: dict[str, Any], tool_result: str | None = None) -> str:
        """Format a tool use with its result (required by BaseFormatter)."""
        return self._format_tool_use({"name": tool_name, "input": tool_use.get("input", {}), "result": tool_result})
