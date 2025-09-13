# MEMORY.md - Claude Notes Project Knowledge Base

## 1. Core Concepts & Definitions

### Project Overview
- **claude-notes**: A Python CLI tool that transforms Claude Code's transcript JSONL files into terminal-viewable output and HTML files
- Built with `uv` for fast Python package management
- Designed to be runnable with `uvx` for easy distribution and usage
- Uses Pydantic v2 (version 2.11.7) for data modeling

### Key Components
- **TranscriptEntry**: The main data model representing entries in Claude conversation JSONL files
- **Message**: Contains role and content (can be string or list of content items)
- **Content Types**: 
  - TextContent: Regular text messages
  - ToolUseContent: Represents tool calls made by Claude (accessible via `item.input` in templates)
  - ToolResultContent: Results from tool executions
- **Templates**: Jinja2-based HTML templates for rendering conversations
  - WhatsApp template: Mimics WhatsApp's chat interface with custom tool rendering
  - Default template: Standard HTML view

### Claude Tools in Conversations
The JSONL files contain various tool uses. Sample JSON files for each tool are available in `samples/` directory:

#### Core File Operations
- **Read** (`samples/tool_Read.json`): File reading - `input.file_path`, `input.offset`, `input.limit`
- **Write** (`samples/tool_Write.json`): File creation - `input.file_path`, `input.content`
- **Edit** (`samples/tool_Edit.json`): Single file edit - `input.file_path`, `input.old_string`, `input.new_string`, `input.replace_all`
- **MultiEdit** (`samples/tool_MultiEdit.json`): Multiple edits - `input.file_path`, `input.edits` (array of edit objects)

#### Search & Navigation
- **Grep** (`samples/tool_Grep.json`): Content search - `input.pattern`, `input.path`, `input.glob`, `input.output_mode`
- **Glob** (`samples/tool_Glob.json`): File pattern search - `input.pattern`, `input.path`
- **LS** (`samples/tool_LS.json`): Directory listing - `input.path`

#### Command Execution
- **Bash** (`samples/tool_Bash.json`): Command execution - `input.command`, `input.description`, `input.timeout`, `input.run_in_background`
- **BashOutput** (`samples/tool_BashOutput.json`): Get background bash output - `input.bash_id`, `input.filter`
- **KillBash** (`samples/tool_KillBash.json`): Kill background bash - `input.shell_id`

#### Task Management
- **TodoWrite** (`samples/tool_TodoWrite.json`): Task management - `input.todos` contains list of todo items with `content`, `status`, and `activeForm` fields
- **Task** (`samples/tool_Task.json`): Agent launches - `input.subagent_type`, `input.description`, `input.prompt`
- **ExitPlanMode** (`samples/tool_ExitPlanMode.json`): Planning completion - `input.plan`

#### Web Tools (not found in samples but documented)
- **WebSearch**: Web search - `input.query`, `input.allowed_domains`, `input.blocked_domains`
- **WebFetch**: URL fetching - `input.url`, `input.prompt`

#### MCP Tools
- **mcp__code-index__find_files** (`samples/tool_mcp__code-index__find_files.json`): MCP file finder
- **mcp__code-index__search_code_advanced** (`samples/tool_mcp__code-index__search_code_advanced.json`): MCP advanced code search

All 15 tool samples extracted from: `/Users/plosson/.claude/projects/-Users-plosson-devel-projects-hexrays-gitlab-ida-licensing/`

## 2. Context & Background

### Project Structure
- Located at: `/Users/plosson/devel/projects/hexrays/claude-notes`
- Main source code in `src/claude_notes/`
- Templates in `src/claude_notes/templates/`
- Claude conversation data stored in `~/.claude/projects/` directories
- CLAUDE.md file includes instruction to read MEMORY.md

### User Context
- User (plosson) is working on analyzing Claude conversations from the ida-licensing project
- Has multiple Claude projects with hundreds of conversations (2000+ tool calls in some projects)
- Needs to review tool usage patterns, particularly ExitPlanMode usage
- Wants WhatsApp-style interface for better conversation readability
- Requires detailed tool information to understand Claude's actions

## 3. Preferences & Patterns

