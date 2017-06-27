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
