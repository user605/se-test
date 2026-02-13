"""
LLM-Based Refactoring Module for the Automated Refactoring Pipeline.

This module takes detected design smells and generates refactored code suggestions
using the Gemini API. All smells are batched into a SINGLE API call to avoid
rate limiting.
"""
import json
import re
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

import google.generativeai as genai

from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    TEMPERATURE,
    MAX_TOKENS,
    CHUNK_SIZE,
)
from prompts import BATCH_REFACTORING_PROMPT
from detector import DesignSmell


@dataclass
class RefactoringSuggestion:
    """Represents a refactoring suggestion for a design smell."""
    smell: DesignSmell
    technique: str
    explanation: str
    original_code: str
    suggested_code: str
    changes_summary: list[str]
    benefits: list[str]
    risks: list[str]


class LLMRefactorer:
    """Generates refactoring suggestions using LLM (batch mode)."""

    def __init__(self, repo_path: str):
        """
        Initialize the refactorer.
        
        Args:
            repo_path: Path to the repository root
        """
        self.repo_path = Path(repo_path)
        self.suggestions: list[RefactoringSuggestion] = []
        
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel(GEMINI_MODEL)
        else:
            raise ValueError("GEMINI_API_KEY not configured")

    def _call_gemini_api(self, prompt: str) -> Optional[str]:
        """Call the Gemini API with a prompt and return the response text with rate limiting."""
        max_retries = 5
        base_delay = 15  # seconds
        
        for attempt in range(max_retries):
            try:
                # Rate limiting: wait before each request
                if attempt > 0:
                    wait_time = base_delay * (2 ** attempt)
                    print(f"   Rate limited. Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                    time.sleep(wait_time)
                else:
                    time.sleep(1)  # Base rate limiting between requests
                
                response = self.model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=TEMPERATURE,
                        max_output_tokens=MAX_TOKENS,
                    )
                )
                
                return response.text
                
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    if attempt < max_retries - 1:
                        continue
                    print(f"Gemini API rate limit exceeded after {max_retries} retries")
                    return None
                print(f"Gemini API error: {e}")
                return None
        
        return None

    def _read_file_content(self, file_path: str) -> str:
        """Read the content of a file."""
        try:
            full_path = self.repo_path / file_path
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            return ""

    def _extract_code_around_smell(self, content: str, line_range: str) -> str:
        """Extract code around the smell location with context."""
        lines = content.split('\n')
        
        try:
            # Parse line range like "15-45" or "15"
            if '-' in line_range:
                start, end = map(int, line_range.split('-'))
            else:
                start = end = int(line_range)
            
            # Add context (10 lines before and after)
            context_start = max(0, start - 10)
            context_end = min(len(lines), end + 10)
            
            # Extract lines
            extracted = lines[context_start:context_end]
            return '\n'.join(extracted)
        except:
            # If parsing fails, return first 100 lines
            return '\n'.join(lines[:100])

    def _build_batch_prompt(self, smells: list[DesignSmell]) -> str:
        """
        Build a single prompt containing all smells and their code snippets.

        Args:
            smells: List of design smells to address.

        Returns:
            Formatted prompt string for the batch API call.
        """
        smell_entries = []

        for idx, smell in enumerate(smells):
            content = self._read_file_content(smell.file_path)
            code_snippet = self._extract_code_around_smell(content, smell.line_range) if content else "(code unavailable)"

            # Truncate very long snippets to keep prompt manageable
            if len(code_snippet) > 800:
                code_snippet = code_snippet[:800] + "\n// ... truncated ..."

            entry = (
                f"--- Smell #{idx} ---\n"
                f"Type: {smell.smell_type}\n"
                f"File: {smell.file_path}\n"
                f"Location: {smell.location}\n"
                f"Line Range: {smell.line_range}\n"
                f"Severity: {smell.severity}\n"
                f"Description: {smell.description}\n"
                f"Code:\n```java\n{code_snippet}\n```\n"
            )
            smell_entries.append(entry)

        smells_data = "\n".join(smell_entries)
        return BATCH_REFACTORING_PROMPT.format(smells_data=smells_data)

    def _parse_batch_response(
        self, response_text: str, smells: list[DesignSmell]
    ) -> list[RefactoringSuggestion]:
        """
        Parse the batch JSON response into RefactoringSuggestion objects.

        Args:
            response_text: Raw response from the LLM.
            smells: The original list of smells (used to link suggestions back).

        Returns:
            List of RefactoringSuggestion objects.
        """
        suggestions = []

        # Clean response (remove markdown code blocks if present)
        cleaned = response_text.strip()
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:]
        if cleaned.startswith('```'):
            cleaned = cleaned[3:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            result = json.loads(cleaned)
        except json.JSONDecodeError as e:
            print(f"   Failed to parse batch LLM response as JSON: {e}")
            return suggestions

        for suggestion_data in result.get("suggestions", []):
            smell_idx = suggestion_data.get("smell_index", -1)
            if smell_idx < 0 or smell_idx >= len(smells):
                # Try to match by position in the array instead
                smell_idx = len(suggestions)
                if smell_idx >= len(smells):
                    continue

            smell = smells[smell_idx]
            content = self._read_file_content(smell.file_path)
            original_snippet = self._extract_code_around_smell(content, smell.line_range) if content else ""

            suggestions.append(RefactoringSuggestion(
                smell=smell,
                technique=suggestion_data.get("refactoring_technique", suggestion_data.get("technique", "Unknown")),
                explanation=suggestion_data.get("explanation", ""),
                original_code=original_snippet[:500],
                suggested_code=suggestion_data.get("suggested_code", ""),
                changes_summary=suggestion_data.get("changes_summary", []),
                benefits=suggestion_data.get("benefits", []),
                risks=suggestion_data.get("potential_risks", suggestion_data.get("risks", []))
            ))

        return suggestions

    def generate_suggestions(
        self,
        smells: list[DesignSmell],
        max_suggestions: int = 10
    ) -> list[RefactoringSuggestion]:
        """
        Generate refactoring suggestions for detected smells using a SINGLE
        batch API call.
        
        Args:
            smells: List of detected design smells
            max_suggestions: Maximum number of suggestions to generate
            
        Returns:
            List of refactoring suggestions
        """
        print(f"\n🔧 Generating refactoring suggestions (batch mode)...")
        print(f"   Processing up to {max_suggestions} smells out of {len(smells)} detected...")
        
        # Prioritize by severity
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        sorted_smells = sorted(smells, key=lambda s: priority_order.get(s.severity, 3))
        
        # Limit to max_suggestions
        smells_to_process = sorted_smells[:max_suggestions]
        
        if not smells_to_process:
            print("   No smells to process.")
            return self.suggestions

        # Build a single batch prompt
        print(f"   Building batch prompt for {len(smells_to_process)} smells...")
        prompt = self._build_batch_prompt(smells_to_process)
        
        # Make ONE API call
        print(f"   Sending single batch request to Gemini API...")
        response_text = self._call_gemini_api(prompt)
        
        if not response_text:
            print("   ✗ Batch API call returned no response.")
            return self.suggestions
        
        # Parse all suggestions from the single response
        print(f"   Parsing batch response...")
        self.suggestions = self._parse_batch_response(response_text, smells_to_process)
        
        print(f"\n   ✓ Generated {len(self.suggestions)} refactoring suggestions in a single API call.")
        
        if self.suggestions:
            for s in self.suggestions:
                print(f"     - {s.technique} for {s.smell.location} ({s.smell.smell_type})")
        
        return self.suggestions

    def get_suggestions_summary(self) -> dict:
        """Get a summary of all suggestions."""
        techniques = {}
        for suggestion in self.suggestions:
            technique = suggestion.technique
            if technique not in techniques:
                techniques[technique] = 0
            techniques[technique] += 1
        
        return {
            "total_suggestions": len(self.suggestions),
            "techniques_used": techniques,
            "files_affected": len(set(s.smell.file_path for s in self.suggestions))
        }

