Long term architectural plans
=============================

In order for FiaaS to become a platform that is flexible enough to work in a number of situations, while maintaining high developer velocity and deep integration with surrounding infrastructure, the platform should be built using a microservice mindset. By building the platform from many small components working independently from the same world view, we can install FiaaS in any kubernetes cluster using a selection of components to fit the needs of a particular cluster.

The platform should be split into separate services, so that each piece can be replaced if needed. Making each service small makes it easier to pivot to support new use-cases, without having to rewrite large parts of the platform.

The FiaaS team should build and maintain a number of services, some of which have overlapping functionality tuned for different deployment options. For instance, we would maintain two different solutions for metrics, to support the two ways of gathering metrics that are in use in Schibsted today. Depending on the need, a cluster operator would deploy one or both solutions to their cluster.

Building our platform from several microservices also gives the cluster operator the option of replacing one or more of the services with custom services tailored for their own needs. For instance, FINN would have integrated access and ingress controller, while other teams would use the heimdall controller for access combined with a standard ingress controller like nginx.

The key to building a platform in this fashion is to ensure that all interfaces between services are documented and easily used. The obvious choice in a Kubernetes cluster is to use the Kubernetes API, either by creating custom objects (Third Party Resource aka Custom Resource), or by adding annotations or labels to existing objects. Some actions would need to be applied before objects are created, and in future versions of Kubernetes, this could be solved by ["Initializers"](https://github.com/kubernetes/community/blob/master/contributors/design-proposals/admission_control_extension.md). Otherwise, services should watch the Kubernetes API for events of interest and act on them. CoreOS coined the term "Operators" for services of this type, and we should aim to make as many of our services be Operators.

The problem of applying actions before an object is created is so important that we can't wait for initializers to become production ready, so we need to devise a way to solve that problem.

Extension mechanism
-----------------------

If we build our platform as above, the services (operators) will often need to know about others operating in the same cluster. Services implemented by others, to integrate with our platform, will also need to be discovered. To solve this, we will use a generic extension mechanism for both services developed by us, and for services developed by cluster operators. We will call these services "Extensions". An extension can be an operator, or a simple service integrating via hooks.

This allows for a wide range of use-cases, some specific to a single site and outside the scope of the PaaS itself, and others developed and maintained as part of the PaaS. Site-specific features can be implemented in much the same way as generic PaaS features, and an extension that starts life as a site-specific solution can easily by lifted up and deployed to all users of the PaaS if it is useful to others. 

Extensions in the cluster needs to be registered, by creating a PaasExtension object, with details about how it integrates with the rest of the platform, a name and possibly other identifying details like maintainer and code repo.

Extensions would typically require some configuration for each application. In the case of pure Operators, the configuration would most likely be in the form of custom annotations that are applied to objects as they are created, and then picked up by the Operator. This is supported in v3 of the fiaas.yml specification, with custom annotations propagated directly from the configuration to the objects.

When an extension needs configuration that can't be applied as annotations on existing objects, we need a place to put that configuration. Configuration of an extension happens in a `extensions` section in the fiaas.yml file of a project (which is exposed in the cluster as a TPR). Each extension needs to register using a unique name, which would typically be the name of the PaasExtension object. The extension would then find its configuration under `extensions.<name>` in the configuration. When linting, anything under `extensions` are ignored by the platform itself, except that we will issue warnings (or even errors?) if there is configuration for a non-existing extension.

Hooks of various kinds
----------------------

To replace initializers, we will need to implement some kind of pre-create hook. We should make sure that this mechanism is extensible and flexible enough to handle other hooks as well. There are already a couple hooks we can envision, and we should be able to add more should the need arise.  

Operators that wish to use hooks should add the hooks it wishes to use to its PaasExtension object.

At the start, we should support two hooks: `pre-create` and `lint`. Each one is a URL which will receive a POST containing data to be acted on. Further hooks would be created by adding more URLs.

### Pre-create hooks

When FDD is creating or updating a new k8s object, it will post the proposed object (using JSON) and the configuration to all registered pre-create hooks. The hook can then modify, reject or ignore the object. After all hooks have been involved, the object is created/updated. The exact semantics should be clearly documented once implemented, but something along the lines of 304 Not Modified if the hook does not have any "comment", a 200 OK followed by a modified body if the hook wants to apply changes, and a suitable code from the 4XX range if the object should not be created/updated at all. In the last case, FDD should log the reason and fail the deployment. 

### Linting hooks

When linting a configuration, all linting hooks will receive a copy of the full configuration. It is assumed that the hook will only concern itself with the parts of the configuration that is relevant for its own operation.

Again, the exact semantics of how results of the linting should be reported will need to be documented once we start implementing the linting process.

### Ordering

Hooks, and in particular pre-create hooks, might be sensitive to the order they are applied in. There are two basic approaches to deal with this, each with variations to some degree. It is hard to guess which one will make the most sense, but we probably need to pick one and go with it. 

One problem with ordering of extensions is who sets the order? The extension developer, or the cluster operator? The developer knows what the extension needs, while the cluster operator knows which other extensions are active in the cluster. It would be nice if we could express what an extension needs and what it provides in a meaningful and machine readable way, but it sounds like it might be something you need a master thesis more than a short section in an architecture document to define.

#### Priority number

One approach is that each extensions lists a priority number in its PaasExtension object. When applying hooks, the extensions are ordered according to their priority. If two extensions have the same priority, the ordering between them is undefined.
 
#### After and before links

The other approach is that each extension has a list of extensions that needs to be applied before it, and a list of extensions that it knows should be after it. It is possible to create loops this way, but it can also express some more complex relationships.

When ordering the extensions, the platform needs to create a graph describing the relationships and apply accordingly. This is a more complex operation than simply ordering by number, and might require some thought. 

We can extend this by adding categories to each extension, where you can say that an extension needs to be after extension "xyz", and after all extensions in category "network", while being before the operators in category "access". This of course creates the additional problem of defining useful categories, and who does the defining.


Use-cases and how to solve them
-------------------------------

### Case 1: Site-specific SSL annotations

To use `lego` to auto-provision SSL certificates, two annotations need to be added to each ingress. This can of course be added manually to every project, but would be better served done on the scope where the ingress TLS mechanism relies on lego. An operator would be good in this case - something which would know what namespaces/applications are served by the ingress controller, and would automatically add those annotations. Ideally, this would be managed by the CRE team in the case of the CRE but could easily be deployed otherwise.

As part of the PaaS we might even consider creating a generic "annotater" operator, which can read a list of default annotations for a namespace/cluster, and apply to all objects matching a selector. This would then be deployed by cluster operators, with suitable configuration for their cluster.

### Case 2: Per environment QoS level

The CRE has adopted the convention that teams are allocated namespaces designating their "dev", "pre" and "pro" environments as suffixes to their team name, e.g. delivery-{dev,pre,pro}. These namespaces have different QoS guarantees, enforced by gating based on pod resource requests and limits.

The specifications around resource requests and limits are documented here: https://confluence.schibsted.io/display/SPTINF/Resources+in+Kubernetes

To handle this case, the resource requests/limits in the pod specification within the deployment needs to be managed per destination namespace. This seems best handled before the deployment is an active object, and that currently seems best done with the deploy daemon. If done as an operator, after the deployment is active, modifying the pod specification would result in a new rolling deploy, meaning that for every FIAAS deploy, we may have a failed deploy, and then another deploy with the desired settings.

This case can be solved with pre-create hooks, removing or adjusting request and limits as needed. This is a site specific policy and not something that really should be handled in FIAAS. However, in order to get deployment to CRE to work, we should probably develop this hook on behalf of the CRE team.

On another note, this policy makes it tricky to run Java applications, as the JVM needs to know how much memory is available. The typical thing to do is to use a script to set the available memory for the JVM to a percentage of the limit (since the OS needs some of the memory for itself) on startup. If we strip away the limits, then the scripts will fail. 

### Case 3: Log shipper support

Assuming that the developer contract is just to log via stdout, there is no real management that needs to happen in the deploy daemon; all log shipping can be facilitated by using the Kubernetes API.

Any configuration of the back-end log shipper could be done via a contract specifying what configmaps/secrets would be required for shipping to function.

If a sidecar was needed (to support syslog or file-based logging), then mutation of the deployment object would be necessary which would require using a pre-create hook.

Until the need to modify the pod spec occurs, this case can be satisfied as an operator.

### Case 4: Optional metrics support

This is much like the log shipper case. There may be a need to modify the pod spec but unless that happens, this case can also be satisfied as an operator.

### Case 5: Fallback URL for ingress

This could be implemented as a custom ingress annotation that is parsed by the ingress controller. A default could be stored within the ingress controller setting the default backend, or using the "annotater" suggested in Case 1.

### Case 6: Monitoring Directives (SLA SLO SLI)

This is a case for an extension that might be promoted to the root configuration, depending on where the company is moving. It could be implemented as a combination pre-create hook and operator, with a linting hook as an optional extra. The pre-create hook would read the configuration and modify the object in some way that allows the operator to set up extra monitoring. It might also be possible to do without the pre-create hook, because when the operator finds an object it needs to act on it can look up the configuration itself, from the TPR that belongs to the application. 

