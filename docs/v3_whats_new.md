# What's new in FIAAS configuration format version 3

The FIAAS configuration format version 3 is the new and improved way to configure the infrastructure needs of your
application when deploying to Kubernetes with FIAAS.

See also [the defaults.yml for version 3](/fiaas_deploy_daemon/specs/v3/defaults.yml).

## version 3

| **Type** | **Required** |
|----------|--------------|
| int      | yes          |

Version 3 is the new version. To use the features described below, it is neccessary to set `version: 3`.

```yaml
version: 3
```

## namespace removed

The namespace field has been removed from the FIAAS configuration format.

We want to promote good continuous delivery practice by promoting a version of an application through a set of
environments and finally to production. In this context an environment can mean a different namespace, which would
mean that we realistically would need different FIAAS configuration files per environment. This would negate the
benefit of promoting the same version across environments, since the infrastructure configuration from the FIAAS
config file could be different. To avoid this, the namespace (environment) should not be a parameter of the FIAAS
configuration file, but should rather originate from elsewhere.


## replicas and autoscaler merged into replicas

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

The `replicas` and `autoscaler` fields have now been merged into a single configuration object named `replicas`.

New defaults:
```yaml
replicas:
  minimum: 2
  maximum: 5
  cpu_threshold_percentage: 50
```

This is equivalent to the following configuration in `version: 2`.

```yaml

replicas: 5
autoscaler:
  enabled: true
  min_replicas: 2
  cpu_threshold_percentage: 50
```

Autoscaling via a HorizontalPodAutoscaler is now the default behavior. To disable autoscaling, set `replicas.minimum ==
replicas.maximum`. The following configuration will result in a Deployment with 2 replicas, and no HorizontalPodAutoscaler.

```yaml
replicas:
  minimum: 2
  maximum: 2
```

## host and path merged into ingress

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

`host`, previously a top-level field, and `path`, previously a field on the `ports` configuration object, are now
merged together in the `ingress` configuration object.
This change allows more flexibility for achieving complicated request routing patterns, e.g. when an application
listens to a lot of paths on the same host, listens for requests to different paths on multiple hosts, or exposes
different paths on different ports.

New defaults:
```yaml
ingress:
  - host: # Not set
    paths:
    - path: /
      port: http
```

In version 3, the following configuration exposes `myapp.example.com/endpoint/for/things`:

```yaml
ingress:
  - host: myapp.example.com
    paths:
      - path: /endpoint/for/things
```

Which is equivalent to the following configuration in v2

```yaml
host: myapp.example.com
ports:
  - path: /endpoint/for/things
```

Since ingress.paths is now a list, where one previously had to (ab)use regular expressions to support multiple
explicitly configured paths, one can now configure each path as an element in the list:

```yaml
ingress:
    host: myapp.example.com
    paths:
      - path: /endpoint/for/things
      - path: /stuff
      - path: /other/things
```

It is also possible to specify different ports for different paths:

```yaml
ingress:
    host: myapp.example.com
    paths:
      - path: /endpoint/for/things
      - path: /stuff
      - path: /other/things
        port: other
ports:
  - protocol: http
    name: main
  - protocol: http
    name: other
    port: 81
    target_port: 8081
```

## new default http healthcheck paths

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

To indicate that it is a good idea to have an explicit well considered endpoint for liveness and readiness checks used
by Kubernetes, the default paths for the http liveness and readiness checks have been changed from `/` to `/_/health`
and `/_/ready`, respectively. This is to match the
[draft application endpoint proposal](https://confluence.schibsted.io/display/SPTINF/Application+Endpoint+Proposal).

New defaults:
```yaml
healthchecks:
  liveness:
    http:
      path: /_/health
  readiness:
    http:
      path: /_/ready
```

Otherwise, the healthcheck parameter defaults remain unchanged.


## default value for resource

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

Well-thought out explicit resource requests and limits per application are important. It results in better
reliability, better QoS for more important applications should resource starvation occur, and it makes scheduling more
efficient. For this reason, `resource.limits` and `resource.requests` now have default values. These defaults are set
relatively conservatively to encourage developers to consider their application's resource usage and adjust these
parameters accordingly.

New defaults:
```yaml
resources:
  limits:
    cpu: 400m
    memory: 512Mi
  requests:
    cpu: 200m
    memory: 256Mi
```

For more details on how this actually works, refer to the Kubernetes documentation for how to
configure [cpu](https://kubernetes.io/docs/tasks/configure-pod-container/assign-cpu-resource/)
and [memory](https://kubernetes.io/docs/tasks/configure-pod-container/assign-memory-resource/) resources for applications.


## prometheus moved under metrics

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

There is a new top-level configuration object called `metrics`. The previously top-level configuration object
`prometheus` is now moved as a field under this object. This will make it easier to add support for other metrics
systems in the future without breaking backwards compatibility.
At the same time, the default path for the metrics endpoint has been changed to `/_/metrics` to match the new
healthcheck default paths.

New defaults:
```yaml
metrics:
  prometheus:
    enabled: true
    port: http
    path: /_/metrics
```

## config configuration object removed

If there is a ConfigMap matching the name of the application in the namespace an application is deployed to, it will
be mounted as a volume automatically, and key/value pairs in the ConfigMap will be available in the application's
environment by default.
Since this is now the default behavior, the top-level `config` configuration object has been removed.

## has_secrets renamed to secrets_in_environment, new default behavior

| **Type** | **Required** |
|----------|--------------|
| boolean  | no           |

If there is a Secret matching the name of the application in the namespace an application is deployed to, it will be
mounted as a volume automatically. This is now default behavior.  The top-level `has_secrets` configuration flag has
been replaced with a new flag named `secrets_in_environment`, which is a boolean flag indicating whether any key/value
pairs in the mounted Secret volume shall also be available in the application's environment.

New defaults:
```yaml
secrets_in_environment: false
```

## Support for custom labels

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

It is now possible to configure custom labels on the Kubernetes resources created when deploying an application. The
default is no additional labels.

```yaml
labels:
  deployment: {}
  horizontal_pod_autoscaler: {}
  ingress: {}
  service: {}
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

## Support for custom annotations

| **Type** | **Required** |
|----------|--------------|
| object   | no           |

It is now possible to configure custom annotations on the Kubernetes resources created when deploying an application. The
default is no additional annotations.

```yaml
annotations:
  deployment: {}
  horizontal_pod_autoscaler: {}
  ingress: {}
  service: {}
```

Like labels, annotations are organized under the Kubernetes resource they will be applied to. To specify custom
annotations, set key-value pairs under the respective Kubernetes resource name. I.e. to set the annotation `foo=bar`
on the Deployment object, you can do the following:

```yaml
annotations:
  deployment:
    foo: bar
```

Annotations are fundamentally different from labels in that labels are primarily used to organize and select
resources, whereas annotations are more suitable for applying generic metadata to resources. This metadata can in turn
be read and used by other systems running in the cluster. Refer to the
[Kubernetes documentation on annotations](https://kubernetes.io/docs/concepts/overview/working-with-objects/annotations/) for
more information.
