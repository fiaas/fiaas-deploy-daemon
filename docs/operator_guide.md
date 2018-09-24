FIAAS Operator Guide
====================

This document is for cluster operators who wish to install FIAAS in their cluster, so that users can use FIAAS when deploying applications. There is several configurable features in FIAAS, and this document will try to explain how they work, and what you need to do in order to make use of them.

All configuration options have associated help-text in the fiaas-deploy-daemon CLI. Getting the latest help-text can be done using this command:

    docker run --rm fiaas/fiaas-deploy-daemon:latest fiaas-deploy-daemon --help
    

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

This is currently only used for FINN, and will go away soon.

### environment

Typical values are `dev`, `pre`, `pro`. It has no effect on fiaas-deploy-daemon, but is propagated to applications in the form of the environment variable `FIAAS_ENVIRONMENT`.

### service-type

Service objects can have a number of types in Kubernetes. This option decides which type, so that you can adapt the services to how the rest of your infrastructure integrates with your Kubernetes cluster. Read more about service types in the [Kubernetes documentation](https://kubernetes.io/docs/concepts/services-networking/service/#publishing-services-service-types)

### infrastructure

This is currently only used for FINN, and will go away soon.

### secrets-init-container-image, secrets-service-account-name and strongbox-init-container-image

Used to implement an init-container that will get secrets from some backend and make them available to the application. Read the section about [Secrets](#secrets)

### datadog-container-image

If specified, apps that request datadog metrics will get this container as a sidecar. The container will get these environment variables set:

* `DD_TAGS=app:<application name>,k8s_namespace:<kubernetes namespace>`
* `API_KEY=<the "apikey" value from the "datadog" secret>`
* `NON_LOCAL_TRAFFIC=false`
* `DD_LOGS_STDOUT=yes`

It is designed to work with the `datadog/docker-dd-agent` container from [Datadog](https://github.com/DataDog/docker-dd-agent).

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

### blacklist / whitelist

This is currently only used for FINN, and will go away soon.

### use-ingress-tls

Used to extend ingress configuration when deploying applications to enable automatic provisioning and management of certificates for the ingress resources created. This requires infrastructure such as kube-lego/cert-manager to be in place for provisioning of certificates.

Possible values:

* `disabled` (default)
* `default_off`
* `default_on`

If `disabled` or no value is specified no tls configuration is applied. This is the default behaviour.

If `default_off` tls configuration can be explicitly requested on a per application basis through application manifests.

If `default_on` tls configuration will be applied unless explicitly disabled in application manifests.


Secrets
-------

FIAAS supports three different sources of secrets. All three options will provide access to secrets in a pre-defined location, currently `/var/run/secrets/fiaas/`. This allows applications to assume their secrets are located at that path, regardless of where the secrets are sourced from.

### Kubernetes Secret

The default source is Kubernetes Secret objects. If a Secret with the same name as the application being deployed exists in the same namespace it is mounted in the container at a pre-defined location.

When using Kubernetes as a source of secrets it is possible to set the key `secrets_in_environment` in the application configuration to `true`, and each key-value pair in the Secret will be exposed as environment variables to your application. This flag is ignored for by other sources because of technical limitations.

### Secrets init container

Since Kubernetes Secrets are somewhat insecure, operators might want to use other options for storing secrets. The option `secrets-init-container-image` allows selecting an image that will be run as an init-container before the application starts, in order to allow fetching secrets from a different location.

The container will be responsible for getting the application secrets from whatever backend is used, and writing them to disk. The path `/var/run/secrets/fiaas` will be an "EmptyDir" with read/write permissions, which is then mounted with read-only permissions in the application container.

If `secrets-service-account-name` is specified, the named service account will be mounted in the init container.

In the init container, the environment variable `K8S_DEPLOYMENT` will be the name of the application. In addition, any variables specified in a ConfigMap named `fiaas-secrets-init-container` will be exposed as environment variables.

The ConfigMap will also be mounted at `/var/run/config/fiaas-secrets-init-container/`. If there exists a ConfigMap for the application then it will be mounted at `/var/run/config/fiaas/`. 

### Strongbox

In AWS you have the option of using [Strongbox](https://schibsted.github.io/strongbox/) for your secrets. If you wish to use Strongbox, the configuration option `strongbox-init-container-image` should be set to an image that can get secrets from Strongbox. This option is very similar to the previous variant, except that Strongbox gets a few more pieces of information from the application configuration. The application must specify an IAM role, and can select AWS region and a list of secret groups to get secrets from.

The Strongbox init container is treated much the same as the previous variant, with two extra environment variables:

* `SECRET_GROUPS` is a comma separated list of secret groups from the application config
* `AWS_REGION` is the AWS region from the application config.

The secrets should be written to disk at the location `/var/run/secrets/fiaas/$group_name/$secret_name`.
