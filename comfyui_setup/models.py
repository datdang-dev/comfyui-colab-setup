"""Model downloading with hf_transfer (preferred) or aria2c (fallback)."""

import concurrent.futures
import json
import os
import time

from . import config
from .ui import Color, run_cmd


def download_one(item, auth_token):
    """Download single file via hf_transfer."""
    from huggingface_hub import hf_hub_download

    url = item["url"]
    if "/datasets/" in url:
        repo_part = url.split("/datasets/")[1].split("/resolve/")[0]
        repo_type = "dataset"
    else:
        repo_part = url.split("huggingface.co/")[1].split("/resolve/")[0]
        repo_type = "model"

    file_path = url.split("/resolve/main/")[1]
    return hf_hub_download(
        repo_id=repo_part,
        filename=file_path,
        repo_type=repo_type,
        token=auth_token,
        local_dir=item["dest_dir"],
    )


def download_all(download_list, auth_token, max_parallel=None):
    """Download all files in download_list with progress display."""
    parallel = max_parallel or config.MAX_DOWNLOAD_PARALLEL

    # Pre-check: skip existing
    to_download = []
    skipped = 0
    for item in download_list:
        dest = os.path.join(item["dest_dir"], item["filename"])
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            skipped += 1
        else:
            os.makedirs(item["dest_dir"], exist_ok=True)
            to_download.append(item)

    if skipped:
        print(f"  ⏭️  Skipping {skipped} existing files")

    if not to_download:
        print(f"  {Color.OKGREEN}✅ All {len(download_list)} files already downloaded!{Color.ENDC}")
        return {"ok": len(download_list), "fail": 0, "skipped": skipped}

    print(f"  🚀 Downloading {len(to_download)} files ({parallel} parallel)...\n")

    # Install hf_transfer
    run_cmd("pip install hf_transfer -q", quiet=True)
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

    ok = 0
    fail = 0
    total = len(to_download)
    start_time = time.time()

    def dl_with_log(item):
        nonlocal ok, fail
        fname = item["filename"]
        try:
            download_one(item, auth_token)
            ok += 1
            elapsed = time.time() - start_time
            speed = ok / elapsed if elapsed > 0 else 0
            eta = (total - ok - fail) / speed if speed > 0 else 0
            print(
                f"  [{ok+fail:3d}/{total}] {Color.OKGREEN}✓{Color.ENDC} {fname}  "
                f"({speed:.1f}/s, ETA {int(eta)}s)"
            )
        except Exception as e:
            fail += 1
            print(f"  [{ok+fail:3d}/{total}] {Color.FAIL}✗{Color.ENDC} {fname}: {e}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as pool:
        list(pool.map(dl_with_log, to_download))

    elapsed = time.time() - start_time
    print(f"\n  {'─'*50}")
    if fail == 0:
        print(
            f"  {Color.OKGREEN}✅ Done: {ok} files in {elapsed:.1f}s ({elapsed/60:.1f}min){Color.ENDC}"
        )
    else:
        print(
            f"  {Color.WARNING}⚠️  Done: {ok} ok, {fail} failed in {elapsed:.1f}s{Color.ENDC}"
        )

    return {"ok": ok, "fail": fail, "skipped": skipped}


def load_and_download(download_list_file=None, auth_token=None, max_parallel=None):
    """Load download list from file and download."""
    dl_file = download_list_file or config.DOWNLOAD_LIST_FILE

    if not os.path.exists(dl_file):
        print(f"  {Color.WARNING}⚠️  No download list found. Run selection first.{Color.ENDC}")
        return {"ok": 0, "fail": 0, "skipped": 0}

    with open(dl_file) as f:
        download_list = json.load(f)

    if not download_list:
        print(f"  ℹ️  No files to download.")
        return {"ok": 0, "fail": 0, "skipped": 0}

    return download_all(download_list, auth_token, max_parallel)
