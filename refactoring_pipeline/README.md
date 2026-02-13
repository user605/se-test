# 🔧 Automated Refactoring Pipeline

An LLM-powered pipeline that detects design smells in Java code and generates refactoring suggestions.

## 🌟 Features

- **Design Smell Detection**: AST-based static analysis + LLM pattern recognition
- **LLM Refactoring**: Generates code suggestions using Groq API (LLaMA 3.3 70B)
- **Large File Handling**: Chunks files >500 lines with context preservation
- **Automated PRs**: Creates GitHub PRs with detailed documentation
- **Flexible Scheduling**: Daily, weekly, or on-demand execution

## 📋 Pipeline Flow

```
┌──────────────────┐     ┌─────────────────┐     ┌──────────────────┐
│  Trigger         │────▶│  Detection      │────▶│  LLM Refactoring │
│  (Schedule/Manual)│     │  (AST + Groq)   │     │  (Suggestions)   │
└──────────────────┘     └─────────────────┘     └──────────────────┘
                                                           │
                                                           ▼
                         ┌─────────────────────────────────────────────┐
                         │  PR Generation                              │
                         │  • Documentation in refactoring-suggestions/│
                         │  • Pull Request on GitHub                   │
                         └─────────────────────────────────────────────┘
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd refactoring_pipeline
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the `refactoring_pipeline` directory:

```env
GROQ_API_KEY=your_groq_api_key
GITHUB_TOKEN=your_github_token
REPO_OWNER=your_github_username
REPO_NAME=your_repo_name
```

### 3. Run the Pipeline

```bash
# Full pipeline
python main.py --repo-path ..

# Dry run (no PR creation)
python main.py --repo-path .. --dry-run

# Static analysis only (no LLM)
python main.py --repo-path .. --no-llm

# Verbose output
python main.py --repo-path .. --verbose
```

## ⚙️ CLI Options

| Option | Description |
|--------|-------------|
| `--repo-path` | Path to repository (default: current dir) |
| `--dry-run` | Generate docs without creating PR |
| `--no-llm` | Static analysis only |
| `--max-suggestions N` | Limit refactoring suggestions (default: 10) |
| `--output-json PATH` | Save results to JSON |
| `--verbose, -v` | Enable verbose output |

## 🔍 Detected Design Smells

| Smell | Threshold | Technique |
|-------|-----------|-----------| 
| God Class | >15 methods or >10 fields | Extract Class |
| Long Method | >50 lines | Extract Method |
| Long Parameter List | >5 parameters | Parameter Object |
| Large Class | >300 lines | Split Class |
| Feature Envy | External accesses | Move Method |
| Data Class | Only getters/setters | Add Behavior |

## 📁 Project Structure

```
refactoring_pipeline/
├── main.py           # CLI orchestrator
├── detector.py       # Design smell detection
├── refactorer.py     # LLM-based suggestions
├── pr_generator.py   # PR/documentation generator
├── prompts.py        # LLM prompt templates
├── config.py         # Configuration
└── requirements.txt  # Dependencies
```

## 🤖 GitHub Actions

The workflow runs automatically and can be triggered manually.

### Setup Secrets

Add these secrets in your repository settings:
- `GROQ_API_KEY`: Your Groq API key
- `GITHUB_TOKEN`: Automatically available

### Trigger Options

1. **Weekly** (default): Sundays at 2 AM UTC
2. **Manual**: Actions → Run workflow
3. **Daily**: Uncomment cron in workflow file

## 📊 Output Example

The pipeline generates PRs with:

```markdown
# 🔧 Automated Refactoring Suggestions

## 🔍 Detected Design Smells
### 🔴 High Severity
- God Class: `WeblogEntryManager` (45 methods)

## 💡 Refactoring Suggestions
### 1. Extract Class
**Before**: Single monolithic class
**After**: Split into focused components
```

## ⚠️ Important Notes

> **Documentation Only**: This pipeline creates suggestions but does NOT modify your codebase.
> All changes are documented in PRs for human review.

## 📜 License

Apache License 2.0
