"""
PR Generation Module for the Automated Refactoring Pipeline.

This module creates Pull Requests on GitHub with refactoring suggestions
and documentation. It does NOT modify the actual codebase.
"""
import json
import os
from datetime import datetime
from pathlib import Path
from dataclasses import asdict

from github import Github, GithubException

from config import (
    GITHUB_TOKEN,
    REPO_OWNER,
    REPO_NAME,
    OUTPUT_FOLDER,
    BRANCH_PREFIX,
)
from detector import DesignSmell, FileMetrics
from refactorer import RefactoringSuggestion


class PRGenerator:
    """Generates Pull Requests with refactoring documentation."""

    def __init__(self, repo_path: str):
        """
        Initialize the PR generator.
        
        Args:
            repo_path: Path to the local repository
        """
        self.repo_path = Path(repo_path)
        self.output_path = self.repo_path / OUTPUT_FOLDER
        
        self.github = None
        self.repo = None
        
        if GITHUB_TOKEN and REPO_OWNER and REPO_NAME:
            try:
                self.github = Github(GITHUB_TOKEN)
                self.repo = self.github.get_repo(f"{REPO_OWNER}/{REPO_NAME}")
            except Exception as e:
                print(f"   Note: GitHub connection not available ({e}). Documentation will be saved locally.")

    def generate_documentation(
        self,
        smells: list[DesignSmell],
        suggestions: list[RefactoringSuggestion],
        metrics: list[FileMetrics],
    ) -> str:
        """
        Generate markdown documentation for the refactoring suggestions.
        
        Returns:
            Path to the generated documentation file
        """
        self.output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        doc_filename = f"refactoring_report_{timestamp}.md"
        doc_path = self.output_path / doc_filename
        
        content = self._generate_markdown(smells, suggestions, metrics, timestamp)
        
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return str(doc_path)

    def _generate_markdown(
        self,
        smells: list[DesignSmell],
        suggestions: list[RefactoringSuggestion],
        metrics: list[FileMetrics],
        timestamp: str,
    ) -> str:
        """Generate the markdown content for the report."""
        lines = [
            "# 🔧 Automated Refactoring Suggestions",
            "",
            f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Files Analyzed**: {len(metrics)}",
            f"**Design Smells Detected**: {len(smells)}",
            f"**Refactoring Suggestions**: {len(suggestions)}",
            "",
            "---",
            "",
            "## 📊 Executive Summary",
            "",
            self._generate_summary(smells, metrics),
            "",
            "---",
            "",
            "## 🔍 Detected Design Smells",
            "",
        ]
        
        # Group smells by severity
        high_smells = [s for s in smells if s.severity == "HIGH"]
        medium_smells = [s for s in smells if s.severity == "MEDIUM"]
        low_smells = [s for s in smells if s.severity == "LOW"]
        
        if high_smells:
            lines.append("### 🔴 High Severity")
            lines.append("")
            for smell in high_smells:
                lines.extend(self._format_smell(smell))
            lines.append("")
        
        if medium_smells:
            lines.append("### 🟡 Medium Severity")
            lines.append("")
            for smell in medium_smells:
                lines.extend(self._format_smell(smell))
            lines.append("")
        
        if low_smells:
            lines.append("### 🟢 Low Severity")
            lines.append("")
            for smell in low_smells:
                lines.extend(self._format_smell(smell))
            lines.append("")
        
        lines.extend([
            "---",
            "",
            "## 💡 Refactoring Suggestions",
            "",
        ])
        
        for i, suggestion in enumerate(suggestions, 1):
            lines.extend(self._format_suggestion(suggestion, i))
        
        lines.extend([
            "---",
            "",
            "## 📈 Metrics Summary",
            "",
            self._generate_metrics_table(metrics),
            "",
            "---",
            "",
            "## ⚠️ Important Notes",
            "",
            "> **This document contains SUGGESTIONS ONLY.**",
            "> ",
            "> - These changes have NOT been applied to the codebase",
            "> - Review each suggestion carefully before implementation",
            "> - Ensure all tests pass after applying any changes",
            "> - Consider the impact on dependent code",
            "",
        ])
        
        return "\n".join(lines)

    def _generate_summary(self, smells: list[DesignSmell], metrics: list[FileMetrics]) -> str:
        """Generate executive summary."""
        smell_types = {}
        for smell in smells:
            smell_types[smell.smell_type] = smell_types.get(smell.smell_type, 0) + 1
        
        top_issues = sorted(smell_types.items(), key=lambda x: x[1], reverse=True)[:3]
        
        summary = [
            f"This analysis identified **{len(smells)} design smells** across **{len(metrics)} files**.",
            "",
        ]
        
        if top_issues:
            summary.append("**Top Issues:**")
            for issue_type, count in top_issues:
                summary.append(f"- {issue_type}: {count} occurrences")
        
        return "\n".join(summary)

    def _format_smell(self, smell: DesignSmell) -> list[str]:
        """Format a single smell for display."""
        return [
            f"#### {smell.smell_type}: `{smell.location}`",
            f"- **File**: `{smell.file_path}`",
            f"- **Lines**: {smell.line_range}",
            f"- **Detection**: {smell.detection_method}",
            f"- **Description**: {smell.description}",
            "",
        ]

    def _format_suggestion(self, suggestion: RefactoringSuggestion, index: int) -> list[str]:
        """Format a refactoring suggestion."""
        lines = [
            f"### {index}. {suggestion.technique}",
            "",
            f"**Addressing**: {suggestion.smell.smell_type} in `{suggestion.smell.location}`",
            "",
            f"**Explanation**: {suggestion.explanation}",
            "",
        ]
        
        if suggestion.original_code:
            lines.extend([
                "**Before (Current Code):**",
                "```java",
                suggestion.original_code[:1000] + ("..." if len(suggestion.original_code) > 1000 else ""),
                "```",
                "",
            ])
        
        if suggestion.suggested_code:
            lines.extend([
                "**After (Suggested):**",
                "```java",
                suggestion.suggested_code[:1000] + ("..." if len(suggestion.suggested_code) > 1000 else ""),
                "```",
                "",
            ])
        
        if suggestion.changes_summary:
            lines.append("**Changes:**")
            for change in suggestion.changes_summary[:5]:
                lines.append(f"- {change}")
            lines.append("")
        
        if suggestion.benefits:
            lines.append("**Benefits:**")
            for benefit in suggestion.benefits[:3]:
                lines.append(f"- ✅ {benefit}")
            lines.append("")
        
        if suggestion.risks:
            lines.append("**Considerations:**")
            for risk in suggestion.risks[:3]:
                lines.append(f"- ⚠️ {risk}")
            lines.append("")
        
        lines.append("---")
        lines.append("")
        
        return lines

    def _generate_metrics_table(self, metrics: list[FileMetrics]) -> str:
        """Generate a metrics summary table."""
        if not metrics:
            return "No metrics available."
        
        total_lines = sum(m.total_lines for m in metrics)
        total_methods = sum(m.method_count for m in metrics)
        avg_methods = total_methods / len(metrics) if metrics else 0
        
        # Find largest files
        sorted_by_lines = sorted(metrics, key=lambda m: m.total_lines, reverse=True)[:5]
        
        lines = [
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total Files | {len(metrics)} |",
            f"| Total Lines | {total_lines:,} |",
            f"| Total Methods | {total_methods:,} |",
            f"| Avg Methods/File | {avg_methods:.1f} |",
            "",
            "**Largest Files:**",
            "",
            "| File | Lines | Methods |",
            "|------|-------|---------|",
        ]
        
        for m in sorted_by_lines:
            lines.append(f"| `{Path(m.file_path).name}` | {m.total_lines} | {m.method_count} |")
        
        return "\n".join(lines)

    def create_pull_request(
        self,
        doc_path: str,
        smells: list[DesignSmell],
        suggestions: list[RefactoringSuggestion],
    ) -> str:
        """
        Create a Pull Request with the refactoring documentation.
        
        Returns:
            URL of the created PR
        """
        if not self.github or not self.repo:
            return self._create_local_pr_info(doc_path, smells, suggestions)

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            branch_name = f"{BRANCH_PREFIX}-{timestamp}"
            
            # Get the default branch
            default_branch = self.repo.default_branch
            default_ref = self.repo.get_git_ref(f"heads/{default_branch}")
            
            # Create new branch
            self.repo.create_git_ref(
                ref=f"refs/heads/{branch_name}",
                sha=default_ref.object.sha
            )
            
            # Read the documentation file
            with open(doc_path, "r") as f:
                doc_content = f.read()
            
            # Create the file in the new branch
            rel_doc_path = str(Path(doc_path).relative_to(self.repo_path))
            self.repo.create_file(
                path=rel_doc_path,
                message=f"docs: Add automated refactoring suggestions ({timestamp})",
                content=doc_content,
                branch=branch_name,
            )
            
            # Create PR description
            pr_body = self._generate_pr_description(smells, suggestions)
            
            # Create the PR
            pr = self.repo.create_pull(
                title=f"🔧 Automated Refactoring Suggestions - {datetime.now().strftime('%Y-%m-%d')}",
                body=pr_body,
                head=branch_name,
                base=default_branch,
            )
            
            return pr.html_url

        except GithubException as e:
            print(f"GitHub API error: {e}")
            return self._create_local_pr_info(doc_path, smells, suggestions)

    def _generate_pr_description(
        self,
        smells: list[DesignSmell],
        suggestions: list[RefactoringSuggestion],
    ) -> str:
        """Generate the PR description."""
        high_count = len([s for s in smells if s.severity == "HIGH"])
        medium_count = len([s for s in smells if s.severity == "MEDIUM"])
        
        lines = [
            "## 🤖 Automated Refactoring Pipeline",
            "",
            "This PR contains **documentation only** with suggested refactorings detected by automated analysis.",
            "",
            "### 📊 Summary",
            "",
            f"- **Total Design Smells**: {len(smells)}",
            f"  - 🔴 High: {high_count}",
            f"  - 🟡 Medium: {medium_count}",
            f"  - 🟢 Low: {len(smells) - high_count - medium_count}",
            f"- **Refactoring Suggestions**: {len(suggestions)}",
            "",
            "### 💡 Top Suggestions",
            "",
        ]
        
        for suggestion in suggestions[:5]:
            lines.append(f"- **{suggestion.technique}** for `{suggestion.smell.location}` ({suggestion.smell.smell_type})")
        
        lines.extend([
            "",
            "### ⚠️ Important",
            "",
            "> This PR adds documentation with refactoring suggestions.",
            "> **No code changes have been made to the main codebase.**",
            "> Review the suggestions in the attached markdown file.",
            "",
            "---",
            "*Generated automatically by the LLM Refactoring Pipeline*",
        ])
        
        return "\n".join(lines)

    def _create_local_pr_info(
        self,
        doc_path: str,
        smells: list[DesignSmell],
        suggestions: list[RefactoringSuggestion],
    ) -> str:
        """Create local PR info when GitHub API is not available."""
        pr_info_path = self.output_path / "pr_info.json"
        
        pr_info = {
            "documentation_path": doc_path,
            "smells_count": len(smells),
            "suggestions_count": len(suggestions),
            "pr_description": self._generate_pr_description(smells, suggestions),
            "created_at": datetime.now().isoformat(),
            "status": "local_only",
            "instructions": [
                "1. Create a new branch from main/master",
                "2. Add the documentation file to the branch",
                "3. Create a PR manually using the description above",
            ]
        }
        
        with open(pr_info_path, "w") as f:
            json.dump(pr_info, f, indent=2)
        
        return f"Local PR info saved to: {pr_info_path}"


def main():
    """Main function for standalone testing."""
    import sys
    from detector import DesignSmellDetector
    from refactorer import LLMRefactorer
    
    repo_path = sys.argv[1] if len(sys.argv) > 1 else "."
    
    # Detect smells
    print("Detecting design smells...")
    detector = DesignSmellDetector(repo_path, use_llm=False)
    smells, metrics = detector.scan_repository()
    
    # Generate suggestions (limited for testing)
    print("Generating refactoring suggestions...")
    refactorer = LLMRefactorer(repo_path)
    suggestions = refactorer.generate_suggestions(smells, max_suggestions=3)
    
    # Generate documentation
    print("Generating documentation...")
    pr_gen = PRGenerator(repo_path)
    doc_path = pr_gen.generate_documentation(smells, suggestions, metrics)
    print(f"Documentation saved to: {doc_path}")
    
    # Create PR (or local info)
    print("Creating PR...")
    result = pr_gen.create_pull_request(doc_path, smells, suggestions)
    print(f"Result: {result}")


if __name__ == "__main__":
    main()
