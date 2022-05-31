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
# fiaas-deploy-daemon

![FIAAS logo](https://raw.githubusercontent.com/fiaas/design-assets/master/logo/Logo_Fiaas_colour.png)

---

[![Build status](https://fiaas-svc.semaphoreci.com/badges/fiaas-deploy-daemon.svg?style=shields)](https://fiaas-svc.semaphoreci.com/projects/fiaas-deploy-daemon)

You need Python 2.7 and `pip`(7.x.x or higher)  on your `PATH` to work with fiaas-deploy-daemon.

Supported use-cases
-------------------

This application is written to support three separate use-cases:

- Normal: Running inside a cluster, deploying applications in the same cluster
- Bootstrap: Running outside a cluster, deploying itself into a specified cluster
- Development: Running outside a cluster, not actually deploying anything (dry-run)

A combination of command-line arguments and environment-variables control which use-case
is in effect, and how the application should act. There is no global flag to select a
use-case, instead the application will look at available information at each step and
determine its course of action.

See the config-module for more information.

Getting started with developing
-------------------------------

- First ensure you have the most recent version of setuptools for python2 with `pip install setuptools==44.0.0`. This is required for the following steps to work
- Use  `$ pip install -r requirements.txt` to install dependencies
- Make changes to code
Run tests with `tox`:
- `$ tox -e codestyle` checks code style, indentations etc.
- `$ tox -e test` runs unit tests
- `$ tox -e integration_test` runs end-to-end/integration tests. These tests require docker.

Useful resources:

- http://docs.python-guide.org/
- http://pytest.org/
- http://www.voidspace.org.uk/python/mock
- http://flask.pocoo.org/

Running fiaas-deploy-daemon against a local `minikube` or `kind` backed Kubernetes cluster
-------------------------------------------

This workflow is intended for manual testing of fiaas-deploy-daemon against a live Kubernetes cluster while
developing.

To run fiaas-deploy-daemon locally and connect it to a local cluster, do the following:

* Set up development environment and install fiaas-deploy-daemon (`$ pip install -r requirements.txt`)

With kind:
* (See https://kind.sigs.k8s.io/docs/user/quick-start/#installation for how to install and configure kind)
* Start kind: `$ kind create cluster --image kindest/node:v1.15.6`
* Run `$ bin/run_fdd_against_kind`

With minikube:
* (See https://minikube.sigs.k8s.io/docs/start/ for how to install and configure minikube)
* Start minikube: `$ minikube start`
* Run `$ bin/run_fdd_against_minikube`

There should be a bunch of logging while fiaas-deploy-daemon starts and initializes the required
CustomResourceDefinitions. This is normal.

If you need to test some behavior manually you can deploy applications into minikube via fiaas-deploy-daemon in a few ways:

#### Deploying an application via CustomResourceDefinition

In Kubernetes 1.7 and later you can deploy applications by creating a Application CustomResource

```yaml
apiVersion: fiaas.schibsted.io/v1
kind: Application
metadata:
  labels:
    app: example
    fiaas/deployment_id: test
  name: example
  namespace: default
spec:
  application: example
  image: nginx:1.13.0
  config:
    version: 3
    ingress:
      - host: example.com
    metrics:
      prometheus:
        enabled: false
    resources:
      limits:
        memory: 128M
        cpu: 200m
      requests:
        memory: 64M
        cpu: 100m
```

Create the resource by saving this in a file like e.g. `example.yml` and then run
`$ kubectl --context minikube create -f example.yml`.


IntelliJ runconfigs
-------------------

#### Running fiaas-deploy-daemon

Use this configuration both for debugging and for manual bootstrapping into a cluster.

* Create a Python configuration with a suitable name: fiaas-deploy-daemon (dev)
* Script: Find the fiaas-deploy-daemon executable in the virtualenvs bin directory
    * If using bash, try `which fiaas-deploy-daemon` inside the virtualenv
* Script parameters:
    * --debug
    * If you want to deploy to a kubernetes cluster use --api-server, --api-token
     and --api-cert as suitable
* Python Interpreter: Make sure to add the virtualenv as an SDK, and use that interpreter


#### Tests

* Create a Python tests -> py.test configuration with a suitable name (name of test-file)
* Target: The specific test-file you wish to run
* Python Interpreter: Make sure to add the virtualenv as an SDK, and use that interpreter


fiaas-config
------------

fiaas-deploy-daemon will read a fiaas-config to determine how to deploy your application.
This configuration is a YAML file. If any field is missing, a default value will be used.
The default values, and explanation of their meaning are available at `/defaults` on any
running instance.


Release Process
---------------

Successful CI builds of the `master` branch will push a container image to `fiaas/fiaas-deploy-daemon:$timestamp-$commit_ref` and `fiaas/fiaas-deploy-daemon:development`. As the `development` tag's name suggests, it is primarily intended for testing. Do not use this container image tag in production. Refer to the [releases section](releases) section in Github to find the most recent stable release.

Refer to [Creating a Release](docs/developing.md#Creating-a-Release) for how to create a new release version.
