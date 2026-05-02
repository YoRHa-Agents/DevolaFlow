"""Writing-style benchmark harness.

Measures naturalness of DevolaFlow's human-facing corpus against a
``human-clean`` reference corpus (chezmoi/ruff/caveman/ironclaw
READMEs). Outputs JSON baselines consumed by
``tests/test_writing_style_benchmark_regression.py``.

Usage:

  python -m benchmarks.writing_style.runner \\
      --corpus devolaflow \\
      --output benchmarks/writing_style/baselines/v10.1.0_pre.json
"""
