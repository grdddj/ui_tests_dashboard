from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Iterator

import requests

from common_all import AnyDict, JobInfo

HERE = Path(__file__).parent

BRANCHES_API_TEMPLATE = "https://gitlab.com/satoshilabs/trezor/trezor-firmware/-/pipelines.json?scope=branches&page={}"
GRAPHQL_API = "https://gitlab.com/api/graphql"

SCREEN_AMOUNT_CACHE_FILE = HERE / "gitlab_cache.json"
if not SCREEN_AMOUNT_CACHE_FILE.exists():
    SCREEN_AMOUNT_CACHE_FILE.write_text("{}")
BRANCH_CACHE: dict[str, int] = json.loads(SCREEN_AMOUNT_CACHE_FILE.read_text())


def update_branch_cache(link: str, amount: int) -> None:
    BRANCH_CACHE[link] = amount
    SCREEN_AMOUNT_CACHE_FILE.write_text(json.dumps(BRANCH_CACHE, indent=2))


@lru_cache(maxsize=32)
def get_gitlab_branches_cached(page: int) -> list[AnyDict]:
    return requests.get(BRANCHES_API_TEMPLATE.format(page)).json()["pipelines"]


def get_newest_gitlab_branches() -> list[AnyDict]:
    return requests.get(BRANCHES_API_TEMPLATE.format(1)).json()["pipelines"]


def get_branch_obj(
    branch_name: str, first_page_cache: list[AnyDict] | None = None
) -> AnyDict:
    # Trying first 10 pages of branches
    for page in range(1, 11):
        # First page should be always updated (unless given),
        # rest can be cached
        if page == 1:
            if first_page_cache:
                branches = first_page_cache
            else:
                branches = get_newest_gitlab_branches()
        else:
            branches = get_gitlab_branches_cached(page)
            print(f"Checking page {page} / 10")
        for branch_obj in branches:
            if branch_obj["ref"]["name"] == branch_name:
                return branch_obj
    raise ValueError(f"Branch {branch_name} not found")


def get_pipeline_jobs_info(pipeline_iid: int) -> AnyDict:
    # Getting just the stuff we need - the job names and IDs
    graphql_query = """
query getJobsFromPipeline($projectPath: ID!, $iid: ID!) {
  project(fullPath: $projectPath) {
    pipeline(iid: $iid) {
      stages {
        nodes {
          groups {
            nodes {
              jobs {
                nodes {
                  id
                  name
                  status
                }
              }
            }
          }
        }
      }
    }
  }
}
    """
    query = {
        "query": graphql_query,
        "variables": {
            "projectPath": "satoshilabs/trezor/trezor-firmware",
            "iid": pipeline_iid,
        },
    }
    return requests.post(GRAPHQL_API, json=query).json()


def get_jobs_of_interests() -> list[str]:
    return [
        "core click R test",
        "core device R test",
        "core click test",
        "core device test",
        "unix ui changes",
    ]


def yield_pipeline_jobs(pipeline_iid: int) -> Iterator[AnyDict]:
    jobs_info = get_pipeline_jobs_info(pipeline_iid)
    stages = jobs_info["data"]["project"]["pipeline"]["stages"]["nodes"]
    for stage in stages:
        nodes = stage["groups"]["nodes"]
        for node in nodes:
            jobs = node["jobs"]["nodes"]
            for job in jobs:
                yield job


def get_diff_screens_from_text(html_text: str) -> int:
    row_identifier = 'bgcolor="red"'
    return html_text.count(row_identifier)


def get_status_from_link(job: AnyDict, link: str) -> tuple[str, int]:
    if job["status"] == "SKIPPED":
        return "Skipped", 0

    if link in BRANCH_CACHE:
        return "Finished", BRANCH_CACHE[link]

    res = requests.get(link)
    status = res.status_code
    if status == 200:
        diff_screens = get_diff_screens_from_text(res.text)
        update_branch_cache(link, diff_screens)
        return "Finished", diff_screens
    else:
        return "Running...", 0


def _get_job_info(job: AnyDict, find_status: bool = True) -> JobInfo:
    passed = job["status"] == "SUCCESS"
    job_id = job["id"].split("/")[-1]
    job_info = JobInfo(
        name=job["name"],
        job_id=job_id,
        passed=passed,
    )
    job_info.job_results = job_info.get_job_results()

    if find_status:
        status, diff_screens = get_status_from_link(job, job_info.master_diff_link)
    else:
        status, diff_screens = None, None

    job_info.status = status
    job_info.diff_screens = diff_screens

    return job_info


def get_latest_infos_for_branch(
    branch_name: str, find_status: bool, first_page_cache: list[AnyDict] | None = None
) -> tuple[str, dict[str, JobInfo]]:
    branch_obj = get_branch_obj(branch_name, first_page_cache)
    pipeline_iid = branch_obj["iid"]
    pipeline_id = branch_obj["id"]

    pipeline_link = f"https://gitlab.com/satoshilabs/trezor/trezor-firmware/-/pipelines/{pipeline_id}"

    def yield_key_value() -> Iterator[tuple[str, JobInfo]]:
        for job in yield_pipeline_jobs(pipeline_iid):
            for job_of_interest in get_jobs_of_interests():
                if job["name"] == job_of_interest:
                    yield job["name"], _get_job_info(job, find_status)

    return pipeline_link, dict(yield_key_value())
