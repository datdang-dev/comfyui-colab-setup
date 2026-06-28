"""Model downloading with hf_transfer (preferred) and progress display."""

import concurrent.futures
import json
import os
import time

from . import config
from .ui import Color, get_logger, run_cmd, timer


def download_one(item, auth_token):
    """Download a single file via hf_hub_download."""
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
    """Download all files in download_list with progress display and timing."""
    log = get_logger()
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
        log.info(f"  Skipping {skipped} existing files")

    if not to_download:
        log.info(f"  {Color.OKGREEN}All {len(download_list)} files already downloaded.{Color.ENDC}")
        return {"ok": len(download_list), "fail": 0, "skipped": skipped}

    log.info(f"  Downloading {len(to_download)} files ({parallel} parallel)...")

    # Enable hf_transfer for faster downloads
    run_cmd("pip install hf_transfer -q", quiet=True)
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

    ok = 0
    fail = 0
    total = len(to_download)

    def dl_with_log(item):
        nonlocal ok, fail
        fname = item["filename"]
        try:
            with timer() as t:
                download_one(item, auth_token)
            ok += 1
            # Estimate throughput: count successful per wall time
            elapsed = time.time() - start_time
            speed = ok / elapsed if elapsed > 0 else 0
            eta = (total - ok - fail) / speed if speed > 0 else 0
            log.info(
                f"  [{ok + fail:3d}/{total}] {Color.OKGREEN}✓{Color.ENDC} {fname}  "
                f"({t.elapsed:.1f}s, {speed:.1f}/s, ETA {int(eta)}s)"
            )
        except Exception as e:
            fail += 1
            log.error(f"  [{ok + fail:3d}/{total}] {Color.FAIL}✗{Color.ENDC} {fname}: {e}")

    with timer() as total_timer:
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel) as pool:
            list(pool.map(dl_with_log, to_download))

    log.info("")
    if fail == 0:
        log.info(
            f"  {Color.OKGREEN}Done: {ok} files in {total_timer.elapsed:.0f}s "
            f"({total_timer.elapsed / 60:.1f}min){Color.ENDC}"
        )
    else:
        log.info(
            f"  {Color.WARNING}Done: {ok} ok, {fail} failed in {total_timer.elapsed:.0f}s{Color.ENDC}"
        )

    return {"ok": ok, "fail": fail, "skipped": skipped}


def load_and_download(download_list_file=None, auth_token=None, max_parallel=None):
    """Load download list from file and execute download."""
    log = get_logger()
    dl_file = download_list_file or config.DOWNLOAD_LIST_FILE

    if not os.path.exists(dl_file):
        # Generate default list from config.yaml if it doesn't exist
        default_models = config.get_default_models()
        if default_models:
            log.info(f"Writing default models from config.yaml to {dl_file}...")
            try:
                with open(dl_file, "w") as f:
                    json.dump(default_models, f, indent=2)
            except Exception as e:
                log.warning(f"Failed to write default download list: {e}")
        else:
            log.warning(f"No download list found at {dl_file} and no default models in config.yaml.")
            return {"ok": 0, "fail": 0, "skipped": 0}

    import yaml
    try:
        with open(dl_file, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)
    except Exception as e:
        log.error(f"Failed to parse download_list.yaml: {e}")
        return {"ok": 0, "fail": 0, "skipped": 0}

    # Flatten grouped list if structured as a dictionary
    download_list = []
    if isinstance(raw_data, list):
        download_list = raw_data
    elif isinstance(raw_data, dict):
        for val in raw_data.values():
            if isinstance(val, list):
                download_list.extend(val)

    if not download_list:
        log.info("  No active models to download in download_list.yaml.")
        return {"ok": 0, "fail": 0, "skipped": 0}

    return download_all(download_list, auth_token, max_parallel)
