"""CLI commands for claude-notes."""
# ruff: noqa: UP017  # Use timezone.utc for Python <3.11 compatibility

from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from claude_notes.config import ConfigManager
from claude_notes.filter import FilterConfig
from claude_notes.parser import TranscriptParser

console = Console()


def get_claude_projects_dir() -> Path:
    """Get the Claude projects directory."""
    return Path.home() / ".claude" / "projects"


def _decode_segments(encoded: str, separator: str) -> str:
    """Decode dash-separated segments, where '--' represents a literal dash."""
    decoded_parts: list[str] = []
    i = 0
    while i < len(encoded):
        char = encoded[i]
        if char == "-":
            if i + 1 < len(encoded) and encoded[i + 1] == "-":
                decoded_parts.append("-")
                i += 2
            else:
                decoded_parts.append(separator)
                i += 1
        else:
            decoded_parts.append(char)
            i += 1
    return "".join(decoded_parts)


def _encode_segments(path: str) -> str:
    """Encode path segments by replacing slashes and underscores with dashes."""
    return path.replace("/", "-").replace("_", "-")


def decode_project_path(encoded_name: str) -> str:
    """Decode the project folder name to actual path."""
    # Windows path (e.g., "C--Users-projects-my--project")
    if len(encoded_name) >= 3 and encoded_name[1:3] == "--" and encoded_name[0].isalpha():
        drive = encoded_name[0]
        rest_encoded = encoded_name[3:]
        rest = _decode_segments(rest_encoded, "/")
        return f"{drive}:/{rest}" if rest else f"{drive}:/"

    # Unix/Linux path (e.g., "-home-user-my--project")
    if encoded_name.startswith("-"):
        encoded_body = encoded_name[1:]
        decoded_body = _decode_segments(encoded_body, "/")
        return "/" + decoded_body

    # Fallback: return as-is if it doesn't match expected encodings
    return encoded_name


def list_projects() -> list[tuple[str, Path, int]]:
    """List all Claude projects with their paths and transcript counts."""
    projects_dir = get_claude_projects_dir()

    if not projects_dir.exists():
        return []

    projects = []

    for project_folder in projects_dir.iterdir():
        if not project_folder.is_dir():
            continue

        # Check if it's a valid project folder
        # Unix/Linux: starts with "-" (e.g., "-home-user-project")
        # Windows: starts with drive letter (e.g., "c--Users-Jack-project" or "C--Users-Jack-project")
        name = project_folder.name
        is_valid = name.startswith("-") or (len(name) >= 3 and name[1:3] == "--" and name[0].isalpha())

        if is_valid:
            # Decode the project path
            actual_path = decode_project_path(name)

            # Count JSONL files (transcripts)
            jsonl_files = list(project_folder.glob("*.jsonl"))
            transcript_count = len(jsonl_files)

            projects.append((actual_path, project_folder, transcript_count))

    # Sort by path
    projects.sort(key=lambda x: x[0])

    return projects


@click.group()
@click.version_option()
@click.option(
    "-c",
    "--config-file",
    type=click.Path(exists=False, path_type=Path),
    help="Path to configuration file (default: ~/.claude/claude-notes.settings.json)",
)
@click.pass_context
def cli(ctx, config_file):
    """Transform Claude Code transcript JSONL files to readable formats."""
    # Store config file path in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["config_file"] = config_file


@cli.command(name="list-projects")
@click.pass_context
def list_projects_cmd(ctx):
    """List all Claude projects."""
    projects = list_projects()

    if not projects:
        console.print("[yellow]No Claude projects found in ~/.claude/projects/[/yellow]")
        return

    # Create a rich table
    table = Table(title="Claude Projects")
    table.add_column("Project Path", style="cyan")
    table.add_column("Transcripts", justify="right", style="green")
    table.add_column("Folder Name", style="dim")

    for project_path, project_folder, transcript_count in projects:
        table.add_row(project_path, str(transcript_count), project_folder.name)

    console.print(table)
    console.print(f"\n[dim]Total projects: {len(projects)}[/dim]")


