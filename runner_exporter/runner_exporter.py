import requests
import os

from prometheus_client import start_http_server, Counter, Gauge
from time import sleep
from logger import get_logger

# Read environment variables
REFRESH_INTERVAL = int(os.environ.get("REFRESH_INTERVAL", 20))
PRIVATE_GITHUB_TOKEN = os.environ["PRIVATE_GITHUB_TOKEN"]
OWNER = os.environ["OWNER"]

logger = get_logger()


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
            ["name", "id", "os", "status", "labels", "busy"],
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

        # Clean up removed runners
        self.ghostbuster(current_runners)

    def ghostbuster(self, current_runners):
        """
            Case some runner is deleted this function will remove from the metrics
        """
        # Remove metric_runner_org_status ghost metrics
        active_metrics = self.metric_runner_org_status._metrics.copy()
        for runner in active_metrics:
            if runner[1] not in current_runners:
                logger.debug(
                    f"Removing {runner[0]} metric_runner_org_status metrics. {str(runner)}"
                )
                self.metric_runner_org_status.remove(*runner)

        # Remove metric_runner_org_label_status ghost metrics
        active_metrics = self.metric_runner_org_label_status._metrics.copy()
        for runner in active_metrics:
            if runner[1] not in current_runners:
                logger.debug(
                    f"Removing {runner[0]} metric_runner_org_label_status metrics. {str(runner)}"
                )
                self.metric_runner_org_label_status.remove(*runner)

        # Remove metric_runner_org_busy ghost metrics
        active_metrics = self.metric_runner_org_busy._metrics.copy()
        for runner in active_metrics:
            if runner[1] not in current_runners:
                logger.debug(
                    f"Removing {runner[0]} metric_runner_org_busy metrics. {str(runner)}"
                )
                self.metric_runner_org_busy.remove(*runner)

    def aggregate_labels(self, labels: dict):
        """
            Aggregate the runners labels in string
        """
        agg_labels = []
        for label in labels:
            if label["type"] == "custom":
                agg_labels.append(label["name"])

        agg_labels.sort()

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
            runner.get("name"),
            runner.get("id"),
            runner.get("os"),
            runner.get("status"),
            agg_labels,
            "true",
        ).set(busy)

        self.metric_runner_org_busy.labels(
            runner.get("name"),
            runner.get("id"),
            runner.get("os"),
            runner.get("status"),
            agg_labels,
            "false",
        ).set(idle)


def main():

    # Start prometheus metrics
    logger.info("Starting metrics server")
    start_http_server(8000)

    metric_runner_api_ratelimit = Gauge(
        "github_runner_api_remain_rate_limit",
        "Github Api remaining requests rate limit (per hour)",
        ["org"],
    )

    runner_exports = runnerExports()

    while True:
        headers = {"Authorization": f"token {PRIVATE_GITHUB_TOKEN}"}
        url = f"https://api.github.com/orgs/{OWNER}/actions/runners?per_page=100"
        logger.debug(f"Sending the api request for /orgs/{OWNER}/actions/runners")
        result = requests.get(url, headers=headers)
        all_runners=[]

        if result.headers:
            value = result.headers.get("X-RateLimit-Remaining")
            logger.debug(f"Remaining requests: {value}")
            metric_runner_api_ratelimit.labels(OWNER).set(int(value))

        if result.ok:
            runner_list = result.json()
            number_of_pages = (runner_list["total_count"]//100)+1
            for page in range(1, number_of_pages+1):
                url = f"https://api.github.com/orgs/{OWNER}/actions/runners?per_page=100&page={page}"
                logger.debug(f"Sending the api request for /orgs/{OWNER}/actions/runners?per_page=100&page={page}")
                result = requests.get(url, headers=headers)
                runners = result.json()["runners"]
                all_runners += runners

            runner_exports.export_metrics(all_runners)
        else:
            logger.error(f"Api request returned error: {result.reason} {result.text}")

        sleep(REFRESH_INTERVAL)


if __name__ == "__main__":
    main()
