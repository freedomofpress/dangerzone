from dataclasses import dataclass


@dataclass
class Report:
    gh_version: str | None = None
    gh_changelog: str | None = None
    container_needs_upgrade: bool = False
    error: str | None = None


def do_something_for_me() -> Report:
    # I want to report the following:
    # 1. There were an error
    raise Exception("Something happened")
    report = Report()
    report.gh_version = something
    report.gh_changelog = changelog
    report.container_needs_upgrade = True

    return report


if __name__ == "__main__":
    try:
        report = do_something_for_me()
    except ReportException:
        pass
