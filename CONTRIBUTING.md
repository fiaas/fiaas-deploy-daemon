# Contributing to fiaas-deploy-daemon

We are happy to accept pull requests that fix bugs or introduce new features.

## New features

If you have a new feature in mind, it is a good idea to discuss it in [#fiaas on
Slack](https://sch-chat.slack.com/messages/C6P6D9CDR) or even in the [fiaas contributors
meeting](https://confluence.schibsted.io/display/SPTINF/FiaaS+contributors+meeting) before starting to work on a pull
request.  If you're not entirely sure about your idea or how to proceed, or if you want to have it discussed in the
fiaas contributors meeting, we encourage [creating a Github
issue](https://github.schibsted.io/finn/fiaas-deploy-daemon/issues/new) giving some background for your idea or
usecase.


## Contributing code

We accept changes as pull requests only. Do not push directly to master. Pull requests require the review and approval
of at least one other contributor before merging.
[ReviewersRaffle](https://confluence.schibsted.io/display/EP/ReviewersRaffle) is used to automatically assign
reviewers, but we also encourage assigning specific people to review your PR if you have someone in mind.

### Testing

We try to keep test coverage [stable or
increasing](https://reports.spt-engprod-pro.schibsted.io/#/finn/fiaas-deploy-daemon?branch=master&type=push&daterange&daterange),
and use [QualityGate](https://confluence.schibsted.io/display/SPTP/Quality+Gate) to manage this. Ensure that your
change has test coverage at the unit and ideally also at the integration/end to end level. Pull requests must pass
QualityGate unless there is a good reason not to - and the PR reviewer agrees to this reason.

Additionally your change must pass the end to end (e2e) test before merging. This test is unfortunately not run in the
CI system due to technical constraints, and must be run manually.

Do this either via `gradle`:

```
$ gradle integrationTest
```

Or by using the python tooling directly:

```
$ python setup.py test --addopts '-m integration_test -n4 -rxs'
```
