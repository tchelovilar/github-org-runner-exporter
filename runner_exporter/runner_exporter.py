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
        """
        Export Runner busy status and running status
        """
        busy_values = [True, False]
        status_values = ["online", "offline"]

        for busy_value in busy_values:
            for status_value in status_values:
                metric_value = 0
                if (
                    runner.get("busy") == busy_value
                    and runner.get("status") == status_value
                ):
                    metric_value = 1

                self.metric_runner_org_busy.labels(
                    runner.get("name"),
                    runner.get("id"),
                    runner.get("os"),
                    status_value,
                    agg_labels,
                    str(busy_value).lower(),
                ).set(metric_value)


class githubApi:
    def __init__(self, github_token, github_owner, logger) -> None:
        self.metric_runner_api_ratelimit = Gauge(
            "github_runner_api_remain_rate_limit",
            "Github Api remaining requests rate limit (per hour)",
            ["org"],
        )

        self.headers = {"Authorization": f"token {github_token}"}
        self.github_owner = github_owner

        self.logger = logger

    def list_runners(self) -> list:
        runners_list = []

        per_page = 100
        url = f"https://api.github.com/orgs/{self.github_owner}/actions/runners?per_page={per_page}"

        while True:
            try:
                self.logger.debug(f"Sending the api request for {url}")
                result = requests.get(url, headers=self.headers)

                if result.headers:
                    remaining_requests = result.headers.get("X-RateLimit-Remaining")
                    logger.debug(f"Remaining requests: {remaining_requests}")
                    self.metric_runner_api_ratelimit.labels(self.github_owner).set(
                        int(remaining_requests)
                    )

                if not result.ok:
                    logger.error(
                        f"Api request returned error: {result.reason} {result.text}"
                    )
                    return []

                api_result = result.json()
                runners_list += api_result["runners"]

                if "next" in result.links.keys():
                    url = result.links["next"]["url"]
                else:
                    break
            except Exception as error:
                logger.error(f"Exception: {error}")
                return []

        return runners_list


def main():

    # Start prometheus metrics
    logger.info("Starting metrics server")
    start_http_server(8000)

    runner_exports = runnerExports()

    github = githubApi(PRIVATE_GITHUB_TOKEN, OWNER, logger)

    while True:
        runners_list = github.list_runners()

        if runners_list:
            runner_exports.export_metrics(runners_list)

        sleep(REFRESH_INTERVAL)


if __name__ == "__main__":
    main()
