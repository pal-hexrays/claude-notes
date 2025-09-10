# Claude Notes Templates

This directory contains Jinja2 templates for HTML output formatting.

## Built-in Templates

### `default.html`
The default template that replicates the existing HTML formatter functionality with:
- Full styling and navigation
- Tool use formatting  
- Multi-conversation support
- Message anchors and timestamps

### `minimal.html`
A simplified template with minimal styling, ideal for:
- Clean, readable output
- Embedding in other documents
- Quick conversation reviews

## Using Templates

### Command Line Usage

```bash
# Use default template
uv run claude-notes show . --format template

# Use built-in template by name
uv run claude-notes show . --format template --template minimal

# Use custom template file
uv run claude-notes show . --format template --template /path/to/my-template.html

# Use template from local templates directory
uv run claude-notes show . --format template --template my-custom-template.html
```

## Creating Custom Templates

### Template Data Structure

Templates receive the following data structure:

```python
{
    "conversations": [  # List of conversations (multiple) OR
    "conversation": {   # Single conversation object
        "info": {
            "conversation_id": "abc123",
            "start_time": "2024-01-01T10:00:00Z"
        },
        "messages": [
            {
                "role": "user",  # or "assistant"
                "role_icon": "👤",  # or "🤖"
                "role_name": "User",  # or "Assistant"
                "timestamp": "2024-01-01T10:00:00Z",
                "message_number": 1,
                "content_parts": [
                    {
                        "type": "text",
                        "text": "Raw text content",
                        "html": "HTML formatted content"
                    }
                ],
                "tool_uses": [
                    {
                        "name": "Bash",
                        "input": {"command": "ls -la"},
                        "result": "file listing..."
                    }
                ],
                "has_content": True,
                "has_tools": False
            }
        ]
    },
    "metadata": {
        "title": "Claude Conversations",
        "generated_at": "2024-01-01T12:00:00Z",
        "total_conversations": 1,
        "has_multiple_conversations": False,
        "single_conversation": True
    }
}
```

### Available Filters

- `humanize_date` - Convert ISO timestamps to human-readable format
- `format_tool_use` - Format tool usage with appropriate styling

### Example Custom Template

```html
<!DOCTYPE html>
<html>
<head>
    <title>{{ metadata.title }}</title>
    <style>
        /* Your custom styles */
    </style>
</head>
<body>
    {% if metadata.single_conversation %}
        <!-- Single conversation layout -->
        {% for message in conversation.messages %}
        <div class="message-{{ message.role }}">
            <h3>{{ message.role_name }}</h3>
            {% for content in message.content_parts %}
                {{ content.html | safe }}
            {% endfor %}
        </div>
        {% endfor %}
    {% else %}
        <!-- Multiple conversations layout -->
        {% for conv in conversations %}
            <!-- Conversation content -->
        {% endfor %}
    {% endif %}
</body>
</html>
```

### Template Search Order

1. Absolute path to template file (if provided)
2. `./templates/` directory in current working directory
3. Built-in templates directory
4. Falls back to `default.html`