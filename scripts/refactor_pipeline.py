#!/usr/bin/env python3
"""
Automated LLM Refactoring Pipeline for Apache Roller
=====================================================

This script scans Java source code for design smells, uses the Google Gemini API
to generate refactored code suggestions, and creates a GitHub Pull Request with
the suggested changes.

Usage:
    python refactor_pipeline.py                    # Full run (requires GEMINI_API_KEY + GITHUB_TOKEN)
    python refactor_pipeline.py --dry-run          # Detect smells only, skip LLM + PR
    python refactor_pipeline.py --module search    # Target a specific module

Environment Variables:
    GEMINI_API_KEY   - Google Gemini API key
    GITHUB_TOKEN     - GitHub personal access token (or GITHUB_TOKEN from Actions)
    GITHUB_REPOSITORY - e.g. "serc-courses/project-1-team-46" (auto-set in Actions)
"""

import os
import re
import sys
import json
import glob
import time
import argparse
import datetime
import textwrap
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
JAVA_SRC = REPO_ROOT / "app" / "src" / "main" / "java" / "org" / "apache" / "roller"

# Module definitions: each module is a list of glob patterns relative to JAVA_SRC
MODULES = {
    "search": {
        "name": "Search and Indexing Subsystem",
        "description": "Handles Lucene-based full-text search, indexing operations, and search result rendering.",
        "globs": [
            "weblogger/business/search/**/*.java",
            "weblogger/pojos/CommentSearchCriteria.java",
            "weblogger/pojos/WeblogEntrySearchCriteria.java",
            "weblogger/ui/rendering/model/SearchResults*.java",
            "weblogger/ui/rendering/pagers/SearchResults*.java",
            "weblogger/ui/rendering/servlets/SearchServlet.java",
            "weblogger/ui/rendering/util/WeblogSearchRequest.java",
            "weblogger/ui/struts2/editor/MediaFileSearchBean.java",
            "weblogger/webservices/opensearch/**/*.java",
        ],
    },
    "user": {
        "name": "User and Role Management Subsystem",
        "description": "Manages user accounts, roles, permissions, and authentication.",
        "globs": [
            "weblogger/business/UserManager.java",
            "weblogger/business/jpa/JPAUserManagerImpl.java",
            "weblogger/pojos/User.java",
            "weblogger/pojos/UserRole.java",
            "weblogger/pojos/WeblogPermission.java",
            "weblogger/pojos/GlobalPermission.java",
            "weblogger/pojos/wrapper/UserWrapper.java",
            "weblogger/ui/core/security/**/*.java",
            "weblogger/ui/rendering/pagers/UsersPager.java",
            "weblogger/ui/struts2/admin/CreateUserBean.java",
            "weblogger/ui/struts2/admin/UserAdmin.java",
            "weblogger/ui/struts2/admin/UserEdit.java",
            "weblogger/ui/struts2/ajax/UserDataServlet.java",
        ],
    },
    "weblog": {
        "name": "Weblog and Content Subsystem",
        "description": "Core weblog management: entries, categories, bookmarks, comments, themes, and rendering.",
        "globs": [
            "weblogger/business/WeblogManager.java",
            "weblogger/business/WeblogEntryManager.java",
            "weblogger/business/jpa/JPAWeblogManagerImpl.java",
            "weblogger/business/jpa/JPAWeblogEntryManagerImpl.java",
            "weblogger/business/themes/**/*.java",
            "weblogger/pojos/Weblog.java",
            "weblogger/pojos/WeblogEntry.java",
            "weblogger/pojos/WeblogEntryComment.java",
            "weblogger/pojos/WeblogEntryTag.java",
            "weblogger/pojos/WeblogCategory.java",
            "weblogger/pojos/WeblogBookmark.java",
            "weblogger/pojos/WeblogBookmarkFolder.java",
            "weblogger/pojos/WeblogTemplate.java",
            "weblogger/pojos/WeblogTheme.java",
            "weblogger/pojos/WeblogHitCount.java",
            "weblogger/pojos/wrapper/WeblogEntryWrapper.java",
            "weblogger/pojos/wrapper/WeblogEntryCommentWrapper.java",
            "weblogger/pojos/wrapper/WeblogCategoryWrapper.java",
            "weblogger/pojos/wrapper/WeblogWrapper.java",
        ],
    },
}

