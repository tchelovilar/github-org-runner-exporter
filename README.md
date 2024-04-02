# Github org runner exporter

Prometheus metrics exporter for github actions self-hosted runners.


## Settings

| Variable             | Required | Description |
|----------------------|:--------:|----------------------------------------|
| PRIVATE_GITHUB_TOKEN | Yes      | Github token with read org permissions
| OWNER                | Yes      | Github organization name
| REFRESH_INTERVAL     | No       | Internval time in seconds betwen api requests (Default: 20)
| LOG_LEVEL            | No       | Log level: DEBUG, INFO, WARNING or ERROR (Default: INFO)
| API_URL              | No       | URL to your github API (Default: https://api.github.com)
| GITHUB_APP_ID        | No       | The Github app id to login as
| GITHUB_PRIVATE_KEY   | No*      | The Github app private key generated from the app settings, required if GITHUB_APP_ID is set


## How to deploy

Create a secret with the [private token](https://github.com/settings/tokens) and the organization name:

```
kubectl create secret generic runner-exporter --from-literal=PRIVATE_GITHUB_TOKEN=<token> --from-literal=OWNER=<org>
```

Add the helm repo:

```
helm repo add tchelovilar https://tchelovilar.github.io/github-org-runner-exporter/
helm repo update
```

Install the helm chart:

```
helm install github-runner-exporter --set envFromSecret=runner-exporter tchelovilar/prometheus-org-runner-exporter
```


## Grafana Dashboard

Import the grafana dashboard file [grafana/dashboard.json](./grafana/dashboard.json)

![Grafana Dashboard](grafana/screenshot.png)
