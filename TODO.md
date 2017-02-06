TODO        
====

Plans for improvement, ideas, proposals etc.

In order for FDD to become more general, we need to make some changes to how it works. This list will try
to list some ideas and thoughts on how to get there.

No PR should span more than one section, and if possible should be even smaller.


Move cluster level configuration into a ConfigMap
-------------------------------------------------

Put some configuration in the cluster, instead of in code/environment/command-line:

* HTTP proxy settings [Done]
* DNS name for ingresses
* Name of environment
* Which type of Service to create: NodePort or LoadBalancer (See Entry configuration)

This should be a ConfigMap, mounted as a file in the pod.

#### Entry configuration

Different users have different needs/wants for how traffic goes from outside the cluster to the pods. In addition
to what FDD does, some things needs to happen in the cluster, or outside the cluster, to route the traffic correctly.

The cluster configuration set which type of service to create, and FDD will always create Services
of that type, and an Ingress object for HTTP apps.

Additional ways of triggering deploy
------------------------------------

* Get fiaas.yml as Base64, instead of URL
* Consume from SQS

3rd party resource for application deployment
---------------------------------------------

* Listen for objects of a type and create deployments from that, instead of listening to a queue directly.
    * Object should contain image identifier, and complete fiaas.yml, and named after the application
* Split the kafka-listener from the deployer.
* Annotate objects with version of deployer, so that on upgrades it can re-deploy everything that's not up
to date.

Changes to fiaas.yml
--------------------

These features could be added to fiaas v2, since they are additions and existing configs would still be valid and
sensible defaults would be used.

* Whitelisting of IPs (propagated to annotations on Ingress/Service)
** Combine with default set of whitelisted IPs from cluster config
* Load configuration from an application specific ConfigMap into ENV-variables
* Set number of replicas per environment
* Application specific annotations propagated to k8s objects
** Annotations per object type, free form

This feature would not be compatible with v2, so we need to create a v3 for this feature. If we combine multiple new 
features in one change, the new fields should perhaps just be added to v3.

* Ability to disable ports for an application (batch jobs or queue consumers)
