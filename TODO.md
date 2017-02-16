TODO        
====

Plans for improvement, ideas, proposals etc.

In order for FDD to become more general, we need to make some changes to how it works. This list will try
to list some ideas and thoughts on how to get there.

No PR should span more than one section, and if possible should be even smaller.


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
* Application specific annotations propagated to k8s objects
** Annotations per object type, free form

This feature would not be compatible with v2, so we need to create a v3 for this feature. If we combine multiple new 
features in one change, the new fields should perhaps just be added to v3.

* Ability to disable ports for an application (batch jobs or queue consumers)
* Set number of replicas per environment

Richer annotations
------------------

It would be useful to know what fiaas.yml version a given object comes
from when we're looking to remove support for older versions.  An easy
way to do this is to annotate generated objects with the version.