def encode_project_path(path: str) -> str:
    """Encode a project path to Claude folder name format."""
    normalized = path.replace("\\", "/")

    # Windows path with drive letter (e.g., C:/Users/...)
    if len(normalized) >= 2 and normalized[1] == ":" and normalized[0].isalpha():
        drive = normalized[0]
        rest = normalized[2:]
        if rest.startswith("/"):
            rest = rest[1:]
        encoded_rest = _encode_segments(rest)
        return f"{drive}--{encoded_rest}"

    # Unix/Linux path (leading slash)
    normalized = normalized.lstrip("/")
    encoded_body = _encode_segments(normalized)
    return "-" + encoded_body


def find_project_folder(project_path: Path) -> Path | None:
    """Find the Claude project folder for a given project path."""
    projects_dir = get_claude_projects_dir()
    encoded_name = encode_project_path(str(project_path))
    project_folder = projects_dir / encoded_name

    # Try exact match first
    if project_folder.exists() and project_folder.is_dir():
        return project_folder

    # On Windows, try case-insensitive match (drive letter might be uppercase or lowercase)
    if not projects_dir.exists():
        return None

    encoded_lower = encoded_name.lower()
    for folder in projects_dir.iterdir():
        if folder.is_dir() and folder.name.lower() == encoded_lower:
            return folder

    return None


def parse_start_time(time_str: str) -> datetime | None:
    """Parse ISO format datetime string and convert to UTC."""
    if not time_str:
        return None

    try:
        # Parse the ISO format datetime
        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        # Convert to UTC if it has timezone info
        return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def order_messages(messages: list, message_order: str) -> list:
    """Order messages based on the specified order."""
    if message_order == "asc":
        return messages
    else:  # desc
        return list(reversed(messages))


def filter_tool_messages(messages: list, filter_config: FilterConfig) -> list:
    """Filter tool content from messages based on filter configuration.
    
    Args:
        messages: List of transcript entries
        filter_config: Filter configuration
        
    Returns:
        List of transcript entries with filtered tool content
    """
    if not filter_config:
        return messages
    
    filtered_messages = []
    for msg in messages:
        # For assistant messages, filter tool uses
        if hasattr(msg, 'type') and msg.type == "assistant" and hasattr(msg, 'message') and msg.message:
            message_data = msg.message
            if hasattr(message_data, 'content') and isinstance(message_data.content, list):
                # Filter out hidden tools from content
                filtered_content = []
                for item in message_data.content:
                    # Check if it's a tool use
                    if hasattr(item, '__class__') and item.__class__.__name__ == "ToolUseContent":
                        if filter_config.should_show_tool(item.name):
                            filtered_content.append(item)
                    else:
                        # Keep non-tool content (text, etc.)
                        filtered_content.append(item)
                
                # Update the message content
                if filtered_content or not all(
                    hasattr(item, '__class__') and item.__class__.__name__ == "ToolUseContent" 
                    for item in message_data.content
                ):
                    # Keep message if it has non-tool content or visible tools
                    message_data.content = filtered_content
                    filtered_messages.append(msg)
            else:
                filtered_messages.append(msg)
        else:
            filtered_messages.append(msg)
    
    return filtered_messages


