"""
Design Smell Detection Module for the Automated Refactoring Pipeline.

This module scans Java files and detects common design smells using:
1. Static analysis (AST parsing with javalang)
2. LLM-based detection (Gemini API)
"""
import os
import re
import json
import fnmatch
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

import javalang
import google.generativeai as genai

from config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    TARGET_EXTENSIONS,
    EXCLUDE_PATTERNS,
    SMELL_THRESHOLDS,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    TEMPERATURE,
    MAX_TOKENS,
)
from prompts import SMELL_DETECTION_PROMPT, CHUNK_CONTEXT_HEADER


@dataclass
class DesignSmell:
    """Represents a detected design smell."""
    smell_type: str
    file_path: str
    location: str
    line_range: str
    severity: str  # LOW, MEDIUM, HIGH
    description: str
    detection_method: str  # "static" or "llm"


@dataclass
class FileMetrics:
    """Metrics for a Java file."""
    file_path: str
    total_lines: int
    method_count: int
    field_count: int
    class_count: int
    max_method_length: int
    max_parameter_count: int


class DesignSmellDetector:
    """Detects design smells in Java code using static analysis and LLM."""

    def __init__(self, repo_path: str, use_llm: bool = True, scan_path: str = None, max_files: int = None):
        """
        Initialize the detector.
        
        Args:
            repo_path: Path to the repository root
            use_llm: Whether to use LLM for additional detection
            scan_path: Optional subdirectory to scan (relative to repo root)
            max_files: Optional maximum number of files to analyze
        """
        self.repo_path = Path(repo_path)
        self.scan_path = scan_path
        self.max_files = max_files
        self.use_llm = use_llm
        self.smells: list[DesignSmell] = []
        self.metrics: list[FileMetrics] = []
        
        if use_llm and GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel(GEMINI_MODEL)
        else:
            self.model = None

    def _call_gemini_api(self, prompt: str) -> Optional[str]:
        """Call the Gemini API with a prompt and return the response text with rate limiting."""
        if not self.model:
            return None
        
        max_retries = 3
        base_delay = 5  # seconds
        
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

    def scan_repository(self) -> tuple[list[DesignSmell], list[FileMetrics]]:
        """
        Scan the repository for Java files and detect design smells.
        
        Returns:
            Tuple of (list of detected smells, list of file metrics)
        """
        java_files = self._find_java_files()
        print(f"Found {len(java_files)} Java files to analyze")

        for file_path in java_files:
            try:
                self._analyze_file(file_path)
            except Exception as e:
                print(f"Error analyzing {file_path}: {e}")

        return self.smells, self.metrics

    def _find_java_files(self) -> list[Path]:
        """Find all Java files that match the target criteria."""
        java_files = []
        
        # Determine the root directory to scan
        scan_root = self.repo_path
        if self.scan_path:
            scan_root = self.repo_path / self.scan_path
            if not scan_root.exists():
                print(f"⚠️  Scan path not found: {scan_root}")
                return []
            print(f"   Scanning subdirectory: {self.scan_path}")
        
        for ext in TARGET_EXTENSIONS:
            for file_path in scan_root.rglob(f"*{ext}"):
                if not self._is_excluded(file_path):
                    java_files.append(file_path)

        java_files = sorted(java_files)
        
        # Limit number of files if specified
        if self.max_files and len(java_files) > self.max_files:
            print(f"   Limiting analysis to {self.max_files} of {len(java_files)} files")
            java_files = java_files[:self.max_files]
        
        return java_files

    def _is_excluded(self, file_path: Path) -> bool:
        """Check if a file should be excluded based on patterns."""
        rel_path = str(file_path.relative_to(self.repo_path))
        
        for pattern in EXCLUDE_PATTERNS:
            if fnmatch.fnmatch(rel_path, pattern):
                return True
            if fnmatch.fnmatch(file_path.name, pattern):
                return True
        
        return False

    def _analyze_file(self, file_path: Path) -> None:
        """Analyze a single Java file for design smells."""
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            lines = content.split("\n")

        # Static analysis
        static_smells, metrics = self._static_analysis(file_path, content, lines)
        self.smells.extend(static_smells)
        if metrics:
            self.metrics.append(metrics)

        # LLM-based analysis for files with potential issues
        if self.use_llm and self.model and self._should_analyze_with_llm(metrics):
            llm_smells = self._llm_analysis(file_path, content, lines)
            self.smells.extend(llm_smells)

    def _static_analysis(
        self, file_path: Path, content: str, lines: list[str]
    ) -> tuple[list[DesignSmell], Optional[FileMetrics]]:
        """Perform static analysis using javalang AST parsing."""
        smells = []
        rel_path = str(file_path.relative_to(self.repo_path))

        try:
            tree = javalang.parse.parse(content)
        except javalang.parser.JavaSyntaxError:
            return smells, None

        # Collect metrics
        method_count = 0
        field_count = 0
        class_count = 0
        max_method_length = 0
        max_param_count = 0

        for path, node in tree:
            # Count classes
            if isinstance(node, javalang.tree.ClassDeclaration):
                class_count += 1
                class_methods = len([m for m in (node.methods or [])])
                class_fields = len([f for f in (node.fields or [])])

                # Detect God Class
                thresholds = SMELL_THRESHOLDS["god_class"]
                if (class_methods > thresholds["max_methods"] or 
                    class_fields > thresholds["max_fields"]):
                    smells.append(DesignSmell(
                        smell_type="God Class",
                        file_path=rel_path,
                        location=node.name,
                        line_range=f"{node.position.line if node.position else '?'}",
                        severity="HIGH" if class_methods > thresholds["max_methods"] * 1.5 else "MEDIUM",
                        description=f"Class has {class_methods} methods and {class_fields} fields. "
                                    f"Consider splitting into smaller, focused classes.",
                        detection_method="static"
                    ))

                method_count += class_methods
                field_count += class_fields

            # Analyze methods
            if isinstance(node, javalang.tree.MethodDeclaration):
                params = node.parameters or []
                param_count = len(params)
                max_param_count = max(max_param_count, param_count)

                # Detect Long Parameter List
                if param_count > SMELL_THRESHOLDS["long_parameter_list"]["max_params"]:
                    smells.append(DesignSmell(
                        smell_type="Long Parameter List",
                        file_path=rel_path,
                        location=f"{node.name}()",
                        line_range=f"{node.position.line if node.position else '?'}",
                        severity="MEDIUM",
                        description=f"Method has {param_count} parameters. "
                                    f"Consider using a Parameter Object pattern.",
                        detection_method="static"
                    ))

                # Estimate method length (rough approximation)
                if node.body:
                    method_lines = len(node.body)
                    max_method_length = max(max_method_length, method_lines)

        # Check for Large Class (by line count)
        total_lines = len(lines)
        if total_lines > SMELL_THRESHOLDS["large_class"]["max_lines"]:
            smells.append(DesignSmell(
                smell_type="Large Class",
                file_path=rel_path,
                location=file_path.stem,
                line_range=f"1-{total_lines}",
                severity="MEDIUM" if total_lines < 500 else "HIGH",
                description=f"File has {total_lines} lines. Consider breaking into smaller classes.",
                detection_method="static"
            ))

        metrics = FileMetrics(
            file_path=rel_path,
            total_lines=total_lines,
            method_count=method_count,
            field_count=field_count,
            class_count=class_count,
            max_method_length=max_method_length,
            max_parameter_count=max_param_count,
        )

        return smells, metrics

    def _should_analyze_with_llm(self, metrics: Optional[FileMetrics]) -> bool:
        """Determine if LLM analysis should be performed based on metrics."""
        if not metrics:
            return False
        
        # Analyze files that are large or have many methods
        return (
            metrics.total_lines > 100 or
            metrics.method_count > 5 or
            metrics.max_parameter_count > 3
        )

    def _llm_analysis(
        self, file_path: Path, content: str, lines: list[str]
    ) -> list[DesignSmell]:
        """Perform LLM-based analysis for deeper smell detection."""
        smells = []
        rel_path = str(file_path.relative_to(self.repo_path))

        # Handle large files by chunking
        if len(lines) > CHUNK_SIZE:
            chunks = self._create_chunks(content, lines, file_path)
            for chunk_info, chunk_content in chunks:
                smells.extend(self._analyze_with_llm(rel_path, chunk_content, chunk_info))
        else:
            smells.extend(self._analyze_with_llm(rel_path, content, ""))

        return smells

    def _create_chunks(
        self, content: str, lines: list[str], file_path: Path
    ) -> list[tuple[str, str]]:
        """Create overlapping chunks from a large file with context."""
        chunks = []
        
        # Extract context information
        package = ""
        imports = []
        class_signature = ""
        
        for line in lines[:50]:  # Check first 50 lines for structure
            if line.strip().startswith("package "):
                package = line.strip()
            elif line.strip().startswith("import "):
                imports.append(line.strip().split()[-1].rstrip(";"))
            elif "class " in line and not line.strip().startswith("//"):
                class_signature = line.strip()
                break

        import_summary = f"{len(imports)} imports" if imports else "no imports"
        
        total_chunks = (len(lines) + CHUNK_SIZE - 1) // CHUNK_SIZE
        
        for i in range(0, len(lines), CHUNK_SIZE - CHUNK_OVERLAP):
            start_line = i + 1
            end_line = min(i + CHUNK_SIZE, len(lines))
            chunk_num = (i // (CHUNK_SIZE - CHUNK_OVERLAP)) + 1
            
            chunk_info = CHUNK_CONTEXT_HEADER.format(
                filename=file_path.name,
                chunk_num=chunk_num,
                total_chunks=total_chunks,
                start_line=start_line,
                end_line=end_line,
                package=package,
                import_summary=import_summary,
                class_signature=class_signature,
            )
            
            chunk_content = "\n".join(lines[i:i + CHUNK_SIZE])
            chunks.append((chunk_info, chunk_content))
            
            if end_line >= len(lines):
                break

        return chunks

    def _analyze_with_llm(
        self, file_path: str, code: str, chunk_info: str
    ) -> list[DesignSmell]:
        """Send code to LLM for analysis."""
        smells = []
        
        prompt = SMELL_DETECTION_PROMPT.format(
            code=code,
            filename=file_path,
            chunk_info=chunk_info,
        )

        try:
            response_text = self._call_gemini_api(prompt)
            
            if not response_text:
                return smells
            
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)
            
            result = json.loads(response_text)
            
            for smell_data in result.get("smells", []):
                smells.append(DesignSmell(
                    smell_type=smell_data.get("type", "Unknown"),
                    file_path=file_path,
                    location=smell_data.get("location", "Unknown"),
                    line_range=smell_data.get("line_range", "?"),
                    severity=smell_data.get("severity", "MEDIUM"),
                    description=smell_data.get("description", ""),
                    detection_method="llm"
                ))

        except Exception as e:
            print(f"LLM analysis error for {file_path}: {e}")

        return smells

    def get_results_as_dict(self) -> dict:
        """Return results as a dictionary for JSON serialization."""
        return {
            "smells": [asdict(s) for s in self.smells],
            "metrics": [asdict(m) for m in self.metrics],
            "summary": {
                "total_files": len(self.metrics),
                "total_smells": len(self.smells),
                "by_severity": {
                    "HIGH": len([s for s in self.smells if s.severity == "HIGH"]),
                    "MEDIUM": len([s for s in self.smells if s.severity == "MEDIUM"]),
                    "LOW": len([s for s in self.smells if s.severity == "LOW"]),
                },
                "by_type": self._count_by_type(),
            }
        }

    def _count_by_type(self) -> dict[str, int]:
        """Count smells by type."""
        counts = {}
        for smell in self.smells:
            counts[smell.smell_type] = counts.get(smell.smell_type, 0) + 1
        return counts


def main():
    """Main function for standalone testing."""
    import sys
    
    repo_path = sys.argv[1] if len(sys.argv) > 1 else "."
    use_llm = "--no-llm" not in sys.argv
    
    detector = DesignSmellDetector(repo_path, use_llm=use_llm)
    smells, metrics = detector.scan_repository()
    
    print(f"\n{'='*60}")
    print(f"DETECTION RESULTS")
    print(f"{'='*60}")
    print(f"Files analyzed: {len(metrics)}")
    print(f"Smells detected: {len(smells)}")
    
    if smells:
        print(f"\nTop Issues:")
        for smell in sorted(smells, key=lambda s: ("HIGH", "MEDIUM", "LOW").index(s.severity))[:10]:
            print(f"  [{smell.severity}] {smell.smell_type} in {smell.location} ({smell.file_path})")
    
    # Save results
    results = detector.get_results_as_dict()
    with open("detection_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to detection_results.json")


if __name__ == "__main__":
    main()
