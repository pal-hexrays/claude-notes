"""AI-powered conversation title generation using Anthropic API."""

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import anthropic
from rich.console import Console

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# Try to import OpenAI
try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

console = Console()


class TitleCache:
    """Manages caching of generated conversation titles."""

    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize the title cache.
        
        Args:
            cache_dir: Directory to store cache file. Defaults to ~/.claude/
        """
        if cache_dir is None:
            cache_dir = Path.home() / ".claude"

        self.cache_dir = cache_dir
        self.cache_file = cache_dir / "title_cache.json"
        self.cache_dir.mkdir(exist_ok=True)
        self._cache = self._load_cache()

    def _load_cache(self) -> Dict[str, Dict[str, Any]]:
        """Load cache from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                console.print("[yellow]Warning: Could not load title cache, starting fresh[/yellow]")
                return {}
        return {}

    def _save_cache(self):
        """Save cache to disk."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, indent=2, ensure_ascii=False)
        except IOError:
            console.print("[yellow]Warning: Could not save title cache[/yellow]")

    def get_cache_key(self, messages: List[Dict[str, Any]]) -> str:
        """Generate cache key from conversation messages."""
        # Extract only user and assistant messages for consistent hashing
        relevant_messages = []
        for msg in messages:
            # Handle nested message structure
            actual_msg = msg.get("message", msg)
            role = actual_msg.get("role")
            
            if role in ["user", "assistant"]:
                # Handle both content formats
                if "content" in actual_msg:
                    # Simple string content (might be string or list)
                    content = actual_msg.get("content", "")
                    if isinstance(content, list):
                        text_content = " ".join(str(c) for c in content)
                    else:
                        text_content = str(content)
                else:
                    # Content parts format
                    content_parts = actual_msg.get("content_parts", [])
                    text_content = ""
                    for part in content_parts:
                        if part.get("type") == "text":
                            text_content += part.get("text", "")
                
                if text_content:
                    relevant_messages.append(f"{role}: {text_content}")

        # Create hash from message content
        content = "\n".join(relevant_messages)
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached title data."""
        return self._cache.get(cache_key)

    def set(self, cache_key: str, title: str, api_cost: float = 0.0):
        """Cache a generated title."""
        from datetime import datetime
        self._cache[cache_key] = {
            "title": title,
            "generated_date": datetime.now().isoformat(),
            "api_cost": api_cost
        }
        self._save_cache()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        if not self._cache:
            return {"total_titles": 0, "total_cost": 0.0}

        total_cost = sum(entry.get("api_cost", 0.0) for entry in self._cache.values())
        return {
            "total_titles": len(self._cache),
            "total_cost": total_cost,
            "cache_file": str(self.cache_file)
        }


