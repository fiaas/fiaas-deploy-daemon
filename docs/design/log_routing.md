Log routing
===========

In a cluster there might be a number of logging targets, depending on teams and other infrastructure in the company. Ideally, application developers shouldn't need to concern themselves with how to get their application logs, the infrastructure should deal with this for them.

This requires integration between the applications, cluster and other infrastructure. This document is going to describe one way of doing this integration.

Use cases
---------

### All the things

The simplest form of log routing is when everything running in the cluster should route logs to the same destination. This will typically be the case in on-premise clusters operated by a single organisation.

### Environment

If the cluster has both the dev environment and the pro environment (or any number of other environments), routing logs to different destinations depending on environment seems natural. In this case we need a way to separate environments, and map from an environment to a logging destination.

### Team

In this setup, each team has their own destination, and every app deployed by that team should send their logs to that destination. In this scenario, we need a way to map from application to team, and then from team to destination.

### Team and Environment

This is a combination of the above two use cases, and requires the mapping to go from application to a combination of environment and team, and from that combination to a logging destination.

### Application

This is the most flexible setup, where every application may have a different logging destination. This setup is almost never a good idea, and we will not concern ourselves with this use case in particular.

Decoupling
----------

One important design consideration is to decouple the parts. By adding annotations/labels that say something about what something *is*, we can then use that information to select what to *do*. This way we don't have to know which logging destination an application should send its logs to, we only need to know that applications belonging to team X or running in environment E should have its logs routed to destination D. We then create the mapping where it makes sense.

An additional bonus is that the information about what something is can be used for other considerations as well.

Needed work
-----------

We already have a system for setting team labels on applications, but it has some edges that needs to be polished. https://github.schibsted.io/finn/fiaas-deploy-daemon/issues/173

Deciding on a label/annotation to describe environment for a namespace, and applying that where needed.

Implement a log router that can route logs based on these labels. This might be out of scope for the FIAAS project itself.