# Smell detection thresholds
GOD_CLASS_LINE_THRESHOLD = 300
GOD_CLASS_METHOD_THRESHOLD = 15
LONG_METHOD_THRESHOLD = 50
LONG_PARAM_THRESHOLD = 4

# Groq API configuration (OpenAI-compatible)
# Uses GEMINI_API_KEY env var to store the Groq API key (keeps existing secret name)
# Free tier TPM limits are very low (e.g. 12K TPM for llama-3.3-70b-versatile)
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]
MAX_RETRIES = 3
RETRY_BASE_DELAY = 30  # seconds — first retry waits 30s, then 60s, then 120s
INTER_BATCH_DELAY = 65  # seconds between batches to reset TPM window

# Token budget per batch: Groq free tier = 12K TPM for 70b model
# Reserve ~4K tokens for output, so ~8K tokens input per batch
# ~4 chars per token → ~32K chars per batch
MAX_CHARS_PER_BATCH = 32_000


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class DesignSmell:
    file: str
    smell_type: str
    description: str
    line_start: int = 0
    line_end: int = 0
    severity: str = "medium"  # low, medium, high

    def to_dict(self):
        return asdict(self)


@dataclass
class RefactoringSuggestion:
    file: str
    original_snippet: str
    suggested_code: str
    smell_type: str
    technique: str
    explanation: str


@dataclass
class PipelineResult:
    module_name: str
    files_scanned: int
    total_lines: int
    smells: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)
    timestamp: str = ""


# ---------------------------------------------------------------------------
# 1. SMELL DETECTOR
# ---------------------------------------------------------------------------

