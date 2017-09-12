TODO        
====

Plans for improvement, ideas, proposals etc.

In order for FDD to become more general, we need to make some changes to how it works. This list will try
to list some ideas and thoughts on how to get there.

No PR should span more than one section, and if possible should be even smaller.


Additional ways of triggering deploy
------------------------------------

Now that we have implemented the deployment flow that uses third party resources, we can discuss other ways
of triggering a deploy:
 
* Get fiaas.yml as Base64, instead of URL
* Split the kafka-listener from the core and create TPRs
* Consume from SQS


New fiaas.yml version 3
-----------------------

We have already defined the v3 schema, and will be working on implementing this going forward.


Richer annotations
------------------

It would be useful to know what fiaas.yml version a given object comes
from when we're looking to remove support for older versions.  An easy
way to do this is to annotate generated objects with the version.

Supporting old fiaas.yml versions
---------------------------------

When adding new features to fiaas.yml, we now have to implement those in both
v1 and v2 factories. It's not always easy to figure out how to translate the
old version to a new feature, so at times we mess up. This will be even more
complex when we introduce new versions.

It would possibly be better if instead of maintaining a factory for each version,
we create a transformer from one version to the next whenever we introduce
a new version. Then we only need to maintain one factory, and all support for
older versions is simplified into transforming yaml. This way it would be easier 
to continue to support v1 even when we arrive at v15, simply by passing the
config through each layer of transformation until we arrive at the current 
version, and pass it to the factory.
