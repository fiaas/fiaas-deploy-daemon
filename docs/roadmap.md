# Roadmap

This is a non-exhaustive list of changes we might want to make, in tentatively prioritized order at the time of writing.

T-shirt size: S, M, L indicates a rough estimate of the relative amount of work involved.

- [S] Implement new release model for fiaas-deploy-daemon (#163)
  - Semantic versioned releases for fiaas-deploy-daemon
  - Deprecate fiaas/skipper
- [L] Run fiaas-deploy-daemon on Python 3 (#6)
- [S] Make number of ApplicationStatus resources to keep configurable (#46)
- [M] Deprecate/remove fiaas.yml v2 format
- [S] Evaluate container registries for moving container images out of DockerHub
- [M] Support autoscaling on custom metrics for applications
- [M] Support managing PodDisruptionBudgets for applications
- [L] Look into replacing fiaas/k8s with kubernetes-clients/python
  - PoC fiaas-deploy-daemon watcher thread using official client
  - Might be  possible to split into smaller tasks by gradually migrating deployer components to official client
- [L] Improve error handling when fiaas.yml is invalid
  - Better instrumentation in fiaas-deploy-daemon for propagating errors
  - Implement a full schema for the Application resource in the CRD, to enable validation
    - Requires removing support for fiaas.yml v2 format
- [L] Look into moving status into the Application resource and deprecating/removing the ApplicationStatus resource