class SmellDetector:
    """Scans Java files for design smells using heuristic rules."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.java_src = repo_root / "app" / "src" / "main" / "java" / "org" / "apache" / "roller"

    def collect_files(self, module_key: str) -> list[Path]:
        """Collect all Java files for a given module."""
        module = MODULES[module_key]
        files = set()
        for pattern in module["globs"]:
            matched = glob.glob(str(self.java_src / pattern), recursive=True)
            files.update(Path(f) for f in matched if f.endswith(".java"))
        # Filter out package-info.java files (they are just documentation)
        files = {f for f in files if f.name != "package-info.java"}
        return sorted(files)

    def detect_smells(self, files: list[Path]) -> list[DesignSmell]:
        """Run all smell detectors on the given files."""
        smells = []
        for filepath in files:
            try:
                content = filepath.read_text(encoding="utf-8", errors="ignore")
                lines = content.splitlines()
            except Exception:
                continue

            rel_path = str(filepath.relative_to(self.repo_root))
            smells.extend(self._detect_god_class(rel_path, lines))
            smells.extend(self._detect_long_methods(rel_path, lines))
            smells.extend(self._detect_long_param_lists(rel_path, lines))
            smells.extend(self._detect_feature_envy(rel_path, lines, content))

        return smells

    def _detect_god_class(self, filepath: str, lines: list[str]) -> list[DesignSmell]:
        """Detect God Class: too many lines or too many public methods."""
        smells = []
        line_count = len(lines)
        public_methods = sum(
            1 for line in lines
            if re.search(r'\bpublic\b.*\(.*\)\s*(\{|throws)', line) and 'class ' not in line
        )

        if line_count > GOD_CLASS_LINE_THRESHOLD:
            smells.append(DesignSmell(
                file=filepath,
                smell_type="God Class (Excessive Size)",
                description=f"Class has {line_count} lines (threshold: {GOD_CLASS_LINE_THRESHOLD}). "
                            f"Consider decomposing into smaller, focused classes.",
                line_start=1,
                line_end=line_count,
                severity="high" if line_count > 500 else "medium",
            ))

        if public_methods > GOD_CLASS_METHOD_THRESHOLD:
            smells.append(DesignSmell(
                file=filepath,
                smell_type="God Class (Too Many Methods)",
                description=f"Class exposes {public_methods} public methods "
                            f"(threshold: {GOD_CLASS_METHOD_THRESHOLD}). "
                            f"Consider applying the Single Responsibility Principle.",
                line_start=1,
                line_end=len(lines),
                severity="high" if public_methods > 25 else "medium",
            ))

        return smells

    def _detect_long_methods(self, filepath: str, lines: list[str]) -> list[DesignSmell]:
        """Detect Long Method: methods with too many lines."""
        smells = []
        method_pattern = re.compile(
            r'^\s*(public|protected|private|static|\s)+'
            r'[\w<>\[\],\s]+\s+(\w+)\s*\([^)]*\)'
        )

        i = 0
        while i < len(lines):
            match = method_pattern.match(lines[i])
            if match:
                method_name = match.group(2)
                # Skip constructors and simple getters/setters
                if method_name in ('if', 'for', 'while', 'switch', 'catch'):
                    i += 1
                    continue

                method_start = i + 1  # 1-indexed
                brace_count = 0
                found_open = False
                j = i

                while j < len(lines):
                    for ch in lines[j]:
                        if ch == '{':
                            brace_count += 1
                            found_open = True
                        elif ch == '}':
                            brace_count -= 1

                    if found_open and brace_count == 0:
                        method_end = j + 1  # 1-indexed
                        method_length = method_end - method_start + 1

                        if method_length > LONG_METHOD_THRESHOLD:
                            smells.append(DesignSmell(
                                file=filepath,
                                smell_type="Long Method",
                                description=f"Method '{method_name}' is {method_length} lines "
                                            f"(threshold: {LONG_METHOD_THRESHOLD}). "
                                            f"Consider extracting sub-methods.",
                                line_start=method_start,
                                line_end=method_end,
                                severity="high" if method_length > 100 else "medium",
                            ))
                        i = j
                        break
                    j += 1
            i += 1

        return smells

    def _detect_long_param_lists(self, filepath: str, lines: list[str]) -> list[DesignSmell]:
        """Detect Long Parameter List / Data Clumps."""
        smells = []
        method_sig_pattern = re.compile(
            r'(public|protected|private|static)\s+[\w<>\[\],\s]+\s+(\w+)\s*\(([^)]+)\)'
        )

        for i, line in enumerate(lines):
            match = method_sig_pattern.search(line)
            if match:
                method_name = match.group(2)
                params = match.group(3)
                param_count = len([p.strip() for p in params.split(',') if p.strip()])

                if param_count > LONG_PARAM_THRESHOLD:
                    smells.append(DesignSmell(
                        file=filepath,
                        smell_type="Long Parameter List / Data Clumps",
                        description=f"Method '{method_name}' has {param_count} parameters "
                                    f"(threshold: {LONG_PARAM_THRESHOLD}). "
                                    f"Consider introducing a Parameter Object.",
                        line_start=i + 1,
                        line_end=i + 1,
                        severity="medium",
                    ))

        return smells

    def _detect_feature_envy(self, filepath: str, lines: list[str], content: str) -> list[DesignSmell]:
        """Detect Feature Envy: methods that reference other classes excessively."""
        smells = []
        # Find all class names imported
        imports = re.findall(r'import\s+[\w.]+\.(\w+)\s*;', content)
        if not imports:
            return smells

        method_pattern = re.compile(
            r'^\s*(public|protected|private|static|\s)+'
            r'[\w<>\[\],\s]+\s+(\w+)\s*\([^)]*\)'
        )

        i = 0
        while i < len(lines):
            match = method_pattern.match(lines[i])
            if match:
                method_name = match.group(2)
                if method_name in ('if', 'for', 'while', 'switch', 'catch'):
                    i += 1
                    continue

                method_start = i
                brace_count = 0
                found_open = False
                j = i
                method_lines = []

                while j < len(lines):
                    method_lines.append(lines[j])
                    for ch in lines[j]:
                        if ch == '{':
                            brace_count += 1
                            found_open = True
                        elif ch == '}':
                            brace_count -= 1
                    if found_open and brace_count == 0:
                        break
                    j += 1

                method_body = '\n'.join(method_lines)
                # Count references to external classes
                external_refs = 0
                for cls_name in set(imports):
                    count = len(re.findall(r'\b' + cls_name + r'\b', method_body))
                    if count > 0:
                        external_refs += count

                method_length = j - method_start + 1
                if method_length > 5 and external_refs > 8:
                    smells.append(DesignSmell(
                        file=filepath,
                        smell_type="Feature Envy",
                        description=f"Method '{method_name}' references {external_refs} "
                                    f"external class symbols. It may belong in another class.",
                        line_start=method_start + 1,
                        line_end=j + 1,
                        severity="medium",
                    ))

                i = j
            i += 1

        return smells


# ---------------------------------------------------------------------------
# 2. LLM REFACTORER (Module-Level Batching)
# ---------------------------------------------------------------------------

class LLMRefactorer:
    """Sends module-level batched code + smell context to Groq for refactoring."""

    def __init__(self, api_key: str):
        from openai import OpenAI
        self.client = OpenAI(
            api_key=api_key,
            base_url=GROQ_BASE_URL,
        )
        self.active_model_idx = 0

    @property
    def active_model_name(self) -> str:
        return GROQ_MODELS[self.active_model_idx]

    def build_module_prompt(
        self,
        module_name: str,
        files: list[Path],
        smells: list[DesignSmell],
        repo_root: Path,
    ) -> list[str]:
        """
        Concatenate module files into prompt batches sized for Groq's TPM limits.
        Each batch stays under MAX_CHARS_PER_BATCH (~8K tokens input).
        Files are greedily packed into batches by size.
        Returns a list of prompts.
        """
        # Read all files
        file_contents = {}
        for f in files:
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                rel = str(f.relative_to(repo_root))
                file_contents[rel] = content
            except Exception:
                continue

        # Build smell report
        smell_report = self._format_smell_report(smells)

        # Build system instruction (compact to save tokens)
        system_instruction = textwrap.dedent(f"""\
        You are a Java architect reviewing the "{module_name}" module of Apache Roller.
        Below are Java source files separated by `// === FILE: <path> ===` markers,
        followed by a SMELL REPORT from static analysis.

        For each file with actionable smells, produce a refactored version.
        Preserve all functionality. Respond in this JSON format (no markdown fences):
        {{
          "suggestions": [
            {{
              "file": "<relative path>",
              "smell_type": "<smell addressed>",
              "technique": "<refactoring technique>",
              "explanation": "<1-2 sentence explanation>",
              "original_snippet": "<key changed lines, max 20 lines>",
              "suggested_code": "<complete refactored file>"
            }}
          ],
          "summary": "<overall summary>"
        }}
        Skip files with no actionable smells.
        """)

        system_chars = len(system_instruction) + len(smell_report) + 100  # overhead
        available_chars = MAX_CHARS_PER_BATCH - system_chars

        # Greedily pack files into batches
        batches = []
        current_batch_files = {}
        current_batch_size = 0

        for rel_path, content in sorted(file_contents.items()):
            file_block = f"\n// === FILE: {rel_path} ===\n{content}\n"
            file_size = len(file_block)

            # If single file exceeds budget, it gets its own batch
            if file_size > available_chars:
                if current_batch_files:
                    batches.append(current_batch_files)
                batches.append({rel_path: content})
                current_batch_files = {}
                current_batch_size = 0
                continue

            # If adding this file would exceed budget, start new batch
            if current_batch_size + file_size > available_chars:
                batches.append(current_batch_files)
                current_batch_files = {}
                current_batch_size = 0

            current_batch_files[rel_path] = content
            current_batch_size += file_size

        if current_batch_files:
            batches.append(current_batch_files)

        # Build prompts from batches
        prompts = []
        for batch_files in batches:
            code_block = ""
            for rel_path, content in sorted(batch_files.items()):
                code_block += f"\n// === FILE: {rel_path} ===\n{content}\n"

            # Only include smells relevant to files in this batch
            batch_file_set = set(batch_files.keys())
            batch_smells = [s for s in smells if s.file in batch_file_set]
            batch_smell_report = self._format_smell_report(batch_smells) if batch_smells else smell_report

            prompt = (f"{system_instruction}\n\n--- SOURCE CODE ---\n{code_block}"
                      f"\n\n--- SMELL REPORT ---\n{batch_smell_report}")
            prompts.append(prompt)

        print(f"[INFO] Module split into {len(prompts)} batch(es) "
              f"for Groq's TPM limits")
        return prompts

    def _format_smell_report(self, smells: list[DesignSmell]) -> str:
        if not smells:
            return "No design smells detected."

        lines = []
        for i, s in enumerate(smells, 1):
            lines.append(
                f"{i}. [{s.severity.upper()}] {s.smell_type} in {s.file} "
                f"(lines {s.line_start}-{s.line_end}): {s.description}"
            )
        return '\n'.join(lines)

    def refactor(
        self,
        module_name: str,
        files: list[Path],
        smells: list[DesignSmell],
        repo_root: Path,
    ) -> list[RefactoringSuggestion]:
        """Send module code + smell context to Groq and parse suggestions."""
        prompts = self.build_module_prompt(module_name, files, smells, repo_root)
        all_suggestions = []

        for idx, prompt in enumerate(prompts):
            batch_label = f" (batch {idx + 1}/{len(prompts)})" if len(prompts) > 1 else ""
            est_tokens = len(prompt) // 4
            print(f"[INFO] Sending module to Groq API ({self.active_model_name}){batch_label}... "
                  f"({len(prompt)} chars, ~{est_tokens} tokens)")

            # Retry with exponential backoff + model fallback for rate limiting
            raw = None
            for attempt in range(MAX_RETRIES + 1):
                try:
                    response = self.client.chat.completions.create(
                        model=self.active_model_name,
                        messages=[
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.3,
                        max_tokens=32000,
                    )
                    raw = response.choices[0].message.content.strip()
                    break  # success — exit retry loop

                except Exception as e:
                    error_str = str(e).lower()
                    is_rate_limit = any(kw in error_str for kw in [
                        "rate limit", "resource exhausted", "quota", "429", "too many requests"
                    ])

                    if is_rate_limit:
                        # Try falling back to next model first
                        if self.active_model_idx < len(GROQ_MODELS) - 1:
                            self.active_model_idx += 1
                            print(f"[WARN] Rate limited on {GROQ_MODELS[self.active_model_idx - 1]}. "
                                  f"Falling back to {self.active_model_name}...")
                            continue  # retry immediately with new model

                        if attempt < MAX_RETRIES:
                            delay = RETRY_BASE_DELAY * (2 ** attempt)  # 30s, 60s, 120s
                            print(f"[WARN] Rate limited (attempt {attempt + 1}/{MAX_RETRIES + 1}). "
                                  f"Retrying in {delay}s...")
                            time.sleep(delay)
                        else:
                            print(f"[ERROR] Groq API call failed after all retries: {e}")
                            break
                    else:
                        print(f"[ERROR] Groq API call failed: {e}")
                        break

            if raw is None:
                print(f"[WARN] Skipping batch {idx + 1} — no response from Groq.")
                continue

            try:
                # Strip markdown code fences if present
                if raw.startswith("```"):
                    raw = re.sub(r'^```\w*\n', '', raw)
                    raw = re.sub(r'\n```$', '', raw)

                data = json.loads(raw)

                for s in data.get("suggestions", []):
                    all_suggestions.append(RefactoringSuggestion(
                        file=s.get("file", ""),
                        original_snippet=s.get("original_snippet", ""),
                        suggested_code=s.get("suggested_code", ""),
                        smell_type=s.get("smell_type", ""),
                        technique=s.get("technique", ""),
                        explanation=s.get("explanation", ""),
                    ))

                summary = data.get("summary", "")
                if summary:
                    print(f"[INFO] LLM summary: {summary}")

            except json.JSONDecodeError as e:
                print(f"[WARN] Failed to parse LLM response as JSON: {e}")
                print(f"[WARN] Raw response (first 500 chars): {raw[:500]}")

            # If there are more batches, wait for TPM window to reset
            if idx < len(prompts) - 1:
                print(f"[INFO] Waiting {INTER_BATCH_DELAY}s for TPM window to reset...")
                time.sleep(INTER_BATCH_DELAY)

        return all_suggestions


# ---------------------------------------------------------------------------
# 3. PR GENERATOR
# ---------------------------------------------------------------------------

class PRGenerator:
    """Creates a GitHub Pull Request with refactoring suggestions."""

    def __init__(self, github_token: str, repo_name: str):
        from github import Github
        self.gh = Github(github_token)
        self.repo = self.gh.get_repo(repo_name)

    def create_pr(self, result: PipelineResult, suggestions: list[RefactoringSuggestion]) -> str:
        """Create a branch, commit suggested files, and open a PR."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        branch_name = f"refactor/llm-automated-{timestamp}"

        # Get the default branch SHA
        default_branch = self.repo.default_branch
        base_ref = self.repo.get_git_ref(f"heads/{default_branch}")
        base_sha = base_ref.object.sha

        # Create new branch
        self.repo.create_git_ref(f"refs/heads/{branch_name}", base_sha)
        print(f"[INFO] Created branch: {branch_name}")

        # Commit refactored files under refactored_suggestions/
        module_slug = result.module_name.lower().replace(" ", "_").replace("&", "and")
        for suggestion in suggestions:
            if not suggestion.suggested_code.strip():
                continue

            # Derive output path
            original_basename = Path(suggestion.file).name
            output_path = f"refactored_suggestions/{module_slug}/{original_basename}"

            try:
                self.repo.create_file(
                    path=output_path,
                    message=f"refactor: LLM suggestion for {original_basename} ({suggestion.technique})",
                    content=suggestion.suggested_code,
                    branch=branch_name,
                )
                print(f"[INFO] Committed: {output_path}")
            except Exception as e:
                print(f"[WARN] Failed to commit {output_path}: {e}")

        # Build PR body
        pr_body = self._build_pr_body(result, suggestions)

        # Create Pull Request
        pr = self.repo.create_pull(
            title=f"🤖 Automated Refactoring: {result.module_name}",
            body=pr_body,
            head=branch_name,
            base=default_branch,
        )
        print(f"[INFO] Pull Request created: {pr.html_url}")
        return pr.html_url

    def _build_pr_body(self, result: PipelineResult, suggestions: list[RefactoringSuggestion]) -> str:
        """Build a detailed PR description."""
        lines = [
            "# 🤖 Automated LLM Refactoring Report",
            "",
            f"**Module**: {result.module_name}",
            f"**Generated at**: {result.timestamp}",
            f"**Pipeline**: GitHub Actions — LLM Refactoring Pipeline",
            "",
            "---",
            "",
            "## 📊 Metrics",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Files Scanned | {result.files_scanned} |",
            f"| Total Lines | {result.total_lines} |",
            f"| Design Smells Found | {len(result.smells)} |",
            f"| Refactoring Suggestions | {len(suggestions)} |",
            "",
            "---",
            "",
            "## 🔍 Detected Design Smells",
            "",
        ]

        # Group smells by type
        smell_types = {}
        for s in result.smells:
            smell_types.setdefault(s["smell_type"], []).append(s)

        for stype, slist in smell_types.items():
            lines.append(f"### {stype}")
            lines.append("")
            for s in slist:
                lines.append(f"- **{s['file']}** (lines {s['line_start']}-{s['line_end']}): "
                             f"{s['description']} [{s['severity'].upper()}]")
            lines.append("")

        lines.extend([
            "---",
            "",
            "## 🔧 Applied Refactoring Techniques",
            "",
        ])

        for i, s in enumerate(suggestions, 1):
            lines.extend([
                f"### {i}. {s.technique} — `{Path(s.file).name}`",
                "",
                f"**Smell**: {s.smell_type}",
                f"**Explanation**: {s.explanation}",
                "",
                "<details>",
                "<summary>View original snippet</summary>",
                "",
                "```java",
                s.original_snippet,
                "```",
                "",
                "</details>",
                "",
            ])

        lines.extend([
            "---",
            "",
            "> **Note**: This PR contains *suggested* refactored code under "
            "`refactored_suggestions/`. The original source code is **not modified**. "
            "Review the suggestions and apply manually if appropriate.",
            "",
            "---",
            "*Generated by the Automated LLM Refactoring Pipeline*",
        ])

        return '\n'.join(lines)


