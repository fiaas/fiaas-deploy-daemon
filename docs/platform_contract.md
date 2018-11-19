# FIAAS platform contract

FIAAS provides a platform for applications, which makes it easier to focus on business logic instead of integrating with the underlying infrastructure. In order to do this, FIAAS has a set of contracts that must be fulfilled so that the platform looks the same in all installations. Some details will not abstracted away in the current implementation, but the platform contracts will continually evolve to include more and more of these details. 

Since FIAAS sits in the middle between the cluster and the application, there are contracts on both sides. There are expectations between FIAAS and the cluster, and between FIAAS and the applications. Many of the things FIAAS promises to applications depend on the cluster to provide systems that solve that need.

The [Operators guide](operator_guide.md) documents what cluster operators need to do in order to make their cluster work with FIAAS, this document will focus on the interactions between FIAAS and the applications. 

## Supported kubernetes versions

| **version** | **manifest deployment target** |
|-------------|--------------------------------|
| 1.6.0       | [Third Party Resource](https://kubernetes.io/docs/tasks/access-kubernetes-api/extend-api-third-party-resource/) |
| 1.7.0       | [Third Party Resource](https://kubernetes.io/docs/tasks/access-kubernetes-api/extend-api-third-party-resource/) and [Custom Resources](https://kubernetes.io/docs/concepts/api-extension/custom-resources/) |
| 1.8.0       | [Custom Resources](https://kubernetes.io/docs/concepts/api-extension/custom-resources/) |
| 1.9.0       | [Custom Resources](https://kubernetes.io/docs/concepts/api-extension/custom-resources/) |
| 1.10.0      | [Custom Resources](https://kubernetes.io/docs/concepts/api-extension/custom-resources/) |

## Notable kubernetes features in use

| **FIAAS field** | **kubernetes entity** |
|-----------------|-----------------------|
| [replicas](/docs/v3_spec.md#replicas) | [HorizontalPodAutoscaler](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/) if `max > min` |
| [ingress](/docs/v3_spec.md#ingress) | [ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/) |
| [healthchecks](/docs/v3_spec.md#healthchecks) | [pod live-/ready-ness probe](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-probes/) |
| [resources](/docs/v3_spec.md#resources) | [pod resources](https://kubernetes.io/docs/concepts/configuration/manage-compute-resources-container/) |
| [metrics](/docs/v3_spec.md#metrics) | Resolves to annotations [example configuration](https://github.com/prometheus/prometheus/blob/master/documentation/examples/prometheus-kubernetes.yml) |

## What applications can expect

### Secrets and configuration

Secrets and configuration is handled in much the same way.

[Secrets](https://kubernetes.io/docs/concepts/configuration/secret/) will be exposed to the application as a read-only volume, mounted at `/var/run/secrets/fiaas/`. If using Strongbox, the secrets will be grouped in directories under the same path. Each secret will be a file, where the value of the secret is the contents of the file.
 
If FIAAS is configured to use plain Kubernetes secrets, it is also possible to request that secrets are exposed in the applications environment. This is not possible for the other secret sources, because they rely on init containers to fetch the secrets, and they can't add to the environment. It is possible to write startup scripts in the application container that can expose the files as environment variables.

Configuration in the form of [ConfigMaps](https://kubernetes.io/docs/tasks/configure-pod-container/configure-pod-configmap/) will be exposed in the same way, at `/var/run/config/fiaas/`, each key will be a file, where the value will be the file contents. Keys in the ConfigMap will also be exposed in the application environment automatically, but keep in mind that keys that are invalid will be skipped.

### Environment variables

FIAAS will set the following environment variables for your application:

* `ARTIFACT_NAME`: The name of your application. 
* `IMAGE`: The currently running container image.
* `VERSION`: The version (the part after `:` in the `IMAGE`). 
* `FIAAS_ENVIRONMENT`: If FIAAS is configured with a name for the environment, this is reflected here.
* `FIAAS_REQUESTS_CPU`: The requested CPU. 
* `FIAAS_REQUESTS_MEMORY`: The requested memory. 
* `FIAAS_LIMITS_CPU`: The CPU limit. 
* `FIAAS_LIMITS_MEMORY`: The memory limit. 
* `FIAAS_NAMESPACE`: The namespace you are in. 
* `FIAAS_POD_NAME`: The name of this pod. 
* `LOG_STDOUT`: Always `true`. Use this to allow applications to switch between file on legacy and stdout on FIAAS, by setting it to `false` in legacy deployments.
* `LOG_FORMAT`: The recommended logging format. Valid values are `json` or `plain`. Should be synced with the rest of the logging infrastructure. The value is copied from the configuration of fiaas-deploy-daemon itself.  

In addition, these environment variables are also set, but they are deprecated and should not be used. Some of them only make sense in the FINN cluster.

* `FIAAS_INFRASTRUCTURE`: The underlying infrastructure, either diy for on-premise, or gke for GKE clusters. 
* `CONSTRETTO_TAGS`: A comma separated string listing possible configuration sections to apply. If no environment is configured, will be set to `kubernetes`. If environment is configured, will be set to: `kubernetes-${FIAAS_ENVIRONMENT},kubernetes,${FIAAS_ENVIRONMENT}`. 
* `FINN_ENV`: A copy of `FIAAS_ENVIRONMENT`.

Finally, the cluster operator may set a number of global environment variables, which will be directly exposed to your application.
Currently those are exposed both under the name given by the operator, but also with a `FIAAS_` prefix. This might change in the future.

## What FIAAS expects from the application

In order to deploy an application, FIAAS needs three pieces of information: The name of the application, a container image, and a [FIAAS configuration](v3_spec.md).

Once deployed, the application is expected to send logs to stdout (as indicated by the `LOG_STDOUT` environment variable). It is expected to have a liveness check and a readiness check as defined in the configuration.

When interacting with other services, it should call the other service using only the name of the application, and let Kubernetes resolve the DNS lookup.

As many of the [12 factors](https://12factor.net/) as possible should be followed, making exceptions where it makes sense.

It should use `/tmp` for temporary files on disk, but always remember that the contents of the disk can be wiped on restart. The application should not get into trouble if it is suddenly killed. It should preferably scale by having more instances rather than bigger instances.
