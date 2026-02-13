"""
Configuration module for the Automated Refactoring Pipeline.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# LLM Configuration (Gemini)
# =============================================================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"  # Latest flash model with separate quota
MAX_TOKENS = 65536
TEMPERATURE = 0.3


# =============================================================================
# Repository Configuration
# =============================================================================
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
REPO_OWNER = os.getenv("REPO_OWNER", "")
REPO_NAME = os.getenv("REPO_NAME", "")

# =============================================================================
# File Scanning Configuration
# =============================================================================
TARGET_EXTENSIONS = [".java"]
EXCLUDE_PATTERNS = [
    "**/test/**",
    "**/Test*.java",
    "**/*Test.java",
    "**/*Tests.java",
    "**/package-info.java",
]

# =============================================================================
# Design Smell Thresholds
# =============================================================================
SMELL_THRESHOLDS = {
    "god_class": {
        "max_methods": 15,
        "max_lines": 500,
        "max_fields": 10,
    },
    "long_method": {
        "max_lines": 50,
    },
    "long_parameter_list": {
        "max_params": 5,
    },
    "large_class": {
        "max_lines": 300,
    },
    "duplicate_code": {
        "similarity_threshold": 0.8,
    },
}

# =============================================================================
# Chunking Configuration (for large files)
# =============================================================================
CHUNK_SIZE = 500  # lines per chunk
CHUNK_OVERLAP = 50  # overlap lines for context

# =============================================================================
# Output Configuration
# =============================================================================
OUTPUT_FOLDER = "refactoring-suggestions"
BRANCH_PREFIX = "refactor/llm-suggestions"
