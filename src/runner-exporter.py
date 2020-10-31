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

# Define metrics to expose
metric_runner_api_ratelimit = Gauge(
    "github_runner_api_remain_rate_limit", "Github Api remaining rate limit", ["org"]
)

metric_runner_org_status = Gauge(
    "github_runner_org_status", "Runner status", ["name", "id", "os", "status"]
)
metric_runner_org_label_status = Gauge(
    "github_runner_org_label_status",
    "Runner label status",
    ["name", "id", "os", "label", "status"],
)

metric_runner_org_busy = Gauge(
    "github_runner_org_busy", "Runner busy status", ["name", "id", "os", "busy"]
)


def export_runner_status(runner: dict):
    metric_runner_org_status.labels(
        runner.get("name"), runner.get("id"), runner.get("os"), runner.get("status")
    ).set(1)


def export_runner_status_by_label(runner: dict):
    for label in runner["labels"]:
        metric_runner_org_label_status.labels(
            runner.get("name"),
            runner.get("id"),
            runner.get("os"),
            label["name"],
            runner.get("status"),
        ).set(1)


def export_runner_busy(runner: dict):
    metric_runner_org_busy.labels(
        runner.get("name"), runner.get("id"), runner.get("os"), runner.get("busy")
    ).set(1)


def main():

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
            for runner in runner_list["runners"]:
                export_runner_status(runner)
                export_runner_status_by_label(runner)
                export_runner_busy(runner)
        sleep(REFRESH_INTERVAL)


if __name__ == "__main__":
    main()
