# Github org runner exporter

Prometheus exporter metrics for github self-hosted runners.


## Settings

| Variable             | Required | Description |
|----------------------|:--------:|----------------------------------------|
| PRIVATE_GITHUB_TOKEN | Yes      | Github token with read org permissions
| OWNER                | Yes      | Github organization name
| REFRESH_INTERVAL     | No       | Internval time in seconds betwen api requests (Default: 20)


## Usage with helm

Clone the repository:

```sh
git clone git@github.com:tchelovilar/github-org-runner-exporter.git
```

Update the values file [deploy/helm-chart/prometheus-org-runner-exporter/values.yaml](./deploy/helm-chart/prometheus-org-runner-exporter/values.yaml)
with environment settings described above.

Go to the project foldar and execute helm install command:

```sh
cd github-org-runner-exporter

helm install github-runner-exporter ./deploy/helm-chart/prometheus-org-runner-exporter/
```
