# Github org runner exporter

Prometheus metrics exporter for GitHub actions self-hosted runners.


## Settings

| Variable             | Required | Description |
|----------------------|:--------:|----------------------------------------|
| PRIVATE_GITHUB_TOKEN | Yes      | Github token with read org permissions
| OWNER                | Yes      | Github organization name
| REFRESH_INTERVAL     | No       | Internval time in seconds betwen api requests (Default: 20)
| LOG_LEVEL            | No       | Log level: DEBUG, INFO, WARNING or ERROR (Default: INFO)


### Authenticating with Github App

The runner exporter requires an API authentication, the recommended way is to create a Github App from the Organization Settings with read-only permission for `Self-hosted runners`, after creating the App you have to install it to the Organization.

You can create the app from the link https://github.com/organizations/MYORG/settings/apps


| Variable             | Required | Description |
|----------------------|:--------:|----------------------------------------|
| GITHUB_APP_ID        | Yes      | Github App ID
| GITHUB_PRIVATE_KEY   | Yes      | Github App private key, you can generate a
| API_URL              | No       | URL to your github API, for Github Enterprise, set it with your API url, like https://github.myenterprise.com/api/v3/orgs/MYORG/  (Default: https://api.github.com)


### Authenticating with a Private Token

It's also possible to authenticate using a Private user token, but it's not recommended.

| Variable             | Required | Description |
|----------------------|:--------:|----------------------------------------|
| PRIVATE_GITHUB_TOKEN | Yes      | Github token with read org permissions


## How to deploy

Once you have created the Github APP, installed it and downloaded the private key file, you can generate a Kubernetes secrets to store it, like:

```bash
kubectl create secret generic runner-exporter \
        --from-literal=OWNER=<organization_name> \
        --from-literal=GITHUB_APP_ID=<app_id> \
        --from-literal=GITHUB_PRIVATE_KEY="-----KEY-----
xxxxxxxx
xxxxxxxx
xxxxxxxx
-----END KEY-----"
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


## Runners Auto Scaling

The generated metrics can be used by [Keda](https://keda.sh/docs/2.13/concepts/) to scale up the Github Runners, on this example keda will add an extra pod when the number of Pods is the same of active replicas.
Be careful, the auto scaler will always scale down the most recent pod, which can interrupt long-running jobs, be sure that you have the Github Runners properly configured to proceed with the scale-down.

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: github-runner
spec:
  advanced:
    horizontalPodAutoscalerConfig:
      behavior:
        scaleDown:
          policies:
          - periodSeconds: 15
            type: Percent
            value: 100
          stabilizationWindowSeconds: 1800 # Seconds before start to scale down
  maxReplicaCount: 8
  minReplicaCount: 1
  scaleTargetRef:
    kind: Deployment
    name: github-runner # Kubernetes Deployment name
  triggers:
  - metadata:
      query: sum(github_runner_org_busy{busy="true", labels="docker,scale"})
      serverAddress: http://prometheus-server.prometheus.svc.cluster.local:9090  # Prometheus server address
      threshold: "0.9"
    type: prometheus
```


## Running locally on docker-compose

You can run it also in the docker-compose. (Thanks @littlej956)

```yaml
services:
	github_runners_exporter:
		image: tchelovilar/github-org-runner-exporter:0.2.2
		container_name: github_runner_exporter
		environment:
		- OWNER=owner
		- GITHUB_APP_ID=12312312
		- |
				GITHUB_PRIVATE_KEY=-----KEY-----
				xxxxxxxx
				xxxxxxxx
				xxxxxxxx
				-----END KEY-----
		- LOG_LEVEL=DEBUG
```
