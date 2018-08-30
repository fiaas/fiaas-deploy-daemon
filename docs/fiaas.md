FIAAS
=====

What will FIAAS give me?
------------------------

FIAAS is designed for CD from the start. From the application developers perspective, FIAAS separates the parts the application developers need to care about from the parts the cluster operator need to care about.

Using FIAAS we can integrate applications with the underlying infrastructure, often adapting to changes without the application developer needing to care. The way FIAAS deploys applications allow us to make changes and then redeploy all applications to make use of the new feature right away. We can change how the infrastructure is connected, and automatically change all applications in one go.

The abstractions provided by FIAAS also means that an application can be deployed to two very different Kubernetes clusters, and still work. In this case, FIAAS acts like an “Interface”, defining how the connection should look, and the cluster provides the implementation of that “Interface”. This is an extension of the fundamental idea of Kubernetes: “Everything has an API”.

FIAAS has an opinion about how you should deploy your application on Kubernetes. It will, in many cases, give you the option of overriding that opinion, but the defaults are chosen for a reason. They have two purposes:

1. Drive applications towards a common convention that is sensible
2. Provide guidance based on what we have learned along the way 

For a new project, the goal is that the defaults provided by FIAAS makes sense, and in most cases work for that application. We try to find the balance between giving developers too many choices vs. hiding too much, but this is always going to be difficult. Neither end of the spectrum is good, FIAAS maintains a fine balance somewhere in the middle.

While application developers always need to care a little about their infrastructure and operations, the aim of FIAAS is to reduce how much detail is needed. Very few developers should need to know how to operate a Kubernetes cluster, and the time saved can be put to better use developing applications for business needs.

We believe that a set of conventions that applications keep close to will make it easier to migrate from one deployment option to another. Driving applications in this direction will mean it is easier to change the next time the IT industry faces a similar revolution. Computers are better at helping you with things that are (almost) the same, than with things that are wildly different. Conventions are good, because it allows us to use computers to help us more often.

Kubernetes is a high-level abstraction when compared to VMs and bare-metal servers, but the simple fact that it does not have any primitives for "Application" tells you that it is not the pinnacle of abstractions. And it shouldn't be. Kubernetes brings incredible power to the infrastructure part of what we do, but to think that it perfectly describes an application is not giving applications enough credit.

We are not arguing that FIAAS is an abstraction that describes applications completely, but we take the foundations of K8S and try to build another level towards the sky, using the fundamental principles that K8S established (such as APIs for everything, good defaults, a way to override the defaults where it makes sense).

But why not Helm?
-----------------

Helm is great for packaged software. Things that get a version number and has an official release cycle. We don't do that here. We do continuous delivery (CD), where every commit potentially gets deployed to production. If you are not doing CD, Helm is a good alternative.

We have tried using Helm in a CD setup, and it is painful, it is hard, and it is error prone. Interestingly enough, a whole ecosystem of tools have emerged that try to wrap Helm to do more useful things.

There are several projects that try to define a set of packages to install, all of them designed in a similar fashion. For the deployment of frameworks, tooling and other cluster level systems, Helm is a perfect choice. If you are a cluster administrator, we encourage the use of Helm, probably combined with things like Keel, Helmfile, Helmsman or Landscaper.
 
Should I use FIAAS for all my applications?
-------------------------------------------

That is not the intention. FIAAS aims to cover 80-90% of stateless microservices. There will always be cases where FIAAS will not be suitable, and that is ok. However, we believe most applications will benefit from using FIAAS to deploy, as it makes life easier for developers. A metric that supports this belief is that at the time of writing, nearly 85% (385 of 460) of applications at FINN are deployed using FIAAS. Of the remainder, only a handful have been confirmed not suitable for deployment using FIAAS. We anticipate the percentage to grow as FINN completes the migration from the legacy infrastructure to Kubernetes.

If you are considering using FIAAS, you should be aware of this fact and let teams choose, but keep in mind that if you have 1000 applications that are deployed in 100 ways to 10 different forms of infrastructure, it might be better to change your workflow than to spend time and energy to reinvent the wheel all those times. It is more efficient to spend resources on building the one four-lane motorway that everyone uses, rather than building 100 small paths.

Why did we make this?
---------------------

We started developing FIAAS at FINN in late 2015, start of 2016. At the time, there were no Kubernetes based PaaS offerings except OpenShift and maybe a few more low level options. OpenShift was evaluated, and considered to not fit our needs.

The original motivations was that as FINN was moving to Kubernetes, we needed a way for FINNs developers to maintain the speed and feedback they had grown accustomed to. We also needed to support the features of the infrastructure platform that they were already relying on in the legacy systems. These features included:

 * From commit to production in less than 10 minutes on average
 * Automatic load balancing and health checking of instances
 * Continuous deploy with no downtime
 * Collection of logs and metrics
 * Some form of service discovery

At the same time we wanted to maintain a separation of concerns. Application developers should concern themselves with what is needed for their business value, while the infrastructure team should maintain control over integration with the infrastructure.

More recently, a few alternatives has been made open source, we are aware of a couple projects. We also know that there exists similar projects at several other companies that we have talked to. I believe it was Digital Ocean that approached us after a presentation to say they had an internal system that was almost identical in design and implementation. If we had started now, it is possible we would have looked at the alternatives, but we still believe there are gaps between FIAAS and the other options, especially when applied to our systems.

As FIAAS has become more mature, it was natural to extend its usage to the rest of Schibsted, so our focus for the last year has been to adapt and extend FIAAS from a PaaS tailored for FINN, to a PaaS that will fit for most sites in Schibsted and beyond.

