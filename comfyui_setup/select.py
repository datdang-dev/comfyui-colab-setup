"""Interactive model selection — per-category input, saves download_list.json."""

import json
import os
from collections import defaultdict

from huggingface_hub import HfApi

from . import config
from .ui import Color, get_logger


def fetch_and_categorize(repo_id, repo_type, base_dir, auth_token):
    """Fetch file list from HF and categorize by prefix."""
    log = get_logger()
    api = HfApi()
    log.info(f"Fetching files from {repo_id} ({repo_type})...")
    all_files = api.list_repo_files(repo_id=repo_id, token=auth_token, repo_type=repo_type)

    # URL prefix
    url_prefix = (
        f"https://huggingface.co/datasets/{repo_id}"
        if repo_type == "dataset"
        else f"https://huggingface.co/{repo_id}"
    )

    # Build category map: prefix -> dest_dir
    cat_dirs = {}
    for prefix, dirname in config.CATEGORIES.items():
        cat_dirs[prefix] = os.path.join(base_dir, dirname)
        os.makedirs(cat_dirs[prefix], exist_ok=True)

    # Categorize files
    categorized = defaultdict(list)
    for f in all_files:
        f_lower = f.lower()
        for prefix, dest in cat_dirs.items():
            if f_lower.startswith(f"{prefix}/"):
                categorized[prefix].append(
                    {
                        "url": f"{url_prefix}/resolve/main/{f}",
                        "dest_dir": dest,
                        "filename": os.path.basename(f),
                    }
                )
                break

    return categorized


def display_tree(categorized):
    """Display file tree with numbers. Returns cat_indexes dict."""
    log = get_logger()
    log.info("")
    log.info(f"{Color.BOLD}{Color.OKCYAN}Available models:{Color.ENDC}")
    log.info("")

    counter = 1
    cat_indexes = {}

    for cat in config.CATEGORIES:
        items = categorized.get(cat, [])
        if not items:
            continue
        log.info(f"  {cat}/ ({len(items)} files)")
        cat_start = counter
        for item in items:
            log.info(f"     [{Color.OKGREEN}{counter:2d}{Color.ENDC}] {item['filename']}")
            counter += 1
        cat_indexes[cat] = list(range(cat_start, counter))
        log.info("")

    return cat_indexes


def interactive_select(categorized, cat_indexes):
    """Per-category interactive selection. Empty input = select ALL in that category."""
    log = get_logger()
    log.info(f"  {'─' * 50}")
    log.info(f"  SELECT MODELS TO DOWNLOAD")
    log.info(f"  {'─' * 50}")
    log.info("")
    log.info("  For each category, enter file numbers (comma separated)")
    log.info("  or leave blank to download ALL in that category.")
    log.info("")

    filtered = []

    for cat in config.CATEGORIES:
        idx_list = cat_indexes.get(cat, [])
        if not idx_list:
            continue

        items = categorized[cat]
        idx_str = ",".join(map(str, idx_list))
        user_input = input(f"  {cat} ({len(idx_list)} files): {idx_str}\n  → Select files (blank=all): ").strip()

        if user_input == "":
            filtered.extend(items)
        else:
            try:
                picks = [int(x.strip()) for x in user_input.split(",")]
                for pick in picks:
                    if pick in idx_list:
                        cat_items = categorized[cat]
                        cat_start = idx_list[0]
                        item_idx = pick - cat_start
                        if 0 <= item_idx < len(cat_items):
                            filtered.append(cat_items[item_idx])
                    else:
                        log.warning(f"    {pick} not in {cat}, skipped")
            except ValueError:
                log.warning(f"    Invalid input, selecting all {cat}")
                filtered.extend(items)

        log.info("")

    return filtered


def run_selection(repo_id=None, repo_type=None, base_dir=None, auth_token=None):
    """Run full selection flow: fetch → display → select → save."""
    log = get_logger()
    repo_id = repo_id or config.DEFAULT_REPO_ID
    repo_type = repo_type or config.DEFAULT_REPO_TYPE
    base_dir = base_dir or os.path.join(str(config.WORKSPACE), "ComfyUI", "models")

    categorized = fetch_and_categorize(repo_id, repo_type, base_dir, auth_token)
    cat_indexes = display_tree(categorized)
    filtered = interactive_select(categorized, cat_indexes)

    # Save download list
    download_file = config.DOWNLOAD_LIST_FILE
    with open(download_file, "w") as f:
        json.dump(filtered, f, indent=2)
