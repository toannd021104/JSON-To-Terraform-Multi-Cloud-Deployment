#!/usr/bin/env python3
"""
Quick deployment test script
Simple wrapper for testing deployments quickly
"""

import sys
import subprocess
from pathlib import Path


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 quick_test.py <provider> <num_copies>")
        print("Example: python3 quick_test.py aws 2")
        sys.exit(1)

    provider = sys.argv[1]
    num_copies = sys.argv[2]

    print("=" * 70)
    print(f"Quick Test: {provider.upper()} with {num_copies} copies")
    print("=" * 70)

    # Run benchmark with auto-cleanup and prompt at the end
    benchmark_path = Path(__file__).parent.parent / "utils" / "benchmark_deployment.py"
    cmd = ["python3", str(benchmark_path), provider, num_copies]

    subprocess.run(cmd)


if __name__ == "__main__":
    main()
