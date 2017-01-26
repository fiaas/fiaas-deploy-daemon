TODO        
====

Plans for improvement, ideas etc.

In order for FDD to become more general, we need to make some changes to how it works. This list will try
to list some ideas and thoughts on how to get there.


Move cluster level configuration into a ConfigMap
-------------------------------------------------

Put some configuration in the cluster, instead of in code/environment/command-line:

* HTTP proxy settings
* DNS name for ingresses
* Name of environment

3rd party resource for application deployment
---------------------------------------------

* Listen for objects of a type and create deployments from that, instead of listening to a queue directly.
    * Object should contain image identifier, and complete fiaas.yml, and named after the application
* Split the kafka-listener from the deployer.
* Annotate objects with version of deployer, so that on upgrades it can re-deploy everything that's not up
to date.

Entry configuration
-------------------

Different users have different needs/wants for how traffic goes from outside the cluster to the pods. In addition
to what FDD does, some things needs to happen in the cluster, or outside the cluster, to route the traffic correctly.

There are a few (sensible) ways for traffic from the outside to reach a pod:

* Service of type LoadBalancer, integrated with a Cloud Provider LB (ie. AWS ELB, or GCP LB)
* Service of type NodePort, with a load balancer/DNS round robin outside the cluster

For HTTP services, another option is to use the Ingress object, combined with either an in-cluster ingress controller,
or an out-of-cluster ingress controller. 

In-cluster controllers take care of routing traffic once it has entered the 
cluster, but relies on one of the two above mentioned methods to direct all traffic into the cluster to the ingress
controller. If you do this, you can still do Services with NodePort or LoadBalancer, but you can also close down
the cluster to only allow traffic through the ingress controller, by setting your Services to be of type ClusterIP.

Out-of-cluster controllers use the same Ingress API object, but routes traffic to the corresponding Services using 
NodePort to enter the cluster. In this model, each service can be reached directly, without going through the ingress
controller, simply by connecting to a the correct port on any node.

In my view, running the ingress controller is the cluster admins job, and they decide which one, and if it's in-cluster
or out-of-cluster. If you don't run an ingress controller at all, you don't need Ingress objects, but they do no harm.

*My suggestion is that the cluster configuration set which type of service to create, and FDD will always create Services
of that type, and an Ingress object for HTTP apps.*

Custom annotations on objects
-----------------------------

This comes up because when you use Service with LoadBalancer on AWS and want TLS-certificates, you attach the AWS
certificate to the LB by way of an annotation on the Service.

It would be best if we could manage without this, but I don't have a good suggestion for handling it, unless you just
have a single site/certificate in your cluster. In that case, you could use the in-cluster ingress controller, with
a manually configured Service with LoadBalancer in front, where you can add your annotations. When doing it like this,
FDD does not need to handle it, it becomes the cluster admins responsibility.
