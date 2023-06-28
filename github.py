from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Iterator

# pip install python-dotenv
from dotenv import load_dotenv
import requests

from common_all import AnyDict, BranchInfo

load_dotenv()

HERE = Path(__file__).parent

GITHUB_PR_API = "https://api.github.com/repos/trezor/trezor-firmware/pulls"
GH_TOKEN = os.getenv("GITHUB_API_TOKEN")
GH_HEADERS = {"Authorization": f"token {GH_TOKEN}"} if GH_TOKEN else {}


def load_cache_file() -> AnyDict:
    return json.loads(CACHE_FILE.read_text())


def load_branches_cache() -> dict[str, BranchInfo]:
    cache_dict = load_cache_file()["branches"]
    return {key: BranchInfo.from_dict(value) for key, value in cache_dict.items()}


def load_metadata_cache() -> AnyDict:
    return load_cache_file()["metadata"]


def update_cache(cache_dict: dict[str, BranchInfo]) -> None:
    CACHE.update(cache_dict)
    json_writable_cache_dict = {key: value.to_dict() for key, value in CACHE.items()}
    content = {
        "branches": json_writable_cache_dict,
        "metadata": {
            "last_update_timestamp": int(datetime.now().timestamp()),
            "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    }
    CACHE_FILE.write_text(json.dumps(content, indent=2))


CACHE_FILE = HERE / "github_cache.json"
if not CACHE_FILE.exists():
    CACHE_FILE.write_text("{}")
CACHE: dict[str, BranchInfo] = load_branches_cache()


def get_commit_ts(commit_hash: str) -> int:
    res = requests.get(
        f"https://api.github.com/repos/trezor/trezor-firmware/commits/{commit_hash}",
        headers=GH_HEADERS,
    )
    res.raise_for_status()
    return int(
        datetime.fromisoformat(
            res.json()["commit"]["committer"]["date"].replace("Z", "")
        ).timestamp()
    )


def get_all_gh_pulls() -> list[AnyDict]:
    res = requests.get(GITHUB_PR_API, headers=GH_HEADERS)
    res.raise_for_status()
    return res.json()


def yield_recently_updated_gh_pr_branches() -> Iterator[BranchInfo]:
    for pr in get_all_gh_pulls():
        last_commit_sha = pr["head"]["sha"]
        branch_name = pr["head"]["ref"]
        print(f"Getting branch {branch_name}")

        # Skip when we already have this commit in cache (and pipeline is finished)
        if branch_name in CACHE:
            cache_info = CACHE[branch_name]
            if cache_info.last_commit_sha == last_commit_sha:
                still_running = False
                for job_info in cache_info.job_infos.values():
                    if job_info.status == "Running...":
                        still_running = True
                if not still_running:
                    print(f"Skipping, commit did not change - {last_commit_sha}")
                    continue

        # It can come from a fork - we do not have UI tests for it
        if branch_name == "master":
            print("Ignoring a fork")
            continue

        last_commit_timestamp = get_commit_ts(last_commit_sha)
        last_commit_datetime = datetime.fromtimestamp(last_commit_timestamp).strftime(
            "%Y-%m-%d %H:%M"
        )
        pull_request_number = pr["number"]
        pull_request_link = (
            f"https://github.com/trezor/trezor-firmware/pull/{pull_request_number}"
        )
        branch_link = f"https://github.com/trezor/trezor-firmware/tree/{branch_name}"

        yield BranchInfo(
            name=branch_name,
            branch_link=branch_link,
            pull_request_number=pull_request_number,
            pull_request_name=pr["title"],
            pull_request_link=pull_request_link,
            last_commit_sha=last_commit_sha,
            last_commit_timestamp=last_commit_timestamp,
            last_commit_datetime=last_commit_datetime,
            job_infos={},
        )
