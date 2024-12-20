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
FIAAS Operator Guide
====================

This document is for cluster operators who wish to install FIAAS in their cluster, so that users can use FIAAS when deploying applications. There is several configurable features in FIAAS, and this document will try to explain how they work, and what you need to do in order to make use of them.

All configuration options have associated help-text in the fiaas-deploy-daemon CLI. Getting the latest help-text can be done using this command:

    docker run --rm fiaas/fiaas-deploy-daemon:development fiaas-deploy-daemon --help

Note: the `development` container image tag is built from the most recent commit on the `master` branch and is only intended for testing.


The Basics
----------

In order for FIAAS to function in a cluster, some basics needs to be in place

* Autoscaling based on CPU metrics requires the metrics API (provided by Heapster or metrics-server)
* Applications expect DNS to work, so kube-dns, coredns or an equivalent substitute should be installed
* Log aggregation, so that stdout and stderr from applications are collected and aggregated and collected somewhere it can be found. Typically Fluentd collecting and sending to a suitable storage.
* An ingress controller capable of handling all the required features
* One or more DNS wildcards that will direct traffic to the ingress controller (see the [--ingress-suffix](#ingress-suffix) option)

In addition, some conventions might be useful to know about:

* In fiaas.yml v3, the default paths for probes and metrics starts with `/_/`. As a cluster operator, it might be useful to configure your cluster to disallow public access to any path that starts with this prefix.

How to set configuration options
--------------------------------

Configuration can be given on the commandline, as environment variables or in a configuration file. The typical use will be to create a ConfigMap object in Kubernetes, which will be mounted automatically when deploying fiaas-deploy-daemon using the supported deployment options.

The ConfigMap should contain a key named `cluster_config.yaml`, which is a YAML formatted configuration file. All long options can be a key in that file. See further details in the end of the help-text from fiaas-deploy-daemon.

Deeper explanation of options
-----------------------------

In the below text, we will explain some of the options, and how they affect your applications, and what you as a cluster operator needs to do in order to use them. Some options are fully described by their help-text, and won't be described here.

### log-format

The log format has very little practical effect unless your applications take advantage of it. This setting controls two things:

1. The log format used by fiaas-deploy-daemon itself
2. The value of the `LOG_FORMAT` environment variable passed to applications

If the value is `json`, applications should adhere to a common set of keys and value types, in order for log aggregation solutions to give a better experience.

Related to log format is the environment variable `LOG_STDOUT`, which is currently hardcoded to `true` for all applications deployed by FIAAS.

The combination of `LOG_STDOUT` and `LOG_FORMAT` can be used to allow applications to switch logging setup when deployed in FIAAS, to cater for different setups in legacy deployments.

### proxy

Use a http proxy for outgoing http requests. This is currently only used for for usage reporting.

### environment

Typical values are `dev`, `pre`, `pro`. It has no effect on fiaas-deploy-daemon, but is propagated to applications in the form of the environment variable `FIAAS_ENVIRONMENT`.

### service-type

Service objects can have a number of types in Kubernetes. This option decides which type, so that you can adapt the services to how the rest of your infrastructure integrates with your Kubernetes cluster. Read more about service types in the [Kubernetes documentation](https://kubernetes.io/docs/concepts/services-networking/service/#publishing-services-service-types)

### infrastructure

This is currently only used for FINN, and will go away soon.

### secret-init-containers, secrets-init-container-image, secrets-service-account-name and strongbox-init-container-image

Used to implement an init-container that will get secrets from some backend and make them available to the application. Read the section about [Secrets](#secrets)

### datadog-container-image

Used when collecting metrics to DataDog. See [Metrics](#metrics).

### datadog-activate-sleep

Flag to set a Lifecycle in the datadog container with a preStop that will execute a sleep of the pre-stop-delay of the main container plus 5 seconds.

### pre-stop-delay

When Kubernetes wants to terminate a pod, multiple things happen. For the purposes of this explanation, we can consider two "chains" of events that are triggered by Kubernetes when a pod is being shut down. Both chains are triggered/started at the same time, and run independently.

The first chain is the removal from load balancers. This starts with the pod being removed from the list of endpoints registered for the service. Once the ingress controller notices this change, it must remove the endpoint from its list of backends and reload the configuration. How quickly the change in endpoints propagate to all watchers is dependent on a number of things in how the cluster is configured, and how quickly an ingress controller will react to such a change varies depending on which ingress controller is in use. Some clusters manage this chain in a few seconds, others need over half a minute to remove a pod from the load balancer.

The second chain is the termination of the pod. This starts by executing any pre-stop handlers defined for the pod and waiting for them to complete. After that, all containers are sent the SIGTERM signal. After the "termination grace period" (which defaults to 30 seconds), containers are sent a SIGKILL.

The upshot of this is that applications that quickly react to SIGTERM and exits cleanly might still be receiving traffic, leading to disconnects or connection refused for the clients until the ingress controller catches up.

As a way to mitigate this, the pre-stop-delay introduces a sleep in the shutdown sequence of applications, which will allow other cluster components time to take the instance out of rotation before it shuts down. This requires that a `sleep` binary is available in the running container. The value to use depends on a number of components in your cluster, so you should tune it to your needs.



### ingress-suffix

When creating Ingress objects for an application, a host may be specified, which will be used to match the request with the application. For each ingress suffix specified in the configuration, a host section is generated for the application in the form `<application name>.<ingress suffix>`. If the application specifies a `host` in its configuration, a section for that host will be generated *in addition* to the sections generated for each ingress suffix.

As a cluster operator, it is your responsibility to create the needed DNS entries that point to your ingress controller. You can have as many DNS suffixes as you like, but keep in mind that the ingress controller needs to handle the number of hosts this generates. The easiest way to do this is to use DNS wildcards.

### host-rewrite-rules

An application has the option of specifying a `host` in its configuration. This host should be the production host to use for your application. In order to support extra environments (like dev and pre), a number of host-rewrite-rules may be specified. Each rule consists of a regex pattern, and a replacement value. The `host` is matched against each pattern in the order given, stopping at the first match. The replacement can contain groups using regular regex replace syntax. Regardless of how a rule is passed in (option, environment variable or in a config file), it must be specified as `<pattern>=<replacement>`. In particular, be aware that even if it would be natural to use the map type in YAML, this is not possible. See <https://docs.python.org/2.7/library/re.html#regular-expression-syntax>.

An example of rules to use in a dev environment:

* If the host value starts with www, replace it with the environment name. So www.site.com becomes dev.site.com.
* If the host value starts with anything else, prefix it with the environment name. So example.com becomes dev.example.com.

In order for this to work DNS entries for the resulting hosts needs to be created. They can usually be CNAME entries pointing to your DNS wildcards (See [ingress-suffix](#ingress-suffix))

### global-env

If you wish to expose certain environment variables to every application in your cluster, define them here. Regardless of how a variable is passed in (option, environment variable or in a config file), it must be specified as `<key>=<value>`.

### use-ingress-tls

Used to extend ingress configuration when deploying applications to enable automatic provisioning and management of certificates for the ingress resources created. This requires infrastructure such as kube-lego/cert-manager to be in place for provisioning of certificates.

Possible values:

* `disabled` (default)
* `default_off`
* `default_on`

If `disabled` or no value is specified no tls configuration is applied. This is the default behaviour.

If `default_off` tls configuration can be explicitly requested on a per application basis through application manifests.

If `default_on` tls configuration will be applied unless explicitly disabled in application manifests.

### tls-certificate-issuer-*

Used to configure how the ingress will be annotated for issuing a TLS certificate using cert-manager:

* `tls-certificate-issuer` sets the _value_ of the annotation, for example to decide between production and staging versions of an issuer in different namespaces
* `tls-certificate-issuer-type-default` sets the default for the _key_ of the annotation, for example to use either `certmanager.k8s.io/cluster-issuer` (the default) or `certmanager.k8s.io/issuer`
* `tls-certificate-issuer-type-overrides` allows specifying a mapping between the suffix of a domain and the issuer-type, to override the default. For example, assuming the 'cluster-issuer' type as the default, then specifying `--tls-certificate-issuer-type-overrides foo.example.com=certmanager.k8s.io/issuer` would mean that foo.example.com and any of its subdomains will use the 'issuer' type instead. In the case of multiple matching suffixes, the more specific (i.e. longest) will be used.
* `tls-certificate-issuer-overrides` allows specifying a mapping between the suffix of a domain and the issuer-name, to override the default. For example, assuming the 'letsencrypt' issuer name as the default, then specifying `--tls-certificate-issuer-type-overrides foo.example.com=issuer-2` would mean that foo.example.com and any of its subdomains will use the 'issuer-2' as issuer name instead. In the case of multiple matching suffixes, the more specific (i.e. longest) will be used.

### use-in-memory-emptydirs

Inside the container, `/tmp` will be mounted from an emptyDir volume, to allow applications some scratch-space without writing through the underlying docker storage driver. Similarly, when using the [Secrets init container](#secrets-init-container), the secrets are written to an emptyDir volume.

Normally, these volumes would use the nodes underlying disk, and can be recovered after a node restart. By enabling this option, these emptyDirs will instead be backed by memory. The memory used goes against the container memory limits, and will not survive a node restart.

See the Kubernetes documentation about [emptyDir](https://kubernetes.io/docs/concepts/storage/volumes/#emptydir) for more information about how emptyDirs work.


### usage-reporting-cluster-name, usage-reporting-provider-identifier, usage-reporting-endpoint, usage-reporting-tenant

Used to configure [Usage Reporting](#usage-reporting).

### extension-hook-url

Used to configure the extension hook url.

The idea is to be able to modify the kubernetes objects with an external service before arriving to the cluster.

The url should be a root that will be completed with `/fiaas/deploy/{objectName}`. This object name can be `Ingress`, `Deployment`, `Service` or `HorizontalPodAutoscaler`.

If the url returns 404, the object will not be modified. In case of 200, the object will be modified with the object returned. In other case, the deployment will fail.

The payload sent will be:
```
{
  "object": Deployment/HorizontalPodAutoscaler/Ingress/Service object
  "application": app_config
```
The response will be the same object type that you sent modified.

As we decided to treat the 404 as a valid response, we have no way to differentiate between an object name not supported by the extension service or a wrong path.

### enable-service-account-per-app

Used to create a serviceaccount for each deployed application, using the application name. If there are imagePullSecrets set on the 'default' service account, these are propagated the per-application service accounts. If a service account with the same name as the application already exists, the application will run under that service account but FIAAS will not overwrite/manage the service account.

### disable-crd-creation

By default fiaas-deploy-daemon updates the Application and ApplicationStatus CRDs on startup. CRDs are cluster scoped, so it is only necessary for one fiaas-deploy-daemon instance in a cluster to manage the CRDs. This flag can be used to disable updating of the CRDs per fiaas-deploy-daemon instance when not needed.
It is a good idea to keep the flag enabled on at least one fiaas-deploy-daemon instance in a cluster, otherwise you have to manually ensure that the Application and ApplicationStatus CRDs are present and up to date in the cluster.

### include-status-in-app

By default, fiaas-deploy-daemon will create an ApplicationStatus resource to hold the status/result when a deploy is triggered by an Application resource's `fiaas/deployment_id` label being updated.

When `include-status-in-app` enabled, the `status` subresource of Application resources triggering deploys will be updated with `result` and `logs`, in addition to the updates to ApplicationStatus resources as the deploy progresses. While the structure is similar to the ApplicationStatus resource, there are some differences:

- `.status.deployment_id` will be set to the value of the `fiaas/deployment_id` label, and `.status.observedGeneration` will be set to the value of `.metadata.generation` on the Application resource update which triggered the deploy. External systems triggering deploys and observing the current state should use these fields to correlate results to the related update/`deployment_id`.
- If multiple deploys are triggered by updates to the same Application resource in close succession, updates to the `.status` key for in-progress deploys other than the most recently triggered deploy *for the same application* may not be written to the `.status` key of the Application resource. ApplicationStatus resources corresponding to these deploys will however be updated as usual. See [#211 (comment)](https://github.com/fiaas/fiaas-deploy-daemon/pull/211#discussion_r1377335846) for more details.
- The `.status.logs` key will only contain log entries logged with `ERROR` level (if any).

This feature is disabled by default.

### pdb-max-unavailable

By default, PDB will be set with maxUnavailable = 1 in case the deployment has more than 1 replica. This parameter allows to change that value either with another int value or with a string percentage (i.e. "20%"). Recommendation is some low value like 10% to avoid issues. Also in case of a number, something below min_replicas should be used to allow evictions.

### pdb-unhealthy-pod-eviction-policy
This option is useful for avoiding operational problems, with node rotations, when there exists deployments with only unhealthy pods. This can be useful in dev clusters which have deployment with only unhealthy pods or in production clusters where the applications tolerate unhealthy pods being disrupted, while new pods are being started.

This option Controls when unhealthy running pods can be evicted. The default 'IfHealthyBudget' allows eviction only if enough healthy pods are available to maintain the desired count of healthy pods. 'AlwaysAllow' permits eviction of unhealthy running pods even if doing so would leave fewer pods than desired temporarily.

[Kubernetes documentation is available here.](https://kubernetes.io/docs/tasks/run-application/configure-pdb/#unhealthy-pod-eviction-policy)

### disable-service-links

By default, [enableServiceLinks](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.29/#podspec-v1-core) is set to true, which means that environment variables are automatically created for each service in the same namespace. This parameter allows you to disable this feature by setting disable-service-links to true. This can be useful in scenarios where you have a large number of services and you want to reduce the number of environment variables that are automatically created. For new installations, it's recommended to disable this feature to streamline the environment setup. However, for existing installations, proceed with caution when disabling this feature. This is due to potential compatibility issues, as some services might rely on these automatically created environment variables for communication.

### dns-search-domains

Additional search domains to put in the pod spec `dnsConfig.searches`. Empty by default.

Deploying an application
------------------------

To deploy an application with FIAAS, you need three things:

- A name for your application (Should follow the [Kubernetes conventions for names](https://kubernetes.io/docs/concepts/overview/working-with-objects/names/#names))
- A docker image reference
- A FIAAS configuration for your application (commonly referred to as `fiaas.yml`)

To deploy an application, create an Application object describing your application. A JSON schema describing the various objects FIAAS uses is in [schema.json](schema.json).

When you create or update your Application object, and at various intervals in between, fiaas-deploy-daemon will load the description of your application and create or update all relevant objects to match what is described in your Application. A requirement is that you also set a label on the Application named `fiaas/deployment_id` (the Deployment ID). This should reflect a particular deployment that is to be considered distinct from previous or later deployments. Typically this will change when you either change your image or your FIAAS config.

When you want to deploy a new version, you can in the simplest case update the `image` field and the Deployment ID label, and FIAAS will ensure a rolling deploy to the new image is performed. Making changes to the other fields in Application will likewise update the deployment.

When a deployment is running, fiaas-deploy-daemon will update a ApplicationStatus object that is specific for the specified Deployment ID. The status object indicates the current state of the deployment, as well as collect some relevant information.

Mast is an application you can install in your cluster, that provides a REST interface for creating Application objects. It does not currently support all features of the Application object, but we hope to expand it in the future. Mast also has a view for showing the status object related to a deployment, and can be a good starting point for those that want to create their own flow.

Two example Application definitions are included in the docs:

- [fiaas-deploy-daemon](crd/examples/fiaas-deploy-daemon.yaml)
- [nginx](crd/examples/nginx.yaml)

Secrets
-------

FIAAS supports different sources of secrets. All options will provide access to secrets in a pre-defined location, currently `/var/run/secrets/fiaas/`. This allows applications to assume their secrets are located at that path, regardless of where the secrets are sourced from.

### Kubernetes Secret

The default source is Kubernetes Secret objects. If a Secret with the same name as the application being deployed exists in the same namespace it is mounted in the container at a pre-defined location.

When using Kubernetes as a source of secrets it is possible to set the key `secrets_in_environment` in the application configuration to `true`, and each key-value pair in the Secret will be exposed as environment variables to your application. This flag is ignored for by other sources because of technical limitations.

### Using init-containers

Since Kubernetes Secrets are somewhat insecure, operators might want to use other options for storing secrets. There are 3 options to
allow images to be made available to application developers which will be run as an init-container before the application starts, in
order to allow for fetching secrets from a different location.

In all cases, the container will be responsible for getting the application secrets from whatever backend is used, and writing them to disk. The path `/var/run/secrets/fiaas` will be an "EmptyDir" with read/write permissions, which is then mounted with read-only permissions in the application container.

In the init container, the environment variable `K8S_DEPLOYMENT` will be the name of the application. In addition, any variables specified in a ConfigMap named `fiaas-secrets-init-container` will be exposed as environment variables.

The ConfigMap will also be mounted at `/var/run/config/fiaas-secrets-init-container/`. If there exists a ConfigMap for the application then it will be mounted at `/var/run/config/fiaas/`.

#### Secrets init container (--secrets-init-container-image)

This allows for a single image to be configured per-namespace, that will be attached to applications without them
having to configure anything.

If `secrets-service-account-name` is specified, the named service account will be mounted in the init container.

### Configurable secrets init containers (--secret-init-containers)

This allows for multiple images to be configured per-namespaces, and application developers can choose which
they wish to use, specify environment variables, and attach annotations to the pod.

The images should be registered with a 'type', e.g. `--secret-init-containers foosecrets=fiaas/some-foo-image:latest`, and this can
then be used by applications by specifying `extensions.secrets.foosecrets` in their configuration.

Any environment variables specified as `extensions.secrets.foosecrets.parameters` will be available, and any annotations
specified as `extensions.secrets.foosecrets.annotations` will be added to the pod.

Using the special value 'default' for the 'type' will mean the image will be attached when an application doesn't
specify any other secrets configuration.

### RoleBinding and ClusterRole Configuration (--list-of-cluster-roles --list-of-roles)

Enables the creation of a `RoleBinding`. If provided a list-of-cluster-roles, it will generate the `RoleBinding` with the kind `ClusterRole`. If provided a list-of-roles, it will generate the `RoleBinding` with the kind `Role`.
This is useful for when you wish all applications to have read access to specific resources. Also you will need to include the roles and rolebindings in the values.yaml file, under the keys `rbac.roleBinding.roles` and `rbac.roleBinding.clusterRoles`

##### List of ClusterRoles and Roles for Role Binding

- `--list-of-cluster-roles=["A", "B"]`: This flag allows the creation of `RoleBinding` objects with `ClusterRole` kind for the specified cluster-level roles.

- `--list-of-roles=["A", "B"]`: This flag allows the creation of `RoleBinding` objects with `Role` kind for the specified namespace-level roles.

#### Strongbox

In AWS you have the option of using [Strongbox](https://https://github.com/schibsted/strongbox) for your secrets. If you wish to use Strongbox, the configuration option `strongbox-init-container-image` should be set to an image that can get secrets from Strongbox. This option is very similar to the previous variant, except that Strongbox gets a few more pieces of information from the application configuration. The application must specify an IAM role, and can select AWS region and a list of secret groups to get secrets from.

The Strongbox init container is treated much the same as the previous variants, with two extra environment variables:

* `SECRET_GROUPS` is a comma separated list of secret groups from the application config
* `AWS_REGION` is the AWS region from the application config.

The secrets should be written to disk at the location `/var/run/secrets/fiaas/$group_name/$secret_name`.


Metrics
-------

There are two supported metrics solutions, Prometheus and Datadog. The cluster needs to provide one or both. Prometheus is the preferred solution.

### Prometheus

A Prometheus installation in the cluster, with ability to scrape all pods. It can optionally be installed in a per-namespace configuration, where each instance scrapes the pods in the same namespace. In this case, consider federation across instances.

### Datadog

In order to use DataDog in a namespace, a secret named `datadog` needs to be provisioned. The secret should have a single key, `apikey`, which is a valid DataDog API key. The cluster operator also needs to configure fiaas-deploy-daemon with a `datadog-container-image`, which will be attached as a sidecar on all pods to receive metrics and forward to Datadog.

The container will get these environment variables set:

* `DD_TAGS=app:<application name>,k8s_namespace:<kubernetes namespace>`
* `DD_API_KEY=<the "apikey" value from the "datadog" secret>`
* `NON_LOCAL_TRAFFIC=false`
* `DD_LOGS_STDOUT=yes`

It is designed to work with the `datadog/docker-dd-agent` container from [Datadog](https://github.com/DataDog/docker-dd-agent).


Usage Reporting
---------------

FIAAS can optionally report usage data to a web-service via POSTs to an HTTP endpoint. Fiaas-deploy-daemon will POST a JSON structure to the endpoint on deployment start, deployment failure and deployment success.

The JSON document contains details about the application being deployed, where it is deployed and the result of that deployment. In the future, we might consider implementing other formats.

Except where noted, FIAAS passes these values on to the collector without processing.

* `usage-reporting-cluster-name`: A string naming the cluster.
* `usage-reporting-operator`: A string identifying the operator of the fiaas-deploy-daemon instance
* `usage-reporting-team`: A string identifying the team responsible for the applications managed by the fiaas-deploy-daemon instance
* `usage-reporting-tenant`: A string identifying the operator reporting usage data. This will in many cases be the same operator, but the specification allows for different values here.
* `usage-reporting-endpoint`: Endpoint to POST usage data to
* `environment`: A string indicating the environment which the fiaas-deploy-daemon instances manages (`dev`, `pre`, `pro`)



Role Based Access Control (rbac)
--------------------------------

fiaas-deploy-daemon needs RBAC privileges to provision and manage various resource types in order to be able to create
and manage resources for applications that will be deployed. The RBAC privileges required to deploy applications in a
namespace can be seen in the [role.yaml](helm/fiaas-deploy-daemon/templates/role.yaml) helm template. By default
fiaas-deploy-daemon also requires privileges to manage (create and update) the Application and ApplicationStatus
CRDs. These privileges are defined in the
[`clusterrole_crd_manager.yaml`](helm/fiaas-deploy-daemon/templates/clusterrole_crd_manager.yaml) helm template.

When running many fiaas-deploy-daemon instances in different namespaces, you may want to consider having a single
fiaas-deploy-daemon instance manage the Application and ApplicationStatus CRDs. This can can be done by setting the
[`disable-crd-creation` flag](#disable-crd-creation) on all but the one fiaas-deploy-daemon instance that should
manage the CRDs. If you use the helm chart to manage RBAC resources for fiaas-deploy-daemon you can then also disable
creation of the clusterrole and associated clusterrolebinding for the instances with the `disable-crd-creation` flag
set by setting the `rbac.clusterRole.create` and `rbac.clusterRoleBinding.create` flags to false.

Migrating from using skipper to using the helm chart to deploy fiaas-deploy-daemon
----------------------------------------------------------------------------------

### Skipper is deprecated

Deploying fiaas-deploy-daemon via [skipper](https://github.com/fiaas/skipper) is deprecated. See issue #163 for some
background and discussion on this topic. If you are using skipper, you should consider switching to using the
fiaas-deploy-daemon helm chart to deploy fiaas-deploy-daemon directly.

You can install the latest release of fiaas-deploy-daemon with the default configuration by with helm.

```shell
helm repo add fiaas https://fiaas.github.io/helm
helm install fiaas/fiaas-deploy-daemon
```
Most likely you'll want to modify some of the default configuration. Take a look at the default values for the release
you're using.

### Migrating to deploying fiaas-deploy-daemon with helm

The steps required for migrating from skipper to the fiaas-deploy-daemon helm chart will vary depending on your
setup. The description below is kept at a high level and should only be considered rough guidance and not a complete
description of the required steps; use at your own risk.

Preparation:
For each namespace fiaas-deploy-daemon is currently deployed in via skipper:
- Ensure you have a set of helm values that will result in configuration for fiaas-deploy-daemon which is the same as
  your currently live configuration.

Migration process:
- Stop and uninstall skipper. If the `rbac.enableFIAASController` helm value is enabled in skipper (the default),
  uninstalling the skipper helm chart will remove the privileges needed for fiaas-deploy-daemon to deploy applications
  and manage its CRDs. It won't be possible to deploy applications until fiaas-deploy-daemon is uninstalled and then
  installed again via the helm chart in each namespace. The clusterrole created when `rbac.enableFIAASController` is
  enabled is quite permissive and is bound to `system:serviceaccounts` by default, so if that flag is enabled in your
  setup it can be a good idea to verify that no other workloads rely on privileges granted by that RBAC configuration
  before uninstalling skipper completely.

For each namespace fiaas-deploy-daemon is currently deployed in via skipper:
- Delete the Application resource named fiaas-deploy-daemon. This should uninstall fiaas-deploy-daemon in the namespace.
  It won't be possible to deploy applications until fiaas-deploy-daemon is installed again via the helm chart.
- If there is a fiaas-deploy-daemon serviceaccount, role and rolebinding in the namespace, and these are managed by
  skipper, and you want to use the fiaas-deploy-daemon helm chart to manage RBAC for fiaas-deploy-daemon, these
  resources can be deleted. The helm chart will re-create the serviceaccount, role and rolebinding. The role and
  rolebinding is created by skipper when it deploys fiaas-deploy-daemon and `enable-service-account-per-app` is enabled
  in the fiaas-deploy-daemon configmap in that namespace.
- Install fiaas-deploy-daemon via the helm chart.
- Delete the fiaas-deploy-daemon-bootstrap pod (if any). Skipper uses this pod to bootstrap fiaas-deploy-daemon into a
  namespace it isn't currently running in. Usually there is just a one-off pod in the `Completed` state, which can be
  deleted.

### Update fiaas-deploy-daemon version with skipper in "no-channel" mode

*The process described below is deprecated along with skipper, but should work until the fiaas-deploy-daemon-bootstrap
entrypoint in fiaas-deploy-daemon is removed. It is documented here mainly as a potential temporary workaround; do not
rely on this configuration as a long-term solution.*

It is possible to configure skipper in a "no-channel" mode to be able to update fiaas-deploy-daemon if you are unable to
complete the above migration first. In this mode the container image reference and fiaas.yml used to deploy any
fiaas-deploy-daemon in configured namespaces is explicitly configured at the skipper level. Skipper will not read the
`latest` and `stable` tags from the release repo, and will ignore the `tag` key set on fiaas-deploy-daemon
configmaps. Skipper will use the configured container image reference for all fiaas-deploy-daemon instances in the
cluster; it is not possible to specify different images for different fiaas-deploy-daemon instances.

To set up this configuration, specify the helm configuration values [`releaseChannelMetadata` and
`releaseChannelMetadataSpecContentAsYAML`](https://github.com/fiaas/skipper/blob/master/helm/fiaas-skipper/values.yaml#L64-L76)
when configuring skipper.

This example shows the mentioned values configured with the version the stable tag points to at the time of writing:
```yaml
releaseChannelMetadata:
  # This is the container image that will be used to run fiaas-deploy-daemon
  image: "fiaas/fiaas-deploy-daemon:20220307131421-31f12b3"
  # This file will contain the content of `releaseChannelMetadataSpecContentAsYAML`
  spec: "/var/run/config/fiaas/release_channel_metadata_spec_fiaas.yaml"
# The following is the fiaas.yml used by fiaas-deploy-daemon to deploy itself, copied from the `.spec` key of
# https://github.com/fiaas/releases/blob/master/fiaas-deploy-daemon/stable.json. Change it to suit your requirements
# if necessary.
releaseChannelMetadataSpecContentAsYAML: |-
  version: 3
  admin_access: true
  replicas:
    maximum: 1
    minimum: 1
  resources:
    requests:
      memory: 128Mi
  ports:
    - target_port: 5000
  healthchecks:
    liveness:
      http:
        path: /healthz
  metrics:
    prometheus:
      path: /internal-backstage/prometheus

```
