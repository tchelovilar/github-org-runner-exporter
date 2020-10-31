import requests
import os

from prometheus_client import start_http_server, Counter, Gauge
from time import sleep

# Read environment variables
REFRESH_INTERVAL = os.environ.get("REFRESH_INTERVAL", 20)
PRIVATE_GITHUB_TOKEN = os.environ["PRIVATE_GITHUB_TOKEN"]
OWNER = os.environ["OWNER"]

# Start prometheus metrics
start_http_server(8000)

metric_runner_api_ratelimit = Gauge(
    "github_runner_api_remain_rate_limit", "Github Api remaining rate limit", ["org"]
)


class runnerExports:
    def __init__(self):
        # Define metrics to expose
        self.metric_runner_org_status = Gauge(
            "github_runner_org_status", "Runner status", ["name", "id", "os", "status"]
        )
        self.metric_runner_org_label_status = Gauge(
            "github_runner_org_label_status",
            "Runner label status",
            ["name", "id", "os", "label", "status"],
        )

        self.metric_runner_org_busy = Gauge(
            "github_runner_org_busy", "Runner busy status", ["name", "id", "os", "busy"]
        )

    def export_metrics(self, runner_list: list):
        current_runners = []

        for runner in runner_list:
            self.export_runner_status(runner)
            self.export_runner_busy(runner)
            current_runners.append(str(runner["id"]))

        self.ghostbuster(current_runners)

    def ghostbuster(self, current_runners):
        runners_to_remove = []
        for (
            runner_name,
            runner_id,
            runner_os,
            runner_status,
        ) in self.metric_runner_org_status._metrics:
            if runner_id not in current_runners:
                runners_to_remove.append(
                    (runner_name, runner_id, runner_os, runner_status)
                )
        # Remove ghosts
        for runner_name, runner_id, runner_os, runner_status in runners_to_remove:
            self.metric_runner_org_status.remove(
                runner_name, runner_id, runner_os, runner_status
            )

        runners_to_remove = []
        for (
            runner_name,
            runner_id,
            runner_os,
            runner_label,
            runner_status,
        ) in self.metric_runner_org_label_status._metrics:
            if runner_id not in current_runners:
                runners_to_remove.append(
                    (runner_name, runner_id, runner_os, runner_label, runner_status)
                )
        # Remove ghosts
        for (
            runner_name,
            runner_id,
            runner_os,
            runner_label,
            runner_status,
        ) in runners_to_remove:
            self.metric_runner_org_label_status.remove(
                runner_name, runner_id, runner_os, runner_label, runner_status
            )

        runners_to_remove = []
        for (
            runner_name,
            runner_id,
            runner_os,
            runner_busy,
        ) in self.metric_runner_org_busy._metrics:
            if runner_id not in current_runners:
                runners_to_remove.append(
                    (runner_name, runner_id, runner_os, runner_busy)
                )
        # Remove ghosts
        for runner_name, runner_id, runner_os, runner_busy in runners_to_remove:
            self.metric_runner_org_busy.remove(
                runner_name, runner_id, runner_os, runner_busy
            )

    def export_runner_status(self, runner: dict):
        online = 1
        offline = 0
        if runner.get("status") != "online":
            online = 0
            offline = 1

        self.metric_runner_org_status.labels(
            runner.get("name"), runner.get("id"), runner.get("os"), "online"
        ).set(online)
        self.metric_runner_org_status.labels(
            runner.get("name"), runner.get("id"), runner.get("os"), "offline"
        ).set(offline)

        for label in runner["labels"]:
            self.metric_runner_org_label_status.labels(
                runner.get("name"),
                runner.get("id"),
                runner.get("os"),
                label["name"],
                "online",
            ).set(online)

            self.metric_runner_org_label_status.labels(
                runner.get("name"),
                runner.get("id"),
                runner.get("os"),
                label["name"],
                "offline",
            ).set(offline)

    def export_runner_busy(self, runner: dict):
        self.metric_runner_org_busy.labels(
            runner.get("name"), runner.get("id"), runner.get("os"), runner.get("busy")
        ).set(1)


def main():
    runner_exports = runnerExports()
    while True:
        # Get actions runners status
        headers = {"Authorization": f"token {PRIVATE_GITHUB_TOKEN}"}
        url = f"https://api.github.com/orgs/{OWNER}/actions/runners"
        result = requests.get(url, headers=headers)
        if result.headers:
            value = result.headers.get("X-RateLimit-Remaining")
            metric_runner_api_ratelimit.labels(OWNER).set(int(value))
        if result.ok:
            runner_list = result.json()
            runner_exports.export_metrics(runner_list["runners"])

        sleep(REFRESH_INTERVAL)


if __name__ == "__main__":
    main()
