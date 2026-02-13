"""
LLM Prompt Templates for the Automated Refactoring Pipeline.
"""

# =============================================================================
# Design Smell Detection Prompts
# =============================================================================

SMELL_DETECTION_PROMPT = """You are an expert software engineer specializing in code quality and design patterns.

Analyze the following Java code for design smells. For each smell found, provide:
1. The type of smell
2. The location (class/method name)
3. Severity (LOW, MEDIUM, HIGH)
4. Brief explanation of why it's a problem

Common design smells to look for:
- **God Class**: Class doing too much, violating Single Responsibility Principle
- **Long Method**: Methods that are too long and complex
- **Feature Envy**: Methods using other class's data more than their own
- **Data Class**: Classes with only getters/setters, no behavior
- **Long Parameter List**: Methods with too many parameters
- **Primitive Obsession**: Overuse of primitives instead of small objects
- **Duplicate Code**: Similar code blocks that should be extracted
- **Shotgun Surgery**: Changes requiring modifications in many classes
- **Divergent Change**: One class modified for many different reasons

CODE TO ANALYZE:
```java
{code}
```

FILE: {filename}
{chunk_info}

Respond in JSON format:
{{
    "smells": [
        {{
            "type": "smell_type",
            "location": "class_or_method_name",
            "line_range": "start-end",
            "severity": "LOW|MEDIUM|HIGH",
            "description": "explanation"
        }}
    ],
    "metrics": {{
        "total_lines": number,
        "method_count": number,
        "field_count": number,
        "complexity_estimate": "LOW|MEDIUM|HIGH"
    }}
}}
"""

# =============================================================================
# Refactoring Suggestion Prompts
# =============================================================================

REFACTORING_PROMPT = """You are an expert software engineer. Given the following design smell in Java code, suggest a refactoring solution.

DESIGN SMELL:
- Type: {smell_type}
- File: {file_path}
- Location: {location}
- Line Range: {line_range}
- Severity: {severity}
- Description: {description}

ORIGINAL CODE:
```java
{original_code}
```

Provide a refactoring suggestion that:
1. Preserves the original functionality
2. Improves the design
3. Follows SOLID principles
4. Uses appropriate design patterns if applicable

Respond ONLY with valid JSON (no markdown, no extra text):
{{
    "refactoring_technique": "technique name (e.g., Extract Method, Extract Class)",
    "explanation": "why this refactoring helps",
    "suggested_code": "the refactored code",
    "changes_summary": [
        "list of specific changes made"
    ],
    "benefits": [
        "list of benefits from this refactoring"
    ],
    "potential_risks": [
        "any risks or considerations"
    ]
}}
"""

# =============================================================================
# Documentation Generation Prompts
# =============================================================================

DOCUMENTATION_PROMPT = """Generate a comprehensive markdown documentation for the following refactoring suggestions.

DETECTED SMELLS:
{smells_json}

REFACTORING SUGGESTIONS:
{refactorings_json}

Create a well-formatted markdown document that includes:
1. Executive summary
2. List of detected smells with severity
3. Detailed refactoring suggestions with before/after code
4. Metrics comparison (estimated)
5. Recommendations for implementation priority

Use proper markdown formatting with headers, code blocks, and tables where appropriate.
"""

# =============================================================================
# Batch Refactoring Prompt (all smells in one call)
# =============================================================================

BATCH_REFACTORING_PROMPT = """You are an expert software engineer. You are given a list of design smells detected in a Java codebase. For each smell, you are provided the smell metadata and the relevant code snippet.

Analyze ALL the smells below and provide a refactoring suggestion for EACH one. Your suggestions should:
1. Preserve the original functionality
2. Improve the design
3. Follow SOLID principles
4. Use appropriate design patterns if applicable

DESIGN SMELLS TO ADDRESS:
{smells_data}

Respond ONLY with valid JSON (no markdown, no extra text). Return a JSON object with a "suggestions" array containing one entry per smell:
{{
    "suggestions": [
        {{
            "smell_index": 0,
            "refactoring_technique": "technique name (e.g., Extract Method, Extract Class)",
            "explanation": "why this refactoring helps",
            "suggested_code": "the refactored code",
            "changes_summary": [
                "list of specific changes made"
            ],
            "benefits": [
                "list of benefits from this refactoring"
            ],
            "potential_risks": [
                "any risks or considerations"
            ]
        }}
    ]
}}
"""

# =============================================================================
# Chunk Context Prompt
# =============================================================================

CHUNK_CONTEXT_HEADER = """// FILE: {filename}
// CHUNK: {chunk_num}/{total_chunks} (Lines {start_line}-{end_line})
// CONTEXT: This is part of a larger file. Key structural elements:
// Package: {package}
// Imports: {import_summary}
// Class: {class_signature}
// ---
"""
