"""Interactive model selection — per-category input like v1."""

import json
import os
from collections import defaultdict

from huggingface_hub import HfApi

from . import config
from .ui import Color


def fetch_and_categorize(repo_id, repo_type, base_dir, auth_token):
    """Fetch file list from HF and categorize by prefix."""
    api = HfApi()
    print(f"\n  {Color.OKBLUE}🔍 Fetching files from {repo_id} ({repo_type})...{Color.ENDC}")
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
                categorized[prefix].append({
                    "url": f"{url_prefix}/resolve/main/{f}",
                    "dest_dir": dest,
                    "filename": os.path.basename(f),
                })
                break

    return categorized


def display_tree(categorized):
    """Display file tree with numbers."""
    print(f"\n  {Color.BOLD}{Color.OKCYAN}📂 Available models:{Color.ENDC}\n")

    counter = 1
    cat_indexes = {}

    for cat in config.CATEGORIES:
        items = categorized.get(cat, [])
        if not items:
            continue
        print(f"  📁 {cat}/ ({len(items)} files)")
        cat_start = counter
        for item in items:
            print(f"     [{Color.OKGREEN}{counter:2d}{Color.ENDC}] {item['filename']}")
            counter += 1
        cat_indexes[cat] = list(range(cat_start, counter))
        print()

    return cat_indexes


def interactive_select(categorized, cat_indexes):
    """Per-category interactive selection. Empty = all."""
    print(f"  {'─'*50}")
    print(f"  📥 SELECT MODELS TO DOWNLOAD")
    print(f"  {'─'*50}\n")
    print(f"  For each category, enter file numbers (comma separated)")
    print(f"  or leave blank to download ALL in that category.\n")

    filtered = []

    for cat in config.CATEGORIES:
        idx_list = cat_indexes.get(cat, [])
        if not idx_list:
            continue

        items = categorized[cat]
        idx_str = ",".join(map(str, idx_list))
        user_input = input(f"  {cat} ({len(idx_list)} files): {idx_str}\n  → Select files (blank=all): ").strip()

        if user_input == "":
            # All files in this category
            filtered.extend(items)
        else:
            try:
                picks = [int(x.strip()) for x in user_input.split(",")]
                for pick in picks:
                    if pick in idx_list:
                        # Find the item by index
                        cat_items = categorized[cat]
                        cat_start = idx_list[0]
                        item_idx = pick - cat_start
                        if 0 <= item_idx < len(cat_items):
                            filtered.append(cat_items[item_idx])
                    else:
                        print(f"    {Color.WARNING}⚠️  {pick} not in {cat}, skipped{Color.ENDC}")
            except ValueError:
                print(f"    {Color.WARNING}⚠️  Invalid input, selecting all {cat}{Color.ENDC}")
                filtered.extend(items)

        print()

    return filtered


def run_selection(repo_id=None, repo_type=None, base_dir=None, auth_token=None):
    """Run full selection flow: fetch → display → select → save."""
    repo_id = repo_id or config.DEFAULT_REPO_ID
    repo_type = repo_type or config.DEFAULT_REPO_TYPE
    base_dir = base_dir or os.path.join(config.WORKSPACE, "ComfyUI", "models")

    categorized = fetch_and_categorize(repo_id, repo_type, base_dir, auth_token)
    cat_indexes = display_tree(categorized)
    filtered = interactive_select(categorized, cat_indexes)

    # Save download list
    download_file = config.DOWNLOAD_LIST_FILE
    with open(download_file, "w") as f:
        json.dump(filtered, f, indent=2)

    total = len(filtered)
    print(f"  {Color.OKGREEN}✅ {total} files selected → saved to {download_file}{Color.ENDC}")
    return filtered
