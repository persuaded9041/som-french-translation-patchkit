# Generated reports

This directory is reserved for deterministic, on-demand review and audit outputs.
Reports are **not canonical inputs** and normal builds/checks must not depend on them.

Android-related reports default to `reports/android/`. Most report files are ignored by Git;
materialize them only when human inspection, diffing, or review is useful.

Canonical structural decisions belong under `recipes/`, not here.
