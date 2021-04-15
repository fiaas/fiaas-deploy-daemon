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
# V3 Spec file reference

This file represents how your application will be deployed into Kubernetes.


## version

| **Type** | **Required** |
|----------|--------------|
| int      | yes          |

Which version of this spec to be used. This field must be set to `3` to use the features described below.
Documentation for [version 2 can be found here](/docs/v2_spec.md).

```yaml
version: 3
```


## replicas

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

Number of pods (instances) to run of the application. Based on the values of `minimum` and `maximum`, this object also
controls whether the number of replicas should be automatically scaled based on load.


Default value:
```yaml
replicas:
  minimum: 2
  maximum: 5
  cpu_threshold_percentage: 50
  singleton: true
```

### minimum

| **Type** | **Required** |
|----------|--------------|
| int      | no           |

Minimum number of pods to run for the application.

If `minimum` and `maximum` are set to the same value, autoscaling will be disabled.

Default value:
```yaml
replicas:
  minimum: 2
```


### maximum

| **Type** | **Required** |
|----------|--------------|
| int      | no           |

Maximum number of pods to run for the application.

If `minimum` and `maximum` are set to the same value, autoscaling will be disabled.


Default value:
```yaml
replicas:
  maximum: 5
```

### cpu_threshold_percentage

| **Type** | **Required** |
|----------|--------------|
| int      | no           |

If `maximum` is greater than `minimum`, autoscaling is enabled for the application.

Currently, the only supported metric for autoscaling is average cpu usage. If average cpu usage across all pods is
greater than this value over some time period, the number of pods will be increased. If average cpu usage across all
pods is less than this value, the number of pods will be decreased after some time period.

Autoscaling is done by using a
[`HorizontalPodAutoscaler`](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/).

If autoscaling is disabled, this value is ignored.

Default value:
```yaml
replicas:
  cpu_threshold_percentage: 50
```

### singleton

| **Type** | **Required** |
|----------|--------------|
| bool     | no           |

Whether there should be a maximum of a single running replica at any one time. Only operational if maximum replicas is
one. Set to false to have multiple replicas running during deployment, avoiding downtime.

This flag is only relevant for single replica applications. If your app normally has more than one replica, the flag is
ignored.

For single replica apps, the `singleton` flag indicates if it is important for the application to never run more than
one replica at a time. If `singleton` is `true` (the default), then the running replica will be shut down before a new
replica is started. This leads to downtime during deploy, but allows for applications that require exclusive access
to some resource.

If you have an application that runs in a single replica, but can run in multiple replicas for short periods of time,
changing this flag to `false` will allow deployments to start a new replica before the old one is shut down, allowing
for zero downtime deployments.

Default value:
```yaml
replicas:
  singleton: true
```

## ingress

| **Type** | **Required** |
|----------|--------------|
| list     | no           |

This object configures path-based/layer 7 routing of requests to the application.
It is a list of hosts which can each have a list of path and port combinations. Requests to the combination of host and
path will be routed to the port specified on the path element. Setting annotations on an entry means a separate Ingress
will be created, and will have metadata.annotations set accordingly.

Default value:
```yaml
ingress:
  - host: # no default value
    paths:
    - path: /
      port: http
    annotations: {}
```

All applications will get a set of default hosts, if the cluster operator has defined ingress suffixes.
If you do not specify a host in your `ingress` configuration, these default hosts will be used.
For example :
1. `your-app.example1.com`
2. `your-app.example2.com`

When you expose a path on a host you get that one as well. For example :
```yaml
ingress:
  - host: example.com
    paths:
    - path: /my-path
```

If you want to customize paths for default hosts as well, you can do it as :
```yaml
ingress:
  - host: example.com
    paths:
    - path: /my-path
  - paths:
    - path: /some-other-path

```

This will make `/some-other-path` available on default hosts, but not on the host you provided in ingress.
Remember, default hosts will also contain the paths from the ingress.

### host

| **Type** | **Required** |
|----------|--------------|
| string   | no           |

The hostname part of a host + path combination where your application expects requests.

If fiaas-deploy-daemon in the namespace you are deploying to is set up with one or more default ingress suffixes, all
paths specified will be made available under these ingress suffixes.  E.g. if `foo.example.com` is the default ingress
suffix, and your application is named `myapp`, your application will be available on `myapp.foo.example.com/`

