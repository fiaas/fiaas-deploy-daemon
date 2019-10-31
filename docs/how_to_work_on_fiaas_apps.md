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
How to work on FIAAS apps
=========================

FIAAS sets many expectations for the runtime environment, and when developing an application to run in that environment, it is sometimes necessary to have a development environment on your local machine that closely resembles what you will have in production.

This document will try to describe how you can set up a local development environment that will mimic a true FIAAS runtime environment. Many of these steps could and should be scripted, but for now it is a somewhat complicated and length setup process. Hopefully this is the first step in improving this. Some parts of this guide may be Linux specific, adapt as necessary for your chosen platform.

Note: This is a guide to developing business apps that run in FIAAS. Developing FIAAS components in many cases require a slightly different flow.

Requirements:

- Minikube: <https://kubernetes.io/docs/setup/minikube/>
- Helm: <https://helm.sh/>


Getting a local Kubernetes cluster
----------------------------------

FIAAS runs in Kubernetes, so you need a Kubernetes cluster on your machine. Luckily, Minikube can help. Unfortunately, Minikube is slightly unstable and buggy, so even when set up perfectly right, it might do weird things.

Steps:

1. `minikube start --kubernetes-version <version>`
1. Make sure the ingress and kube-dns minikube addons are enabled: `minikube addons list`
    - If either is not enabled, you must first run `minikube addons enable <addon>`,
    - then stop minikube (`minikube stop`),
    - and start over
1. Inject any pull secrets you may require. An example script to do this is located in `bin/inject_pull_secret`. Adapt to your needs.


Install FIAAS in your cluster
-----------------------------

To install FIAAS, we are going to use [Skipper](https://github.com/fiaas/skipper). Unfortunately, Skipper is not packaged and distributed properly (yet), so you need to clone the repo and run from there.

```bash
git clone git@github.com:fiaas/skipper.git
cd skipper
# As a sanity check, verify that your current kubectl context is minikube
kubectl config current-context
# Install helm in the cluster
helm init --upgrade --wait
# Install Skipper, which will install FIAAS
helm install helm/fiaas-skipper --wait --set ingress.fqdn=skipper.$(minikube ip).xip.io \
 --set ingress.suffix=$(minikube ip).xip.io --set ingress.enableTLS=false --set addFiaasDeployDaemonConfigmap=true \
 --set rbac.enabled=true 
```

With these commands, Skipper installs a default configuration for FIAAS in the `default` namespace, and installs the stable version of FIAAS. You may want to adjust the configuration to more closely match the configuration used in your runtime environment. To do that, follow these steps:

1. View a copy of the `fiaas-deploy-daemon` ConfigMap used in your runtime environment (`kubectl get cm fiaas-deploy-daemon -oyaml` using the correct context).
1. Make sure you are still using the `minikube` context: `kubectl config use-context minikube`
1. Edit the ConfigMap to your liking: `kubectl edit cm fiaas-deploy-daemon`
1. Restart fiaas-deploy-daemon. This can be done in one of several ways:
    - Delete the running pod: `kubectl delete pod <name of fiaas-deploy-daemon pod>`
    - Edit the `fiaas-deploy-daemon` Deployment by adding an innocuous label or annotation: `kubectl edit deploy fiaas-deploy-daemon`
    - Or simply delete the Application object and let Skipper re-deploy (this can take several minutes): `kubectl delete application fiaas-deploy-daemon`

You now have a working Kubernetes cluster with FIAAS installed! Keep in mind that as long as you use `minikube stop` to stop the cluster, and `minikube start --kubernetes-version <version>` to start it, the cluster should come up exactly as it was when you stopped it. You should only need to do the above steps the first time, or when changing versions of either Minikube or Kubernetes.


Working with an application
---------------------------

Now that you have a cluster, you will want to run things in it. The first thing to do, is to make sure you are using the docker daemon inside the cluster, so get your docker-env from Minikube: `eval $(minikube docker-env)`.

Now you can build your application like you normally would, and the docker image will be available to your Kubernetes cluster. A common pitfall is to just build `latest`, as `latest` will always be considered "the same version" when Kubernetes considers if it needs to pull the image and restart. You should adjust your build scripts to add a timestamp to the version.

Once you have a docker image, you need to make FIAAS deploy it to your cluster. This is done by creating an Application object in the cluster. `docs/crd/examples/nginx.yaml` has an example YAML manifest for an Application. 

If we start with the `nginx.yaml` file, you need to change the following parts:

- Under metadata:
    - name: Set the name of your application here. This name is used throughout FIAAS
    - labels.fiaas/deployment_id: Set this to the version you just built, optionally adding a counter if you want to trigger a new build but not build a new image
- Under spec:
    - application: The name of your application again
    - image: The docker image you wish to deploy. Remember to include version
    - config: A direct copy of your `fiaas.yml`

Once you have your new YAML file, deploy the application: `kubectl create -f <your.yaml>`. This will trigger FIAAS to deploy the application. Depending on your configuration, after a bit of startup, you should be able to use your application. You can find a working web-address by listing the Ingress: `kubectl get ing <application name>`. 

When you build a new image, you must change the `deployment_id` and `image` fields, and update the Application: `kubectl replace -f <your.yaml>`.
