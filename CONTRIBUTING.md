# Contributing to fiaas-deploy-daemon

We are happy to accept pull requests that fix bugs or introduce new features!

The following is a set of general guidelines for contributing to fiaas-deploy-daemon.

## Code of conduct

Contributors to fiaas-deploy-daemon as well as participants in any other FIAAS project are expected to adhere to the [Code of Conduct](https://github.com/fiaas/governance/blob/master/code_of_conduct.md).

## Governance

FIAAS has a minimal governance model that its projects are managed in accordance with. See [this document](https://github.com/fiaas/governance/blob/master/governance_model.md) for details.

## Create an issue

If you have found a bug, please [submit a a Github issue](/issues/new) to describe the bug and ideally any steps to reproduce it.

If you have a new feature or any larger changes in mind we also encourage [creating a Github issue](/issues/new) giving some background for your idea or usecase before submitting code as a pull-request.

## Contributing code

Changes will be accepted as pull requests only. Do not push directly to master. Pull requests require the review and approval of at least one maintainer before merging.

### Testing

We try to keep test coverage stable or increasing. Please ensure that your change has test coverage at the unit and ideally also at the integration/end to end level. Pull requests must pass CI build which includes codestyle checks, unit tests and end-to-end tests before merging. See the [Getting started with developing](/README.md#getting-started-with-developing) section in the README for how to check codestyle and run tests locally.