If the `host` field is set, the application will be available on `host` + any paths specified *in addition* to any
default ingress suffixes.

Example:
```yaml
ingress:
  - host: your-app.example.com
```

If the operator of your cluster has configured host-rewrite rules they will be applied to the hostname given in this
field. See [the operator guide](operator_guide.md#host-rewrite-rules) for details about how this feature works.

In typical clusters, this value should be the host used by your application in production, and host-rewrite rules should
be used to adapt the host to testing environments.

### paths

| **Type** | **Required** |
|----------|--------------|
| list     | no           |

List of paths and port combinations.

Example:
```yaml
ingress:
  - host: your-app.example.com
    paths:
      - path: /foo
      - path: /bar
      - path: /metrics
        port: metrics-port
```

In this example, requests to `your-app.example.com/foo` or `your-app.example.com/bar` will go to the port named
`http`. Unless overridden, this is the default service port 80 which points to target port 8080 in the pod running
your application. Requests to `your-app.example.com/metrics` will go to the port named metrics-port, which also has to
be defined under the `ports` configuration structure. It is also possible to use a port number, but named ports are
strongly recommended.

### annotations

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

A map of annotations to add to the ingress.

Each entry in the ingress list that contains a non-empty `annotations` value will cause a separate Ingress object to
be created during the deployment. All items that have an empty value will have their hosts/paths merged into a single
Ingress.

Example:
```yaml
ingress:
  - host: your-app.example.com
    paths:
      - path: /foo
  - host: other.example.com
    paths:
      - path: /foo
    annotations:
      some/annotation: bar
```

In this example, the first ingress will be created for `your-app.example.com` (along with any default suffixes, if present) and
a second will be created for `other.example.com` and this will be annotated with the provided values.

Annotations defined within the `ingress.annotations` config will take precedence over any defined in the top-level `annotations`
configuration.

Example:
```yaml
ingress:
  - host: app.example.com
  - host: other.example.com
    annotations:
      some/annotation: foo

annotations:
  ingress:
    some/annotation: bar
```

In this example, the ingress for `app.example.com` will have the annotation set with the value `bar`, while the ingress for
`other.example.com` will have it set to `foo`.

## healthchecks

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

Application endpoints to be used by Kubernetes to determine [whether your application is up and/or ready to handle requests](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-probes/).
If `healthchecks.liveness` is specified and `healthchecks.readiness` is not specified, `healthchecks.liveness` will be used as the value for `healthchecks.readiness`.

### liveness

| **Type** | **Required** |
|----------|--------------|
| object   | no           |


Default value:
```yaml
healthchecks:
  liveness:
    execute:
      command: # No default value
    http:
      path: /_/health
      port: http
      http_headers: {}
    tcp:
      port: # no default value
    initial_delay_seconds: 10
    period_seconds: 10
    success_threshold: 1 # For liveness, 1 is the only valid value. For readiness, it can be higher
    timeout_seconds: 1
```

You can only have one check, so specify only one of `execute`, `http`, or `tcp`. The default is a `http` check, which
will send a HTTP request to the path and port configuration on the pod running the application. The health check will
be considered good if the HTTP response has a status code in the 200 range. Otherwise it will be considered bad.

An `execute` check can be used to execute a program inside the pod running the application. In this case, a exit
status of 0 is considered a good health check, while any other exit status is considered bad.

Example:
```yaml
healthchecks:
  liveness:
    execute:
      command: /app/bin/check --foo
```

A `tcp` check can be used if the application's primary endpoint uses some other application layer protocol than
HTTP. This type of check attempts to negotiate a TCP handshake on the specified port. If this succeeds, the health
check is considered good, otherwise it is considered bad.

Example:
```yaml
healthchecks:
  liveness:
    tcp:
      port: 70
```

### readiness

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

`liveness` and `readiness` use the same structure for configuring the check itself. See the documentation for `liveness`.


## resources

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

[Resources](https://kubernetes.io/docs/concepts/configuration/manage-compute-resources-container/) required by the
application.

Default value:
```yaml
resources:
  limits:
    cpu: 400m
    memory: 512Mi
  requests:
    cpu: 200m
    memory: 256Mi
```

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

Minimum amount of resources this application needs.

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

Example:
```yaml
resources:
  limits:
    memory: 1G
    cpu: 1
  requests:
    memory:  512M
    cpu: 0.7
```


## metrics

### prometheus

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

Tells Prometheus where to find application metrics.

Default value:
```yaml
metrics:
  prometheus:
    enabled: true
    port: http
    path: /_/metrics
```

#### enabled
| **Type** | **Required** |
|----------|--------------|
| boolean  | no           |

Whether or not the pods running the application will be scraped by Prometheus looking for metrics.

#### port
| **Type** | **Required** |
|----------|--------------|
| string   | no           |

Name of HTTP port Prometheus metrics are served on.

#### path
| **Type** | **Required** |
|----------|--------------|
| string   | no           |

HTTP endpoint where metrics are exposed.

### datadog

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

Configure datadog.

Default value:
```yaml
metrics:
  datadog:
    enabled: false
    tags: {}
```

#### enabled
| **Type** | **Required** |
|----------|--------------|
| boolean  | no           |

Attach a datadog sidecar for metrics collection. The sidecar will run DogStatsD, and your application should send metrics
to `${STATSD_HOST}:${STATSD_PORT}` (in the current incarnation, this is set to `localhost:8125`, but your application
should make use of the environment variables in order to be somewhat futureproof). In order for this to send metrics to the
correct datadog account, a secret must be created in the namespace which contains the datadog API key. This key decides
where the metrics end up.

Creating the datadog secret can be done using `kubectl` directly:

```
kubectl -n "${NAMESPACE}" create secret generic datadog --from-literal apikey="${DD_API_KEY}"
```

Three additional tags are attached to the collected metrics automatically:

- namespace name
- application name
- pod name

#### tags
| **Type** | **Required** |
|----------|--------------|
| object   | no           |

Include the given tags for metrics exposed by the Datadog sidecar.
These metrics will be added to the three metrics injected by default
(namespace name, app name, pod name.)

For example:

```yaml
metrics:
  datadog:
    enabled: true
    tags:
      tag1: value1
      tag2: value2
```

Will add the following to the `DD_TAGS` environment variable in the
Datadog sidecar:

    tag1:value1,tag2:value2

## ports

| **Type** | **Required** |
|----------|--------------|
| list     | no           |

List of ports the application listens for requests.

Default value:
```yaml
ports:
  - protocol: http
    name: http
    port: 80
    target_port: 8080
```

### protocol
| **Type** | **Required** |
|----------|--------------|
| string   | no          |

Protocol used by the application. It must be `http` or `tcp`.

### name
| **Type** | **Required** |
|----------|--------------|
| string   | no           |

A logical name for port discovery. Must be <= 63 characters and match `[a-z0-9]([-a-z0-9]*[a-z0-9])?`.

### port
| **Type** | **Required** |
|----------|--------------|
| int      | no          |

Port number that will be exposed. For protocol equals TCP the available port range is (1024-32767) (may vary depending
on the configuration of the underlying Kubernetes cluster).

### target_port
| **Type** | **Required** |
|----------|--------------|
| int      | no          |

The port number which is exposed by the container and should receive traffic routed to `port`.


## annotations

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

This configuration structure can be used to set custom annotations on the Kubernetes resources which are
created or updated when deploying the application.

Default value:
```yaml
annotations:
  deployment: {}
  horizontal_pod_autoscaler: {}
  ingress: {}
  service: {}
  pod: {}
```

The annotations are organized under the Kubernetes resource they will be applied to. To specify custom anotations, set
key-value pairs under the respective Kubernetes resource name. I.e. to set the label `foo=bar` on the Service
object, you can do the following:

```yaml
annotations:
  service:
    foo: bar
```

Annotations are fundamentally different from labels in that labels are primarily used to organize and select
resources, whereas annotations are more suitable for applying generic metadata to resources. This metadata can in turn
be read and used by other systems running in the cluster. Refer to the
[Kubernetes documentation on annotations](https://kubernetes.io/docs/concepts/overview/working-with-objects/annotations/) for
more information.


## labels

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

Default value:
```yaml
labels:
  deployment: {}
  horizontal_pod_autoscaler: {}
  ingress: {}
  service: {}
  pod: {}
```

The labels are organized under the Kubernetes resource they will be applied to. To specify custom labels, set
key-value pairs under the respective Kubernetes resource name. I.e. to set the label `layer=frontend` on the Service
object, you can do the following:

```yaml
labels:
  service:
    layer: frontend
```

Labels have strict syntax requirements for both the key and value part. Refer to the [Kubernetes documentation on
labels and selectors](https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/) for details.


## secrets_in_environment

| **Type** | **Required** |
|----------|--------------|
| boolean  | no           |

Any Kubernetes secret matching the application name will automatically be mounted under `/var/run/secrets/fiaas/`. If
this setting is enabled, any key-value pairs from the same secret will also be available as environment variables in
the application's environment.

Default value:
```yaml
secrets_in_environment: false
```


## admin_access

| **Type** | **Required** |
|----------|--------------|
| boolean  | no           |

Controls whether or not Kubernetes apiserver tokens from the `default` `ServiceAccount` in the namespace the application
is deployed to will be mounted inside the pods. This is only neccessary if the application requires access to the
Kubernetes apiserver. If in doubt, leave this disabled.

```yaml
admin_access: False
```


## extensions

### secrets

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

Configuration for pulling secrets from arbitrary sources before application startup. The keys of this
object should be the 'type' of secret init-container that has been registered in the cluster
(using `--secret-init-containers`).
The init-container can be configured using 'parameters', which will be available inside the container as
Environment Variables; and/or 'annotations', which will be added to the annotations present in the pod.

If no value is provided here, and a 'default' init-container is registered in the cluster it will be used
for the application.

The init-container should make secrets available as files under `/var/run/secrets/fiaas`. Any additional structure
or convention will depend on the init-container being used.

Example (Note: the specific structure of this will depend on the configuration of FIAAS in your cluster/namespace):
```yaml
extensions:
  secrets:
    parameter-store:
      parameters:
        AWS_REGION: eu-west-1
        SECRET_ID: somesecret
      annotations:
        iam.amazonaws.com/role: arn:aws:iam::12345678:role/the-role-name
```

### strongbox

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

Configuration from pulling secrets from [Strongbox](https://schibsted.github.io/strongbox/) before application
startup. Secrets will be made available as files under `/var/run/secrets/fiaas`, each secret in each secret group
being stored under `/var/run/secrets/fiaas/$group_name/$secret_name`.

Default values:
```yaml
extensions:
  strongbox: # This is only enabled if fiaas-deploy-daemon runs with --strongbox-init-container-image set
    iam_role: # AWS IAM role assumed before pulling secrets from Strongbox
    aws_region: eu-west-1 # AWS region to get Strongbox secrets from
    groups: [] # Strongbox secret groups. Will get all secrets present in each group
```

#### iam_role

| **Type** | **Required** |
|----------|--------------|
| string   | no           |

The [ARN](https://docs.aws.amazon.com/general/latest/gr/aws-arns-and-namespaces.html#arn-syntax-iam) for the AWS IAM
role which should be assumed before pulling secrets from Strongbox. This role will need read access to the secrets you
want to get.

Required to get secrets from Strongbox.

#### aws_region

| **Type** | **Required** |
|----------|--------------|
| string   | no           |

The AWS region to pull Strongbox secrets from. Defaults to `eu-west-1`.

#### groups

| **Type** | **Required** |
|----------|--------------|
| list     | no           |

List of Strongbox Secret Groups to pull secrets from. All secrets from each group will be pulled.

Required to get secrets from Strongbox.


Example:
```yaml
extensions:
  strongbox:
    iam_role: arn:aws:iam::12345678:role/the-role-name
    aws_region: eu-west-1
    groups:
    - group-name-1
    - group-name-2
```

### tls

#### enabled

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

If enabled, ingress objects will be extended to include annotations necessary for use with
[cert-manager](https://github.com/jetstack/cert-manager)s [ingress-shim](https://cert-manager.readthedocs.io/en/latest/reference/ingress-shim.html)
to make use of automatic provisioning and management of TLS certificates.

If certificate_issuer is set, generated ingress objects will be extended to include annotations specifying which certificate issuer to use with
cert-manager.

Example:
```yaml
extensions:
  tls:
    enabled: true
    certificate_issuer: letsencrypt
```

Note generally fiaas operators will have already configured a default certificate issuer if applicable so the option to specify that explicitly
is strictly here for allowing for overwriting of the default value and if omitted will use the configured default value.
