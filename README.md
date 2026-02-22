# adk-cli

`adk-cli` is a powerful, agentic development tool built on the [Google ADK (Agent Development Kit)](https://github.com/google/adk-python). It provides a terminal-based interface (TUI) for interacting with Gemini models that have direct access to your local filesystem and shell.

## 🌟 Inspiration

This project is inspired by several leading agentic coding tools:
- **[gemini-cli](https://github.com/google/gemini-cli)**: For its clean architecture and focus on Google's Gemini models.
- **Claude Code**: For its robust, phase-based orchestration and multi-agent patterns.
- **Nano-Claw**: For its "Integrity-First" approach to code modification and file handling.

## 🚀 Key Features

- **Interactive TUI**: A rich, responsive chat interface built with [Textual](https://textual.textualize.io/).
- **Filesystem Tools**: Built-in capabilities to `ls`, `cat`, `grep`, `write`, and `edit` files.
- **Shell Integration**: Execute bash commands with user-approved security guards.
- **Skill System**: Extensible via Markdown-based "Skills" that define custom instructions and tool usage.
- **Persistent Sessions**: Automatically remembers project context and chat history using SQLite.
- **Security First**: Granular permission modes (`ask`, `auto`, `plan`) to control tool execution.
- **Project Awareness**: Automatically maps workspace roots to unique IDs for isolated session management.

## 🛠️ How It Works

`adk-cli` leverages Google ADK to orchestrate the agentic loop.

1. **Orchestration**: Uses the `Runner` and `LlmAgent` from ADK to manage the conversation flow and tool execution.
2. **Policy Engine**: A custom security plugin intercepts every tool call, checking it against a policy (e.g., read-only tools are allowed, while `bash` or `write_file` require a UI confirmation).
3. **Context Management**: It detects the project root (via `.git`, `pyproject.toml`, etc.) and manages history in a global SQLite database at `~/.adk/`.

## 🚥 Getting Started

### Prerequisites

- Python 3.14+
- A Gemini API Key from [Google AI Studio](https://aistudio.google.com/apikey).

### Installation

```bash
# Clone the repository
git clone https://github.com/your-repo/adk-cli.git
cd adk-cli

# Install dependencies (using uv is recommended)
uv sync
```

### Configuration

Set your API key in a `.env` file or export it:

```bash
export GOOGLE_API_KEY="your_api_key_here"
```

### Usage

Launch the interactive TUI:
```bash
adk
```

Execute a one-off task:
```bash
adk chat "Review the current directory and list all python files" --print
```

Manage global settings:
```bash
adk config set default_model gemini-3-flash-preview
```

## 🏗️ Development

This project uses a "Scripts to Rule Them All" pattern for development tasks:

- `./script/bootstrap`: Install dependencies and set up the environment.
- `./script/test`: Run the test suite (pytest).
- `./script/lint`: Run linting checks (ruff).

## 📄 License

This project is licensed under the Apache 2.0 License.
