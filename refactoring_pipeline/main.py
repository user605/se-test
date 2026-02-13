"""
Main Orchestrator for the Automated Refactoring Pipeline.

This is the entry point that coordinates:
1. Design smell detection
2. LLM-based refactoring suggestions
3. Documentation generation
4. PR creation
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from detector import DesignSmellDetector
from refactorer import LLMRefactorer
from pr_generator import PRGenerator
from config import GEMINI_API_KEY, GITHUB_TOKEN


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Automated Refactoring Pipeline using LLMs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full pipeline
  python main.py --repo-path /path/to/repo

  # Dry run (no PR creation)
  python main.py --repo-path /path/to/repo --dry-run

  # Static analysis only (no LLM)
  python main.py --repo-path /path/to/repo --no-llm

  # Limit suggestions
  python main.py --repo-path /path/to/repo --max-suggestions 5
        """
    )
    
    parser.add_argument(
        "--repo-path",
        type=str,
        default=".",
        help="Path to the repository to analyze (default: current directory)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate documentation but don't create PR"
    )
    
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM-based analysis (static analysis only)"
    )
    
    parser.add_argument(
        "--max-suggestions",
        type=int,
        default=10,
        help="Maximum number of refactoring suggestions to generate (default: 10)"
    )
    
    parser.add_argument(
        "--scan-path",
        type=str,
        default=None,
        help="Subdirectory to scan (relative to repo root), e.g. 'app/src/main/java/com/mypackage'"
    )
    
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Maximum number of Java files to analyze (default: all)"
    )
    
    parser.add_argument(
        "--output-json",
        type=str,
        default=None,
        help="Path to save JSON results (optional)"
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    return parser.parse_args()


def check_requirements(use_llm: bool, dry_run: bool) -> bool:
    """Check if required credentials are available."""
    issues = []
    
    if use_llm and not GEMINI_API_KEY:
        issues.append("GEMINI_API_KEY not set (required for LLM analysis)")
    
    if not dry_run and not GITHUB_TOKEN:
        issues.append("GITHUB_TOKEN not set (required for PR creation)")
    
    if issues:
        print("⚠️  Configuration Issues:")
        for issue in issues:
            print(f"   - {issue}")
        print("\nSet environment variables or use .env file.")
        return False
    
    return True


def run_pipeline(args) -> dict:
    """Run the complete refactoring pipeline."""
    results = {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "repo_path": args.repo_path,
        "smells": [],
        "suggestions": [],
        "documentation_path": None,
        "pr_url": None,
        "errors": [],
    }
    
    repo_path = Path(args.repo_path).resolve()
    
    if not repo_path.exists():
        results["status"] = "error"
        results["errors"].append(f"Repository path not found: {repo_path}")
        return results
    
    print(f"\n{'='*60}")
    print(f"🔧 AUTOMATED REFACTORING PIPELINE")
    print(f"{'='*60}")
    print(f"Repository: {repo_path}")
    if args.scan_path:
        print(f"Scan Path: {args.scan_path}")
    if args.max_files:
        print(f"Max Files: {args.max_files}")
    print(f"LLM Analysis: {'Enabled' if not args.no_llm else 'Disabled'}")
    print(f"Dry Run: {'Yes' if args.dry_run else 'No'}")
    print(f"{'='*60}\n")
    
    # Step 1: Detect design smells (always static analysis for detection)
    # LLM is used only in Step 2 for generating refactoring suggestions
    print("📍 Step 1: Detecting Design Smells (Static Analysis)...")
    try:
        detector = DesignSmellDetector(
            str(repo_path),
            use_llm=False,
            scan_path=args.scan_path,
            max_files=args.max_files,
        )
        smells, metrics = detector.scan_repository()
        results["smells"] = detector.get_results_as_dict()
        print(f"   ✓ Found {len(smells)} design smells in {len(metrics)} files")
        
        if args.verbose:
            for smell in smells[:5]:
                print(f"     - [{smell.severity}] {smell.smell_type}: {smell.location}")
            if len(smells) > 5:
                print(f"     ... and {len(smells) - 5} more")
    except Exception as e:
        results["errors"].append(f"Detection error: {str(e)}")
        print(f"   ✗ Detection failed: {e}")
        smells, metrics = [], []
    
    # Step 2: Generate refactoring suggestions
    suggestions = []
    if smells and not args.no_llm and GEMINI_API_KEY:
        print("\n📍 Step 2: Generating Refactoring Suggestions...")
        try:
            refactorer = LLMRefactorer(str(repo_path))
            suggestions = refactorer.generate_suggestions(smells, max_suggestions=args.max_suggestions)
            results["suggestions"] = refactorer.get_suggestions_summary()
            print(f"   ✓ Generated {len(suggestions)} refactoring suggestions")
            
            if args.verbose:
                for suggestion in suggestions[:3]:
                    print(f"     - {suggestion.technique} for {suggestion.smell.location}")
        except Exception as e:
            results["errors"].append(f"Refactoring error: {str(e)}")
            print(f"   ✗ Suggestion generation failed: {e}")
    elif args.no_llm:
        print("\n📍 Step 2: Skipping LLM suggestions (--no-llm flag)")
    else:
        print("\n📍 Step 2: Skipping suggestions (no smells found or no API key)")
    
    # Step 3: Generate documentation
    print("\n📍 Step 3: Generating Documentation...")
    try:
        pr_gen = PRGenerator(str(repo_path))
        doc_path = pr_gen.generate_documentation(smells, suggestions, metrics)
        results["documentation_path"] = doc_path
        print(f"   ✓ Documentation saved to: {doc_path}")
    except Exception as e:
        results["errors"].append(f"Documentation error: {str(e)}")
        print(f"   ✗ Documentation generation failed: {e}")
        doc_path = None
    
    # Step 4: Create PR (unless dry run)
    if not args.dry_run and doc_path:
        print("\n📍 Step 4: Creating Pull Request...")
        try:
            pr_result = pr_gen.create_pull_request(doc_path, smells, suggestions)
            results["pr_url"] = pr_result
            print(f"   ✓ PR: {pr_result}")
        except Exception as e:
            results["errors"].append(f"PR creation error: {str(e)}")
            print(f"   ✗ PR creation failed: {e}")
    elif args.dry_run:
        print("\n📍 Step 4: Skipping PR creation (dry run)")
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 SUMMARY")
    print(f"{'='*60}")
    print(f"Files analyzed: {len(metrics)}")
    print(f"Design smells found: {len(smells)}")
    print(f"  - HIGH severity: {len([s for s in smells if s.severity == 'HIGH'])}")
    print(f"  - MEDIUM severity: {len([s for s in smells if s.severity == 'MEDIUM'])}")
    print(f"  - LOW severity: {len([s for s in smells if s.severity == 'LOW'])}")
    print(f"Refactoring suggestions: {len(suggestions)}")
    
    if results["errors"]:
        print(f"\n⚠️  Errors encountered: {len(results['errors'])}")
        results["status"] = "partial_success" if results["documentation_path"] else "error"
    
    print(f"{'='*60}\n")
    
    return results


def main():
    """Main entry point."""
    args = parse_args()
    
    # Check requirements
    use_llm = not args.no_llm
    if not check_requirements(use_llm, args.dry_run):
        if not args.dry_run:
            print("\nTip: Use --dry-run to generate documentation without creating a PR")
        if use_llm:
            print("Tip: Use --no-llm to run static analysis only")
        sys.exit(1)
    
    # Run pipeline
    results = run_pipeline(args)
    
    # Save JSON results if requested
    if args.output_json:
        with open(args.output_json, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"Results saved to: {args.output_json}")
    
    # Exit with appropriate code
    if results["status"] == "error":
        sys.exit(1)
    elif results["status"] == "partial_success":
        sys.exit(0)  # Still exit 0 for CI compatibility
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
