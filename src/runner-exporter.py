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
            "github_runner_org_status",
            "Runner status",
            ["name", "id", "os", "labels", "status"],
        )
        self.metric_runner_org_label_status = Gauge(
            "github_runner_org_label_status",
            "Runner label status",
            ["name", "id", "os", "label", "status"],
        )

        self.metric_runner_org_busy = Gauge(
            "github_runner_org_busy",
            "Runner busy status",
            ["name", "id", "os", "labels", "busy"],
        )

    def export_metrics(self, runner_list: list):
        current_runners = []

        for runner in runner_list:
            agg_labels = self.aggregate_labels(runner["labels"])
            # Export metrics
            self.export_runner_status(runner, agg_labels)
            self.export_runner_busy(runner, agg_labels)
            # Updated active runners list
            current_runners.append(str(runner["id"]))

        self.ghostbuster(current_runners)

    def ghostbuster(self, current_runners):
        """
            Case some runner is deleted this function will remove from the metrics
        """
        # Remove ghosts form metric_runner_org_status metric
        runners_to_remove = []
        for (
            runner_name,
            runner_id,
            runner_os,
            labels,
            runner_status,
        ) in self.metric_runner_org_status._metrics:
            if runner_id not in current_runners:
                runners_to_remove.append(
                    (runner_name, runner_id, runner_os, labels, runner_status)
                )
        for (
            runner_name,
            runner_id,
            runner_os,
            labels,
            runner_status,
        ) in runners_to_remove:
            self.metric_runner_org_status.remove(
                runner_name, runner_id, runner_os, labels, runner_status
            )
        # Remove ghosts form metric_runner_org_label_status metric
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
        # Remove ghosts form metric_runner_org_busy metric
        runners_to_remove = []
        for (
            runner_name,
            runner_id,
            runner_os,
            labels,
            runner_busy,
        ) in self.metric_runner_org_busy._metrics:
            if runner_id not in current_runners:
                runners_to_remove.append(
                    (runner_name, runner_id, runner_os, labels, runner_busy)
                )
        for runner_name, runner_id, runner_os, labels, runner_busy in runners_to_remove:
            self.metric_runner_org_busy.remove(
                runner_name, runner_id, runner_os, labels, runner_busy
            )

    def aggregate_labels(self, labels: dict):
        """
            Aggregate the runners labels in string
        """
        agg_labels = []
        for label in labels:
            if label["type"] == "custom":
                agg_labels.append(label["name"])

        return ",".join(agg_labels)

    def export_runner_status(self, runner: dict, agg_labels: str):
        online = 1
        offline = 0
        if runner.get("status") != "online":
            online = 0
            offline = 1

        self.metric_runner_org_status.labels(
            runner.get("name"), runner.get("id"), runner.get("os"), agg_labels, "online"
        ).set(online)
        self.metric_runner_org_status.labels(
            runner.get("name"),
            runner.get("id"),
            runner.get("os"),
            agg_labels,
            "offline",
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

    def export_runner_busy(self, runner: dict, agg_labels: str):
        idle = 1
        busy = 0

        if runner.get("busy") == True:
            idle = 0
            busy = 1

        self.metric_runner_org_busy.labels(
            runner.get("name"), runner.get("id"), runner.get("os"), agg_labels, "true"
        ).set(busy)

        self.metric_runner_org_busy.labels(
            runner.get("name"), runner.get("id"), runner.get("os"), agg_labels, "false"
        ).set(idle)


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