# ---------------------------------------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------------------------------------

def run_pipeline(module_key: str, dry_run: bool = False):
    """Execute the full refactoring pipeline."""
    print("=" * 60)
    print("  Automated LLM Refactoring Pipeline")
    print("=" * 60)
    print()

    module_info = MODULES[module_key]
    print(f"[INFO] Target module: {module_info['name']}")
    print(f"[INFO] Description: {module_info['description']}")
    print(f"[INFO] Dry run: {dry_run}")
    print()

    # --- Stage 1: Detect Smells ---
    print("[STAGE 1/3] Detecting design smells...")
    detector = SmellDetector(REPO_ROOT)
    files = detector.collect_files(module_key)
    print(f"[INFO] Found {len(files)} Java files in module")

    if not files:
        print("[ERROR] No files found for module. Check glob patterns.")
        sys.exit(1)

    smells = detector.detect_smells(files)
    total_lines = sum(
        len(f.read_text(encoding="utf-8", errors="ignore").splitlines())
        for f in files
    )

    print(f"[INFO] Scanned {len(files)} files ({total_lines} lines)")
    print(f"[INFO] Found {len(smells)} design smells")
    print()

    for s in smells:
        print(f"  [{s.severity.upper():6s}] {s.smell_type}")
        print(f"          {s.file}:{s.line_start}-{s.line_end}")
        print(f"          {s.description}")
        print()

    # Build result
    result = PipelineResult(
        module_name=module_info["name"],
        files_scanned=len(files),
        total_lines=total_lines,
        smells=[s.to_dict() for s in smells],
        timestamp=datetime.datetime.now().isoformat(),
    )

    if dry_run:
        print("[INFO] Dry run — skipping LLM refactoring and PR generation.")
        # Save smell report to file
        report_path = REPO_ROOT / "scripts" / "smell_report.json"
        with open(report_path, 'w') as f:
            json.dump(asdict(result), f, indent=2)
        print(f"[INFO] Smell report saved to: {report_path}")
        return result

    # --- Stage 2: LLM Refactoring ---
    print("[STAGE 2/3] Generating refactored code via Gemini API...")
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[ERROR] GEMINI_API_KEY environment variable not set.")
        sys.exit(1)

    refactorer = LLMRefactorer(api_key)
    suggestions = refactorer.refactor(
        module_name=module_info["name"],
        files=files,
        smells=smells,
        repo_root=REPO_ROOT,
    )
    print(f"[INFO] Received {len(suggestions)} refactoring suggestions")
    print()

    # --- Stage 3: Create Pull Request ---
    print("[STAGE 3/3] Creating Pull Request...")
    github_token = os.environ.get("GITHUB_TOKEN")
    repo_name = os.environ.get("GITHUB_REPOSITORY", "serc-courses/project-1-team-46")

    if not github_token:
        print("[ERROR] GITHUB_TOKEN environment variable not set.")
        sys.exit(1)

    pr_gen = PRGenerator(github_token, repo_name)
    pr_url = pr_gen.create_pr(result, suggestions)

    print()
    print("=" * 60)
    print(f"  ✅ Pipeline complete!")
    print(f"  PR: {pr_url}")
    print("=" * 60)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Automated LLM Refactoring Pipeline for Apache Roller"
    )
    parser.add_argument(
        "--module",
        choices=list(MODULES.keys()),
        default="search",
        help="Which module to analyze (default: search)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run smell detection only, skip LLM and PR generation",
    )
    args = parser.parse_args()

    run_pipeline(args.module, args.dry_run)


if __name__ == "__main__":
    main()