class LLMTitleGenerator:
    """Generates conversation titles using Anthropic's Claude API or OpenAI's GPT API."""

    def __init__(self, api_key: Optional[str] = None, enable_cache: bool = True, provider: str = "auto"):
        """Initialize the title generator.
        
        Args:
            api_key: API key. If None, will try environment variables.
            enable_cache: Whether to use caching for generated titles.
            provider: LLM provider - 'anthropic', 'openai', or 'auto' (tries both).
        """
        self.provider = provider
        self.client = None
        self.cache = TitleCache() if enable_cache else None

        # Try to initialize based on provider preference
        if provider == "openai" or (provider == "auto" and OPENAI_AVAILABLE):
            self._init_openai(api_key)

        if not self.client and (provider == "anthropic" or provider == "auto"):
            self._init_anthropic(api_key)

        if not self.client:
            console.print("[yellow]No LLM API configured. Title generation will use fallback format.[/yellow]")
            console.print(
                "[dim]Set ANTHROPIC_API_KEY or OPENAI_API_KEY environment variable to enable AI titles.[/dim]")

    def _init_openai(self, api_key: Optional[str] = None):
        """Initialize OpenAI client."""
        if not OPENAI_AVAILABLE:
            return

        openai_key = api_key or os.getenv("OPENAI_API_KEY")
        if openai_key:
            try:
                self.client = OpenAI(api_key=openai_key)
                self.provider = "openai"
                console.print("[green]Using OpenAI for title generation[/green]")
            except Exception as e:
                console.print(f"[yellow]Could not initialize OpenAI client: {e}[/yellow]")
                self.client = None

    def _init_anthropic(self, api_key: Optional[str] = None):
        """Initialize Anthropic client."""
        anthropic_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            try:
                self.client = anthropic.Anthropic(api_key=anthropic_key)
                self.provider = "anthropic"
                console.print("[green]Using Anthropic for title generation[/green]")
            except Exception as e:
                console.print(f"[yellow]Could not initialize Anthropic client: {e}[/yellow]")
                self.client = None

    def extract_context(self, messages: List[Dict[str, Any]], max_chars: int = 2000) -> str:
        """Extract relevant context from conversation messages for title generation.
        
        Args:
            messages: List of conversation messages
            max_chars: Maximum characters to include in context
            
        Returns:
            Formatted conversation context for API
        """
        context_lines = []
        total_chars = 0

        # Only include user and assistant messages, skip tool calls
        for msg in messages:
            # Handle nested message structure
            actual_msg = msg.get("message", msg)
            role = actual_msg.get("role")
            
            if role not in ["user", "assistant"]:
                continue
            
            # Handle both content formats
            if "content" in actual_msg:
                # Simple string content (might be string or list)
                content = actual_msg.get("content", "")
                if isinstance(content, list):
                    # Join list elements if it's a list
                    text_content = " ".join(str(c) for c in content)
                else:
                    text_content = str(content)
            else:
                # Content parts format
                content_parts = actual_msg.get("content_parts", [])
                text_content = ""
                for part in content_parts:
                    if part.get("type") == "text":
                        text_content += part.get("text", "")

            if text_content.strip():
                role_label = "User" if role == "user" else "Claude"
                line = f"{role_label}: {text_content.strip()}"

                if total_chars + len(line) > max_chars:
                    break

                context_lines.append(line)
                total_chars += len(line)

                # Stop after reasonable number of exchanges
                if len(context_lines) >= 20:  # 10 exchanges
                    break

        return "\n\n".join(context_lines)

    def generate_title(self, messages: List[Dict[str, Any]], excluded_titles: List[str] = None) -> Tuple[str, float]:
        """Generate a Seinfeld-style title for a conversation.
        
        Args:
            messages: List of conversation messages
            excluded_titles: List of titles to avoid (for uniqueness)
            
        Returns:
            Tuple of (generated_title, api_cost)
        """
        # Check cache first
        if self.cache:
            cache_key = self.cache.get_cache_key(messages)
            cached_data = self.cache.get(cache_key)
            if cached_data:
                return cached_data["title"], 0.0  # No additional cost for cached titles

        # If no API client, return generic title
        if not self.client:
            return "The Conversation", 0.0

        # Extract context for API
        context = self.extract_context(messages)
        if not context:
            return "The Conversation", 0.0

        # Generate title using Anthropic API
        try:
            # Build prompt with excluded titles if provided
            excluded_section = ""
            if excluded_titles:
                excluded_list = "\n".join(f"- {title}" for title in excluded_titles)
                excluded_section = f"""
ABSOLUTELY FORBIDDEN TITLES - DO NOT USE THESE UNDER ANY CIRCUMSTANCES:
{excluded_list}

You MUST be creative and find a DIFFERENT, UNIQUE aspect of the conversation to reference.
If the obvious title is taken, look for secondary themes, moods, specific details, or metaphors.
"""
            
            prompt = f"""Based on the following conversation between a user and Claude, generate a Seinfeld episode title using "The [Noun]" format.

Seinfeld episodes typically:
- Use "The [Noun]" format (e.g., "The Contest", "The Soup Nazi", "The Parking Garage")
- Reference a central object, concept, mood, or theme from the conversation
- Are memorable and slightly humorous
- Capture the main topic/theme in 2-4 words
- Focus on the key subject matter discussed

Examples of good Seinfeld titles:
- "The Template" (for a conversation about templates)
- "The Stylesheet" (for CSS/styling discussion)
- "The Bug" (for debugging conversation)
- "The Formatter" (for code formatting)
- "The Interface" (for UI/UX discussion)
{excluded_section}
Conversation:
{context}

Generate only "The [Noun]" title, no explanation or episode number:"""

            if self.provider == "openai":
                # Use OpenAI API
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",  # Cheapest GPT-4 model
                    max_tokens=50,  # Enough for "The [Compound Noun]" formats
                    temperature=0.8,  # Slightly higher for more variety
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                title = response.choices[0].message.content.strip()
            else:
                # Use Anthropic API
                response = self.client.messages.create(
                    model="claude-3-5-haiku-20241022",  # Cheapest model
                    max_tokens=50,  # Enough for "The [Compound Noun]" formats
                    temperature=0.8,  # Slightly higher for more variety
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                )
                title = response.content[0].text.strip()

            # Ensure title starts with "The"
            if not title.startswith("The "):
                title = f"The {title}" if title else "The Conversation"

            # Estimate cost based on provider
            if self.provider == "openai":
                # GPT-4o-mini: ~$0.15 per 1M input tokens, $0.60 per 1M output
                estimated_cost = (len(prompt) / 4 / 1_000_000 * 0.15) + (len(title) / 4 / 1_000_000 * 0.60)
            else:
                # Claude 3.5 Haiku: ~$0.25 per 1M input tokens
                estimated_cost = (len(prompt) + len(title)) / 4 / 1_000_000 * 0.25

            # Cache the result
            if self.cache:
                self.cache.set(cache_key, title, estimated_cost)

            return title, estimated_cost

        except Exception as e:
            console.print(f"[red]Error generating title: {e}[/red]")
            return "The Conversation", 0.0

    def format_episode_title(self, episode_number: int, generated_title: str) -> str:
        """Format title in Seinfeld episode format.
        
        Args:
            episode_number: Episode number (1-based)
            generated_title: Generated title from API
            
        Returns:
            Formatted title like "S01E05: The Template"
        """
        return f"S01E{episode_number:02d}: {generated_title}"

    def generate_titles_for_conversations(self, conversations: List[Dict[str, Any]],
                                          show_progress: bool = True) -> Dict[int, str]:
        """Generate titles for multiple conversations.
        
        Args:
            conversations: List of conversation data
            show_progress: Whether to show progress information
            
        Returns:
            Dictionary mapping conversation index to formatted title
        """
        titles = {}
        total_cost = 0.0

        if show_progress and conversations:
            console.print(f"[cyan]Generating Seinfeld episode titles for {len(conversations)} conversations...[/cyan]")

        for i, conversation in enumerate(conversations, 1):
            if show_progress:
                console.print(f"[dim]Processing S01E{i:02d}...[/dim]", end=" ")

            messages = conversation.get("messages", [])
            generated_title, cost = self.generate_title(messages)
            total_cost += cost

            formatted_title = self.format_episode_title(i, generated_title)
            titles[i] = formatted_title

            if show_progress:
                console.print(f"[green]{formatted_title}[/green]")

        if show_progress and total_cost > 0:
            console.print(f"[dim]Total estimated cost: ${total_cost:.4f}[/dim]")

        return titles

    def get_cache_stats(self) -> Optional[Dict[str, Any]]:
        """Get cache statistics."""
        return self.cache.get_stats() if self.cache else None
    
    def generate_unique_titles(self, conversations_messages: List[List[Dict[str, Any]]], 
                              max_retries: int = 3) -> List[Tuple[str, float]]:
        """Generate unique titles for multiple conversations.
        
        Args:
            conversations_messages: List of message lists for each conversation
            max_retries: Maximum attempts to regenerate duplicate titles
            
        Returns:
            List of (title, cost) tuples, one for each conversation
        """
        results = []
        all_titles = set()
        total_cost = 0.0
        
        # First pass: generate initial titles
        for messages in conversations_messages:
            title, cost = self.generate_title(messages)
            results.append((title, cost))
            all_titles.add(title)
            total_cost += cost
        
        # Check for duplicates and regenerate if needed
        for retry in range(max_retries):
            # Find duplicates
            title_counts = {}
            for title, _ in results:
                title_counts[title] = title_counts.get(title, 0) + 1
            
            duplicates = {title for title, count in title_counts.items() if count > 1}
            if not duplicates:
                break  # No duplicates, we're done
            
            console.print(f"[yellow]Found {len(duplicates)} duplicate titles, regenerating (attempt {retry + 1}/{max_retries})...[/yellow]")
            
            # Regenerate duplicates
            for i, (title, old_cost) in enumerate(results):
                if title in duplicates:
                    # Get all current titles to exclude
                    excluded = [t for t, _ in results]
                    
                    # Try to generate a new unique title
                    new_title, new_cost = self.generate_title(conversations_messages[i], excluded)
                    
                    # Update if we got a different title
                    if new_title not in all_titles:
                        results[i] = (new_title, old_cost + new_cost)
                        all_titles.discard(title)
                        all_titles.add(new_title)
                        total_cost += new_cost
        
        # Final check for any remaining duplicates
        final_counts = {}
        for title, _ in results:
            final_counts[title] = final_counts.get(title, 0) + 1
        
        remaining_dups = sum(1 for count in final_counts.values() if count > 1)
        if remaining_dups > 0:
            console.print(f"[yellow]Warning: {remaining_dups} duplicate titles remain after {max_retries} attempts[/yellow]")
        
        return results
