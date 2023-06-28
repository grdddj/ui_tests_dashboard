from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

AnyDict = dict[Any, Any]


@dataclass
class BranchInfo:
    name: str
    branch_link: str
    pull_request_number: int
    pull_request_name: str
    pull_request_link: str
    last_commit_sha: str
    last_commit_timestamp: int
    last_commit_datetime: str
    job_infos: dict[str, JobInfo]
    pipeline_link: str | None = None

    @classmethod
    def from_dict(cls, data: AnyDict) -> BranchInfo:
        self = BranchInfo(**data)
        # Need to transform job_info dict to JobInfo objects,
        # as that was not done automatically by dataclass
        self.job_infos = {
            job_name: JobInfo.from_dict(job_info_dict)  # type: ignore
            for job_name, job_info_dict in self.job_infos.items()
        }
        return self

    def to_dict(self) -> AnyDict:
        # Need to transform JobInfo objects to dict as well to add extra properties
        self.job_infos = {  # type: ignore
            job_name: job_info if isinstance(job_info, dict) else job_info.to_dict()
            for job_name, job_info in self.job_infos.items()
        }
        return asdict(self)


job_info_extra_properties = ["job_link", "reports_link", "master_diff_link"]


@dataclass
class JobInfo:
    name: str
    job_id: str
    passed: bool = False
    status: str | None = None
    diff_screens: int | None = None

    @classmethod
    def from_dict(cls, data: AnyDict) -> JobInfo:
        for extra in job_info_extra_properties:
            if extra in data:
                del data[extra]
        return JobInfo(**data)

    def to_dict(self) -> AnyDict:
        res = asdict(self)
        for extra in job_info_extra_properties:
            res[extra] = getattr(self, extra)
        return res

    @property
    def _reports_base_url(self) -> str:
        return f"https://satoshilabs.gitlab.io/-/trezor/trezor-firmware/-/jobs/{self.job_id}/artifacts"

    @property
    def _folder(self) -> str:
        # Normal tests vs "unix ui changes" test
        if self.name.startswith("core"):
            return "test_ui_report"
        else:
            return "master_diff"

    @property
    def master_diff_link(self) -> str:
        return f"{self._reports_base_url}/{self._folder}/master_diff.html"

    @property
    def job_link(self) -> str:
        return f"https://gitlab.com/satoshilabs/trezor/trezor-firmware/-/jobs/{self.job_id}"

    @property
    def reports_link(self) -> str:
        return f"{self.job_link}/artifacts/browse/{self._folder}"


def get_logger(name: str, log_file_path: str | Path) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    log_handler = logging.FileHandler(log_file_path)
    log_formatter = logging.Formatter("%(asctime)s %(message)s")
    log_handler.setFormatter(log_formatter)
    logger.addHandler(log_handler)
    return logger
