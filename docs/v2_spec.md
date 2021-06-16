<!--
Copyright 2017-2019 The FIAAS Authors

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->
# V2 Spec file reference
This file represents how your application will be deployed into Kubernetes.

## version

| **Type** | **Required** |
|----------|--------------|
| int      | yes          |

Which version of this spec to be used.

```yaml
version: 2
```


## namespace

| **Type** | **Required** |
|----------|--------------|
| string   | no           |

The name of the namespace where the application will be deployed into (meaning, where kubernetes objects will be created).

```yaml
namespace: default
```


## admin_access

| **Type** | **Required** |
|----------|--------------|
| boolean  | no           |

Whether or not the default `ServiceAccount` on that namespace will be mounted inside the Pod.

```yaml
admin_access: False
```


## replicas

| **Type** | **Required** |
|----------|--------------|
| int      | no           |

Number of Pods to create for the application.

```yaml
replicas: 2
```


## host

| **Type** | **Required** |
|----------|--------------|
| string   | no           |

Host where the Ingress controller will expect requests to the application.

```yaml
host: your-app.example.com
```


## has_secrets

| **Type** | **Required** |
|----------|--------------|
| boolean  | no           |

If True, a Secret with the application's name will be mounted into the Pods.

```yaml
has_secrets: False
```


## resources

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

[Resources](https://kubernetes.io/docs/concepts/configuration/manage-compute-resources-container/) required by the application.

### limits

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

Maximum amount of resources this application needs.

#### memory

| **Type** | **Required** |
|----------|--------------|
| string   | no           |

The application will be OOM killed if exceeding these limits.

#### cpu

| **Type** | **Required** |
|----------|--------------|
| string   | no           |

The application will have its CPU usage throttled if exceeding this limit.

### requests

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

Maximum amount of resources this application needs.

#### memory

| **Type** | **Required** |
|----------|--------------|
| string   | no           |

The application will be scheduled on nodes with at least this amount of memory available.

#### cpu

| **Type** | **Required** |
|----------|--------------|
| string   | no           |

The application will be scheduled on nodes with at least this amount of CPU available.

```yaml
resources:
  limits:
    memory: 1G
    cpu: 1
  requests:
    memory:  512M
    cpu: 0.7
```


## autoscaler

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

Enables Kubernetes Horizontal Pod Autoscaling. It scales from `autoscaler.min_replicas` to `replicas`. If enabled, you need to set `resources.requests.cpu` too.
Scales up on mean CPU utilisation higher than `autoscaler.cpu_threshold_percentage`. See [https://kubernetes.io/docs/user-guide/horizontal-pod-autoscaling/](https://kubernetes.io/docs/user-guide/horizontal-pod-autoscaling/).

```yaml
autoscaler:
  enabled: False
  min_replicas: 2
  cpu_threshold_percentage: 50
```


## prometheus

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

Tells Prometheus where to find application metrics.

### enabled
| **Type** | **Required** |
|----------|--------------|
| boolean  | no           |

Whether or not the pod will be scraped by Prometheus looking for metrics.

### port
| **Type** | **Required** |
|----------|--------------|
| string   | no          |

Name of HTTP port prometheus is served on.

### path
| **Type** | **Required** |
|----------|--------------|
| string   | no          |

Endpoint where metrics are being exposed.

```yaml
prometheus:
  enabled: True
  port: http
  path: /internal-backstage/prometheus
```


## ports

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

List of ports the application listens for HTTP requests.

### protocol
| **Type** | **Required** |
|----------|--------------|
| boolean  | no           |

Protocol used by the application. It must be `HTTP` or `TCP`.

### name
| **Type** | **Required** |
|----------|--------------|
| string   | no          |

A logical name for port discovery. Must be <= 63 characters and match `[a-z0-9]([-a-z0-9]*[a-z0-9])?`.

### path
| **Type** | **Required** |
|----------|--------------|
| string   | no          |

Only for `HTTP`. Used together with `host`.

### port
| **Type** | **Required** |
|----------|--------------|
| int      | no           |

Port number that will be exposed. For protocol equals TCP the available port range is (1024-32767).

### target_port
| **Type** | **Required** |
|----------|--------------|
| int      | no           |

The port number which is exposed by the container and should receive traffic routed to `port`.

```yaml
ports:
  - protocol: http
    name: http
    port: 80
    target_port: 80
    path: /
```


## config

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

A `ConfigMap` of the same name must exist, and it'll be made available to the application.

### volume
| **Type** | **Required** |
|----------|--------------|
| boolean  | no           |

Whether or not to mount the `ConfigMap` as volume inside the `Pod`.
If True, the `ConfigMap` is mounted at `/var/run/config/fiaas/`.

### envs
| **Type** | **Required** |
|----------|--------------|
| list     | no          |

A list of environment variables to set from the `ConfigMap`. The entry must be named the same in the `ConfigMap`.

```yaml
config:
  volume: False
  envs: []
```


## healthchecks

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

Application endpoints to be used by Kubernetes to determine [when your application is alive and ready](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-probes/).
If `healthchecks.readiness` is left out, `healthchecks.liveness` will be used as `healthchecks.readiness` too.

### liveness

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

It defines the check used to determine if your application is alive. Based on [Kubernetes configuration for liveness](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-probes/#define-a-liveness-command).

### readiness

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

It defines the check used to determine if your application is ready to serve traffic. Based on [Kubernetes configuration for readiness](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-probes/#define-readiness-probes).


```yaml
healthchecks:
  liveness:
    http:
      path: /
      port: http
      http_headers: {}
    initial_delay_seconds: 10
    period_seconds: 10
    success_threshold: 1
    timeout_seconds: 1
```
