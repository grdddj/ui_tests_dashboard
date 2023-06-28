from __future__ import annotations

import click

from github import (
    get_all_gh_pull_branches,
    update_cache,
    yield_recently_updated_gh_pr_branches,
)
from gitlab import get_latest_infos_for_branch, get_newest_gitlab_branches


@click.group()
def cli():
    pass


@cli.command(name="branch")
@click.argument("branch", default="master")
@click.option("--no-status", is_flag=True, default=False)
def get_branch(branch: str, no_status: bool):
    print(f"Getting links for branch: {branch}")
    pipeline_link, tests_info = get_latest_infos_for_branch(branch, not no_status)

    for name, info in tests_info.items():
        print(name)
        for key, value in info.to_dict().items():
            print(f"  - {key}: {value}")
    print(f"Pipeline link: {pipeline_link}")


def do_update_pulls():
    new_branch_infos = list(yield_recently_updated_gh_pr_branches())
    print(80 * "*")
    print(f"Found {len(new_branch_infos)} new branches")
    # speeding things up by loading the first common page
    first_page_cache = get_newest_gitlab_branches()
    for branch in new_branch_infos:
        print(f"Getting links for branch: {branch}")
        try:
            pipeline_link, tests_info = get_latest_infos_for_branch(
                branch.name, True, first_page_cache
            )
            branch.pipeline_link = pipeline_link
            branch.job_infos = tests_info
        except Exception as e:
            print(f"Failed to get links for branch: {branch.name}")
            print(e)

    branch_dict = {branch.name: branch for branch in new_branch_infos}
    all_branches = get_all_gh_pull_branches()
    update_cache(branch_dict, all_branches)


@cli.command(name="pulls")
def update_pulls():
    do_update_pulls()


if __name__ == "__main__":
    cli()
