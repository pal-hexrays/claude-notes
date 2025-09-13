"""Tool filtering configuration and logic."""

import re
from typing import Optional, Set


class FilterConfig:
    """Configuration for filtering tool displays."""
    
    # Tool category mappings
    TOOL_CATEGORIES = {
        'file': {'Read', 'Write', 'Edit', 'MultiEdit'},
        'search': {'Grep', 'Glob', 'LS'},
        'command': {'Bash', 'BashOutput', 'KillBash'},
        'task': {'TodoWrite', 'Task', 'ExitPlanMode'},
        'web': {'WebSearch', 'WebFetch'},
        'mcp': set()  # Handled dynamically by prefix
    }
    
    def __init__(
        self,
        filter_tools: Optional[str] = None,
        only_tools: Optional[str] = None,
        filter_categories: Optional[str] = None,
        filter_pattern: Optional[str] = None
    ):
        """Initialize filter configuration.
        
        Args:
            filter_tools: Comma-separated list of tool names to hide
            only_tools: Comma-separated list of tools to show (hide all others)
            filter_categories: Comma-separated list of categories to hide
            filter_pattern: Regex pattern for tools to hide
        """
        self.hidden_tools: Set[str] = set()
        self.allowed_tools: Optional[Set[str]] = None
        self.filter_pattern: Optional[re.Pattern] = None
        
        # Parse filter_tools
        if filter_tools:
            self.hidden_tools.update(
                tool.strip() for tool in filter_tools.split(',') if tool.strip()
            )
        
        # Parse only_tools (takes precedence)
        if only_tools:
            self.allowed_tools = {
                tool.strip() for tool in only_tools.split(',') if tool.strip()
            }
        
        # Parse filter_categories
        if filter_categories:
            categories = [cat.strip().lower() for cat in filter_categories.split(',')]
            for category in categories:
                if category in self.TOOL_CATEGORIES:
                    self.hidden_tools.update(self.TOOL_CATEGORIES[category])
        
        # Compile filter pattern
        if filter_pattern:
            try:
                self.filter_pattern = re.compile(filter_pattern)
            except re.error:
                # Invalid regex - ignore it
                pass
    
    def should_show_tool(self, tool_name: str) -> bool:
        """Check if a tool should be displayed.
        
        Args:
            tool_name: Name of the tool to check
            
        Returns:
            True if the tool should be shown, False if it should be hidden
        """
        # If only_tools is set, only show tools in that list
        if self.allowed_tools is not None:
            return tool_name in self.allowed_tools
        
        # Check if tool is explicitly hidden
        if tool_name in self.hidden_tools:
            return False
        
        # Check MCP tools by prefix
        if tool_name.startswith('mcp__') and 'mcp' in self.hidden_tools:
            return False
        
        # Check regex pattern
        if self.filter_pattern and self.filter_pattern.match(tool_name):
            return False
        
        return True
    
    def to_dict(self) -> dict:
        """Convert filter config to dictionary for serialization."""
        result = {}
        
        if self.hidden_tools:
            # Convert back to comma-separated string
            result['filter_tools'] = ','.join(sorted(self.hidden_tools))
        
        if self.allowed_tools is not None:
            result['only_tools'] = ','.join(sorted(self.allowed_tools))
        
        if self.filter_pattern:
            result['filter_pattern'] = self.filter_pattern.pattern
        
        return result
    
    @classmethod
    def from_config(cls, config: dict) -> 'FilterConfig':
        """Create FilterConfig from configuration dictionary.
        
        Args:
            config: Configuration dictionary (from CLI args or config file)
            
        Returns:
            FilterConfig instance
        """
        return cls(
            filter_tools=config.get('filter_tools'),
            only_tools=config.get('only_tools'),
            filter_categories=config.get('filter_categories'),
            filter_pattern=config.get('filter_pattern')
        )