### Development Preferences
- Uses `uv` for Python package management
- Prefers step-by-step debugging and verification
- Wants collapsible/expandable UI elements for tool details
- Likes WhatsApp-style chat interfaces with date separators and time-only displays
- Uses plan mode before implementing features

### UI/UX Requirements
- Tool calls should be collapsible by default
- Show brief summary when collapsed (tool name + key parameter)
- Expand to show full details on click
- Date separators between different days (like WhatsApp)
- Show only time (HH:MM) for messages within the same day
- Custom rendering for each tool type showing relevant details
- TodoWrite should show actual todo items with status indicators
- Edit tools should show code changes in diff-style format
- File paths should be styled distinctly for clarity

## 4. Decisions & Conclusions

### Technical Solutions Implemented

#### Tool Detection Issue
- **Problem**: Tool calls weren't showing in rendered HTML despite being in JSONL files
- **Root Cause**: Jinja2 variable scoping issue - variables set inside loops don't update outer scope
- **Solution**: Use `namespace()` object to maintain state across scopes, checking `item.__class__.__name__ == "ToolUseContent"`

#### Empty Message Filtering
- **Problem**: Empty user messages (tool results only) were showing as blank bubbles
- **Solution**: Enhanced base formatter to filter out user messages containing only tool_result items
- Also filters messages where content is string starting with "Tool Result:"

#### XML Tag Cleanup
- **Issue**: Claude's internal XML tags (like `<command-name>`, `<local-command-stdout>`) were appearing as raw text
- **Solution**: Added regex replacements in `_format_text_content` to clean these tags

### Custom Tool Rendering Implementation
Successfully implemented tool-specific rendering for all major tool types:
- **TodoWrite**: Displays full todo list with status emojis (✅ completed, ⏳ in_progress, ⏸️ pending)
- **Edit/MultiEdit**: Shows old → new changes with diff-style highlighting
- **Bash**: Terminal-style command display with dark background
- **Read/Write**: File paths in code blocks with operation details
- **Grep/Glob**: Search patterns and paths clearly displayed
- **Task**: Agent type and task description shown
- **Web tools**: Clickable URLs for WebFetch, formatted queries for WebSearch
- **ExitPlanMode**: Plan summary displayed when available
- **Default case**: Generic rendering for unknown tools showing all input parameters

### CSS Styling Added
- `.todo-list`, `.todo-item`: Styled todo lists with status indicators
- `.code-change`, `.code-old`, `.code-new`: Diff-style code change display
- `.tool-command`: Terminal-style command blocks
- `.tool-file-path`: Styled file paths
- `.tool-param`, `.tool-param-name`: Parameter display styling

## 5. Assumptions & Constraints

### Data Structure Constraints
- JSONL files use different structures for different conversation versions
- Some messages have `type` field, others have `role` field
- Tool content can be either dict or Pydantic object (ToolUseContent)
- Tool input is always accessible via `item.input` in templates
- Must handle both formats gracefully

### Rendering Constraints
- Pydantic objects ARE accessible in Jinja2 templates
- Can access attributes like `item.type` and `item.name` directly
- Class name checking via `__class__.__name__` is reliable
- Must use namespace for cross-scope variable updates in Jinja2
- Tool results are stored separately and accessed via `tool_results[msg.uuid]`

### Performance Considerations
- Some conversations have 700+ messages with 2000+ tool calls
- ida-licensing project shows 2280 tool bubbles after fixes
- Need efficient rendering and collapsible UI to handle large conversations
- Tool results can be very long - need truncation and scrollable areas
- Testing shows: 297 todo lists, 1627 todo items, 608 bash commands, 572 code changes rendered successfully

## Next Steps

### Completed Enhancements
1. ✅ Custom rendering for each tool type with rich displays
2. ✅ Default case for unknown/future tools
3. ✅ Tool-specific CSS styling
4. ✅ Testing with ida-licensing project (2280 tools rendered)

### Potential Future Enhancements
- Consider adding search/filter functionality for specific tools
- May need pagination for very large conversations
- Could add copy buttons for commands and code
- Might add syntax highlighting for code blocks
- Could implement tool result caching for performance