@cli.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path), default=".")
@click.option("--raw", is_flag=True, help="Show raw JSON data instead of formatted view")
@click.option("--no-pager", is_flag=True, help="Disable pager and show all content at once")
@click.option(
    "--filter-tools", 
    type=str, 
    help="Comma-separated list of tool names to hide. Available tools: "
         "Read, Write, Edit, MultiEdit, Bash, BashOutput, KillBash, "
         "Grep, Glob, LS, TodoWrite, Task, ExitPlanMode, WebSearch, WebFetch"
)
@click.option(
    "--only-tools", 
    type=str, 
    help="Show only these tools, hide all others. Available tools: "
         "Read, Write, Edit, MultiEdit, Bash, BashOutput, KillBash, "
         "Grep, Glob, LS, TodoWrite, Task, ExitPlanMode, WebSearch, WebFetch"
)
@click.option(
    "--filter-categories", 
    type=str, 
    help="Hide tool categories. Available categories: "
         "file (Read,Write,Edit,MultiEdit), "
         "search (Grep,Glob,LS), "
         "command (Bash,BashOutput,KillBash), "
         "task (TodoWrite,Task,ExitPlanMode), "
         "web (WebSearch,WebFetch), "
         "mcp (all mcp__ prefixed tools)"
)
@click.option(
    "--filter-pattern", 
    type=str, 
    help="Regex pattern for tools to hide (e.g., 'mcp__.*' to hide all MCP tools)"
)
@click.option(
    "--format", type=click.Choice(["terminal", "animated", "template"]), default="terminal", help="Output format"
)
@click.option("--output", type=click.Path(), help="Output file (GIF/MP4/cast format for animated, HTML for template)")
@click.option(
    "--session-order",
    type=click.Choice(["asc", "desc"]),
    default="asc",
    help="Order sessions by timestamp (asc=oldest first, desc=newest first)",
)
@click.option(
    "--message-order",
    type=click.Choice(["asc", "desc"]),
    default=None,
    help="Order messages within sessions (asc=oldest first, desc=newest first). Defaults to asc for HTML, desc for terminal.",
)
@click.option("--style", type=click.Path(exists=True), help="Custom CSS file to include with HTML format")
@click.option("--template", type=str, help="Template file or name to use with template format")
@click.option(
    "--typing-speed", type=float, default=0.05, help="Typing speed in seconds per character (animated format)"
)
@click.option(
    "--pause-duration", type=float, default=2.0, help="Pause duration between messages in seconds (animated format)"
)
@click.option("--cols", type=int, default=120, help="Terminal columns (animated format)")
@click.option("--rows", type=int, default=30, help="Terminal rows (animated format)")
@click.option("--max-duration", type=float, help="Maximum animation duration in seconds (animated format)")
@click.option(
    "--emoji-fallbacks",
    is_flag=True,
    help="Replace emoji with text fallbacks for better GIF compatibility (animated format)",
)
@click.option("--save-config", is_flag=True, help="Save current command line options to configuration file")
@click.pass_context
def show(
    ctx,
    path: Path,
    raw: bool,
    no_pager: bool,
    filter_tools: str | None,
    only_tools: str | None,
    filter_categories: str | None,
    filter_pattern: str | None,
    format: str,
    output: str | None,
    session_order: str,
    message_order: str,
    style: str | None,
    template: str | None,
    typing_speed: float,
    pause_duration: float,
    cols: int,
    rows: int,
    max_duration: float | None,
    emoji_fallbacks: bool,
    save_config: bool,
):
    """Show all conversations for a Claude project.

    If PATH is not specified, uses the current directory.
    """
    # Load configuration from file
    config_path = ctx.obj.get("config_file")
    file_config = ConfigManager.load_config(config_path)

    # Get all CLI arguments
    cli_args = ctx.params.copy()

    # Track which arguments were explicitly provided on command line
    # In Click, we can check parameter sources to see which were explicitly set
    explicit_args = set()
    for param_name in ctx.params:
        param_source = ctx.get_parameter_source(param_name)
        # COMMANDLINE means it was explicitly provided by the user
        if param_source == click.core.ParameterSource.COMMANDLINE:
            explicit_args.add(param_name)

    # If save_config flag is set, save current options to config file
    if save_config:
        # Only save arguments that were explicitly provided
        save_args = {}
        for arg_name in explicit_args:
            if arg_name not in ["path", "save_config"]:  # Exclude path and save_config itself
                save_args[arg_name] = cli_args[arg_name]

        ConfigManager.save_config(save_args, config_path)
        console.print(f"[green]Configuration saved to: {config_path or ConfigManager.DEFAULT_CONFIG_PATH}[/green]")

    # Merge configs (only explicit CLI args override file config)
    merged_config = ConfigManager.merge_configs(file_config, cli_args, explicit_args)

    # Apply merged configuration
    path = cli_args.get("path", path)  # Path should always come from CLI
    raw = merged_config.get("raw", raw)
    no_pager = merged_config.get("no_pager", no_pager)
    format = merged_config.get("format", format)
    output = merged_config.get("output", output)
    session_order = merged_config.get("session_order", session_order)
    message_order = merged_config.get("message_order", message_order)
    style = merged_config.get("style", style)
    template = merged_config.get("template", template)
    typing_speed = merged_config.get("typing_speed", typing_speed)
    pause_duration = merged_config.get("pause_duration", pause_duration)
    cols = merged_config.get("cols", cols)
    rows = merged_config.get("rows", rows)
    max_duration = merged_config.get("max_duration", max_duration)
    emoji_fallbacks = merged_config.get("emoji_fallbacks", emoji_fallbacks)

    # Set default message order based on format if not explicitly provided
    if message_order is None:
        message_order = "asc" if format == "template" else "desc"

    # Convert to absolute path
    abs_path = path.resolve()

    # Check if the path is a direct .jsonl file
    if abs_path.is_file() and abs_path.suffix == ".jsonl":
        # Use the file directly
        jsonl_files = [abs_path]
    else:
        # Find the project folder
        project_folder = find_project_folder(abs_path)

        if not project_folder:
            console.print(f"[red]Error:[/red] No Claude project found for path: {abs_path}")
            console.print("\n[dim]Hint: Use 'claude-notes list-projects' to see all available projects[/dim]")
            return

        # List all JSONL files
        jsonl_files = sorted(project_folder.glob("*.jsonl"))

    if not jsonl_files:
        console.print(f"[yellow]No transcript files found in project: {abs_path}[/yellow]")
        return

    # No header output - just start with the conversation

    # Load all conversations
    conversations = []
    for jsonl_file in jsonl_files:
        try:
            parser = TranscriptParser(jsonl_file)
            info = parser.get_conversation_info()
            messages = parser.get_messages()

            # Get the start timestamp for sorting (convert to UTC)
            start_time = parse_start_time(info.get("start_time", ""))

            # Get file modification time as fallback (in UTC)
            file_mtime = datetime.fromtimestamp(jsonl_file.stat().st_mtime, tz=timezone.utc)

            conversations.append(
                {
                    "file": jsonl_file,
                    "info": info,
                    "messages": messages,
                    "start_time": start_time,
                    "file_mtime": file_mtime,
                }
            )
        except Exception as e:
            console.print(f"[red]Error parsing {jsonl_file.name}: {e}[/red]")

    # Sort conversations by start time, with file modification time as fallback
    # Use timezone-aware datetime.min to avoid comparison issues
    conversations.sort(
        key=lambda x: x["start_time"] or x["file_mtime"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=(session_order == "desc"),
    )
    
    # Create filter config from CLI arguments
    filter_config = FilterConfig(
        filter_tools=filter_tools,
        only_tools=only_tools,
        filter_categories=filter_categories,
        filter_pattern=filter_pattern
    )
    
    # Apply tool filtering to all conversations
    for conv in conversations:
        conv["messages"] = filter_tool_messages(conv["messages"], filter_config)

    # Assign default titles
    for i, conv in enumerate(conversations, 1):
        conv["info"]["title"] = f"Conversation {i}"

    if raw:
        # Display raw JSON data
        import json

        for conv in conversations:
            console.print(f"\n[bold cyan]Conversation: {conv['info'].get('conversation_id', 'Unknown')}[/bold cyan]")
            console.print(json.dumps(conv["messages"], indent=2))
    elif format == "animated":
        # Generate animated GIF
        from claude_notes.formatters.factory import FormatterFactory

        # Create animated formatter with options
        formatter_kwargs = {
            "typing_speed": typing_speed,
            "pause_duration": pause_duration,
            "cols": cols,
            "rows": rows,
            "max_duration": max_duration,
            "use_emoji_fallbacks": emoji_fallbacks,
        }

        try:
            formatter = FormatterFactory.create_formatter("animated", **formatter_kwargs)
        except (ImportError, RuntimeError) as e:
            console.print(f"[red]Error:[/red] {e}")
            console.print("[dim]Hint: Install animation dependencies with: uv add --optional-deps animation[/dim]")
            return

        # Collect all conversations into a single asciicast
        all_messages = []
        for conv in conversations:
            # Order the messages based on user preference
            ordered_messages = order_messages(conv["messages"], message_order)

            all_messages.extend(ordered_messages)

            # Add separator between conversations if multiple
            if len(conversations) > 1:
                separator_msg = {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": f"\n--- {conv['info'].get('title', f'Conversation {conversations.index(conv) + 1}')} ---\n",
                    },
                }
                all_messages.append(separator_msg)

        # Generate asciicast
        try:
            cast_file = formatter.format_conversation(all_messages, conversation_info={})

            # Handle output options
            if output:
                output_path = Path(output)
                base_name = output_path.stem
                output_dir = output_path.parent

                # Always save the cast file alongside the output
                cast_output = output_dir / f"{base_name}.cast"
                import shutil

                shutil.copy2(cast_file, cast_output)
                console.print(f"[cyan]Asciicast file saved: {cast_output}[/cyan]")

                # Generate output based on file extension
                if output.endswith(".gif") or not output_path.suffix:
                    gif_output = str(output_path.with_suffix(".gif"))
                    formatter.generate_gif(cast_file, gif_output)
                    console.print(f"[green]Animated GIF generated: {gif_output}[/green]")
                elif output.endswith(".mp4"):
                    mp4_output = str(output_path.with_suffix(".mp4"))
                    formatter.generate_mp4(cast_file, mp4_output)
                    console.print(f"[green]MP4 video generated: {mp4_output}[/green]")
                elif output.endswith(".cast"):
                    # User specifically requested just the cast file
                    console.print(f"[green]Asciicast file saved: {cast_output}[/green]")
                else:
                    # Unknown extension, assume they want GIF
                    gif_output = str(output_path.with_suffix(".gif"))
                    formatter.generate_gif(cast_file, gif_output)
                    console.print(f"[green]Animated GIF generated: {gif_output}[/green]")
            else:
                console.print(f"[yellow]Asciicast file generated: {cast_file}[/yellow]")
                console.print("[dim]Use --output filename.cast/.gif/.mp4 to save in desired format[/dim]")

        except Exception as e:
            console.print(f"[red]Error generating animation: {e}[/red]")

    elif format == "template":
        # Generate template-based HTML output
        from claude_notes.formatters.template import TemplateFormatter

        try:
            formatter = TemplateFormatter(template)
        except ValueError as e:
            console.print(f"[red]Template Error:[/red] {e}")
            return

        # Prepare conversations for template rendering
        all_conversations = []
        for conv in conversations:
            # Order the messages based on user preference
            ordered_messages = order_messages(conv["messages"], message_order)

            all_conversations.append({"info": conv["info"], "messages": ordered_messages})

        # Generate HTML using template
        html_output = formatter.format_conversations(all_conversations)

        if output:
            # Write to file
            output_path = Path(output)
            output_path.write_text(html_output, encoding="utf-8")
            console.print(f"[green]Template HTML output written to: {output_path}[/green]")
        else:
            # Print to stdout
            print(html_output)

    else:
        # Display formatted conversations in terminal
        from claude_notes.formatters.terminal import TerminalFormatter

        formatter = TerminalFormatter(console)

        if no_pager:
            # Display all content at once without pager
            for _i, conv in enumerate(conversations):
                # Order the messages based on user preference
                ordered_messages = order_messages(conv["messages"], message_order)

                formatter.display_conversation(ordered_messages, conv["info"])
        else:
            # Use pager for progressive display
            from claude_notes.pager import Pager

            pager = Pager(console)

            # Collect all formatted content first
            for _i, conv in enumerate(conversations):
                # Order the messages based on user preference
                ordered_messages = order_messages(conv["messages"], message_order)

                pager.add_conversation(ordered_messages, conv["info"], formatter)

            # Start the pager interface
            pager.display()
