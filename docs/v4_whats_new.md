<!--
Copyright 2017-2024 The FIAAS Authors

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->
# What's new in FIAAS configuration format version 4

Version 4 of the FIAAS application specification extends the workload options with first class support for
stateful applications.

## Stateful workloads

The new top-level `statefulset` block lets you request a Kubernetes `StatefulSet` instead of the default
`Deployment`. When `statefulset.enabled` is `true`, FIAAS will:

* replace the generated `Deployment` with a `StatefulSet`
* render a headless service and reuse it as the `StatefulSet`'s `serviceName`
* create PVC templates from the items listed in `statefulset.volume_claims`
* mount the claims into the main application container alongside the existing config and `/tmp` volumes
* skip the HorizontalPodAutoscaler because the Kubernetes autoscaler does not support `StatefulSet`

The minimal configuration looks like this:

```yaml
statefulset:
  enabled: true
  volume_claims:
    - name: data
      mount_path: /var/lib/app
      resources:
        requests:
          storage: 10Gi
```

All other fields in the block are optional and default to behaviour compatible with Kubernetes defaults.

## Version selection

Remember to set `version: 4` at the top of your `fiaas.yml` to opt in to these features. Applications still targeting
older configuration versions will continue to be transformed and deployed as before.
