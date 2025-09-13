# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`claude-notes` is a Python CLI tool that transforms Claude Code's transcript JSONL files into terminal-viewable output and HTML files. The tool is built with `uv` for fast Python package management and is designed to be runnable with `uvx` for easy distribution and usage.

<always>Read the MEMORY.md file as well</always>

## Technology Stack

- **Python 3.11+** - Main programming language
- **uv** - Fast Python package and project manager
- **uvx** - Tool for running Python applications in isolated environments
- **CLI Framework** - To be determined (likely Click or Typer)

## Development Setup

1. Install `uv` if not already installed: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. Initialize the project environment: `uv sync`

## Test 

uv run claude-notes show /Users/plosson/devel/projects/hexrays/gitlab/ida/licensing


