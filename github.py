from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Iterator

import requests

# pip install python-dotenv
from dotenv import load_dotenv

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


CACHE_FILE = HERE / "github_cache.json"
if not CACHE_FILE.exists():
    CACHE_FILE.write_text(json.dumps({"branches": {}, "metadata": {}}, indent=2))
CACHE: dict[str, BranchInfo] = load_branches_cache()


def load_metadata_cache() -> AnyDict:
    return load_cache_file()["metadata"]


def update_cache(cache_dict: dict[str, BranchInfo], all_branches: list[str]) -> None:
    # Removing already merged branches from cache
    for branch in CACHE:
        if branch not in all_branches:
            del CACHE[branch]

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


def get_all_gh_pull_branches() -> list[str]:
    return [pr["head"]["ref"] for pr in get_all_gh_pulls()]


def skip_branch(branch: AnyDict) -> bool:
    last_commit_sha = branch["head"]["sha"]
    branch_name = branch["head"]["ref"]

    # TEMPORARY:
    # Only interested in new branches that have master_diff.html report in each test
    if (
        "grdddj" not in branch_name
        or "unit_tests" in branch_name
        or "ci_report" in branch_name
    ):
        print("Skipping, does not have master_diff.html")
        return True

    # Skip when we already have this commit in cache (and pipeline is finished)
    if branch_name in CACHE:
        cache_info = CACHE[branch_name]
        if cache_info.last_commit_sha == last_commit_sha:
            still_running = False
            for job_info in cache_info.job_infos.values():
                # TODO: investigate why this happens
                # (from CLI it is object, from HTML it is dict)
                if isinstance(job_info, dict):
                    status = job_info["status"]
                else:
                    status = job_info.status
                if status == "Running...":
                    still_running = True
            if not still_running:
                print(f"Skipping, commit did not change - {last_commit_sha}")
                return True

    # It can come from a fork - we do not have UI tests for it
    if branch_name == "master":
        print("Ignoring a fork")
        return True

    return False


def yield_recently_updated_gh_pr_branches() -> Iterator[BranchInfo]:
    for pr in get_all_gh_pulls():
        branch_name = pr["head"]["ref"]
        print(f"Getting branch {branch_name}")

        if skip_branch(pr):
            continue

        last_commit_sha = pr["head"]["sha"]

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
