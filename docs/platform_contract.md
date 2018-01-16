# FIAAS platform contract

## Supported kubernetes versions

| **version** | **manifest deployment target** |
|-------------|--------------------------------|
| 1.6.0       | [Third Party Resource](https://kubernetes.io/docs/tasks/access-kubernetes-api/extend-api-third-party-resource/) |
| 1.7.0       | [Third Party Resource](https://kubernetes.io/docs/tasks/access-kubernetes-api/extend-api-third-party-resource/) and [Custom Resources](https://kubernetes.io/docs/concepts/api-extension/custom-resources/) |
| 1.8.0       | [Custom Resources](https://kubernetes.io/docs/concepts/api-extension/custom-resources/) |

## Noteable kubernetes features in use

| **FIAAS field** | **kubernetes entity** |
|-----------------|-----------------------|
| [replicas](/docs/v3_spec.md#replicas) | [HorizontalPodAutoscaler](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/) if `max > min` |
| [ingress](/docs/v3_spec.md#ingress) | [ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/) |
| [healthchecks](/docs/v3_spec.md#healthchecks) | [pod live-/ready-ness probe](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-probes/) |
| [resources](/docs/v3_spec.md#resources) | [pod resources](https://kubernetes.io/docs/concepts/configuration/manage-compute-resources-container/) |
| [metrics](/docs/v3_spec.md#metrics) | Resolves to annotations [example configuration](https://github.com/prometheus/prometheus/blob/master/documentation/examples/prometheus-kubernetes.yml) |

### Conventions for secrets

[Secrets](https://kubernetes.io/docs/concepts/configuration/secret/) in the same namespace as your application with the same name as the application gets mounted into `/var/run/secrets/fiaas/`. The same logic is there for ConfigMaps, mounting them into `/var/run/config/fiaas/`.

### Conventions for config maps

[ConfigMaps](https://kubernetes.io/docs/tasks/configure-pod-container/configmap/) gets injected as key/value environment variables automatically while for secrets there is a [flag](/docs/v3_spec.md#secrets_in_environment) for that.


## Cluster contract

You will need a functioning kubernetes cluster to use FIAAS, with at least networking and an ingress controller.

Required cluster addons are:

* Heapster is required for autoscaling, and it must be deployed in the kube-system namespace
* kube-dns/coredns this is neccessary for service discovery

Additionally, cluster level services that are not techincally addons:
* Fluentd configured to route logs to some log aggregation service is required for log aggregation
* A prometheus instance that runs in the cluster so that it is able to use kubernetes service discovery and scrape pods directly is required for prometheus metrics.
### Networking

[Flannel](https://kubernetes.io/docs/concepts/cluster-administration/networking/#flannel) is a good place to start if you don't have any particular preference, but any network endorsed by kubernetes should work just fine.

### Ingress controller

You will need to run an ingress controller in your cluster in order to get a cluster compliant with FIAAS. A good place to start is with [NGINX Ingress Controller](https://github.com/kubernetes/ingress-nginx#nginx-ingress-controller).


### Load balancing

There needs to be a load balancer that can reach the [ingress](https://kubernetes.io/docs/concepts/services-networking/ingress/) controller in the kubernetes cluster. The [host field](https://github.schibsted.io/finn/fiaas-deploy-daemon/blob/master/docs/v3_spec.md#host) in the fiaas.yml needs to be created as a DNS entry that points to the load balancer. You will only see the page when using that name in the requests you do, because the ingress controller directs traffic based on the host field.




