"""Integration test package — bridge shape contract tests.

Pins the v10.8.0 D-C-2 contract: every external-plugin bridge surface has
a regression test asserting the production bridge code parses real
captured output from the upstream tool WITHOUT zeroing fields silently
(the v10.2.3 bridge defect class).

The tests in this package use CHECKED-IN fixtures under
``tests/integration/fixtures/`` — they do NOT require live network access
or installed plugin binaries. Per-PR pytest runs the full suite in
~3-5s with zero external dependency.

A separate weekly CI job at ``.github/workflows/bridge-fixture-refresh.yml``
re-captures fixtures from real plugin output and opens a draft PR if
drift is detected; the per-PR run always uses the committed fixtures.

External canonical URLs (S-7 compliance):
    * DevolaFlow: https://github.com/YoRHa-Agents/DevolaFlow
    * Si-Chip: https://github.com/YoRHa-Agents/Si-Chip
    * RTK: https://github.com/rtk-ai/rtk
    * ui-pro: https://github.com/YoRHa-Agents/ui-pro
"""
