<!--
Copyright 2017-2019 The FIAAS Authors

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
# Scripts

## k8s in DOcker

### Overview

dind-cluster-v1.6.sh
- https://github.com/Mirantis/kubeadm-dind-cluster

Doc
- https://github.com/Mirantis/kubeadm-dind-cluster#using-preconfigured-scripts
- https://github.com/Mirantis/kubeadm-dind-cluster#using-with-kubernetes-source


### TL;DR

```
# start the cluster
$ ./dind-cluster-v1.6.sh up

...

NAME          STATUS    AGE       VERSION
kube-master   Ready     4m        v1.6.6
kube-node-1   Ready     2m        v1.6.6
kube-node-2   Ready     2m        v1.6.6
* Access dashboard at: http://localhost:8080/ui
```

```
# Use the cluster
#
# add kubectl directory to PATH
$ export PATH="$HOME/.kubeadm-dind-cluster:$PATH"
```
