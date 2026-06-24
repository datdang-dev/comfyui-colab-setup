#!/usr/bin/env python3
"""
ComfyUI Colab Setup — CLI entry point.
======================================
Thin wrapper around comfyui_setup.main. All logic lives in the package.

Usage:
    python install.py --hf-token=YOUR_TOKEN
    python install.py --hf-token=YOUR_TOKEN --use-prebuilt
    python install.py --skip-nodes --skip-select --repo-id=datsss/my-dataset
"""

import os
import sys
from pathlib import Path

# Ensure comfyui_setup package is importable
_PROJECT_ROOT = str(Path(__file__).parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from comfyui_setup import config
from comfyui_setup.main import parse_args, _run
from comfyui_setup.ui import setup_logging


def main():
    args = parse_args()

    # Init logging with file handler so terminal disconnect doesn't lose output
    setup_logging(log_file=str(config.LOG_FILE))

    _run(
        hf_token=args.hf_token,
        repo_id=args.repo_id,
        repo_type=args.repo_type,
        max_parallel=args.max_parallel,
        workspace=args.workspace,
        custom_nodes=args.custom_nodes,
        use_prebuilt=args.use_prebuilt,
        env_repo=args.env_repo,
        skip_nodes=args.skip_nodes,
        skip_select=args.skip_select,
        skip_download=args.skip_download,
    )


if __name__ == "__main__":
    main()
