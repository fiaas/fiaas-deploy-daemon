${GIT_TAG_ANNOTATION}

## Release Artifacts
- Container image: `${RELEASE_IMAGE_REF}`
- `fiaas-deploy-daemon` Helm chart version `${CHART_VERSION}`

Find the helm chart by adding the FIAAS helm repo and inspecting the chart from there:
```shell
helm repo add fiaas https://fiaas.github.io/helm
helm search repo fiaas-deploy-daemon --version ${CHART_VERSION}
```
