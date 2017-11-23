# fiaas-deploy-daemon

<!-- Badger start badges -->
[![Badger](https://badger.spt-engprod-pro.schibsted.io/badge/travis/finn/fiaas-deploy-daemon)](https://travis.schibsted.io/finn/fiaas-deploy-daemon) [![Badger](https://badger.spt-engprod-pro.schibsted.io/badge/coverage/finn/fiaas-deploy-daemon)](https://reports.spt-engprod-pro.schibsted.io/#/finn/fiaas-deploy-daemon?branch=master&type=push&daterange&daterange) [![Badger](https://badger.spt-engprod-pro.schibsted.io/badge/issues/finn/fiaas-deploy-daemon)](https://reports.spt-engprod-pro.schibsted.io/#/finn/fiaas-deploy-daemon?branch=master&type=push&daterange&daterange) [![Badger](https://badger.spt-engprod-pro.schibsted.io/badge/engprod/finn/fiaas-deploy-daemon)](https://github.schibsted.io/spt-engprod/badger)
<!-- Badger end badges -->

===================

You need Python 2.7 and `pip`(7.x.x or higher)  on your `PATH` to work with fiaas-deploy-daemon.

When you first run gradle, it will install `pew`, and use it to create a virtualenv
named 'fiaas-deploy-daemon'. If you wish, you can install pew and/or create the
virtualenv before you run gradle, in which case gradle will use the ones you provide.

On OSX there may be some problems with pew and you get something like "Python locale error: unsupported locale setting"
Setting the following solved this for us

`export LC_ALL=$LANG`


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

- `$ finnbuild execute setup` or `$ ./gradlew setup` (adjust as necessary for windows)
- Learn about pew: `$ pew`
- Enter the virtualenv `$ pew workon fiaas-deploy-daemon`
- Make changes to code
- `$ finnbuild execute test` or `$ ./gradlew test` (adjust as necessary for windows)

Useful resources:

- http://docs.python-guide.org/
- http://pytest.org/
- http://www.voidspace.org.uk/python/mock
- http://flask.pocoo.org/

Running fiaas-deploy-daemon with `minikube`
-------------------------------------------

To run fiaas-deploy-daemon locally and connect it to a minikube cluster, do the following.

* Set up development environment and install fiaas-deploy-daemon (`$ pip install -r requirements.txt`)
* Start minikube: `$ minikube start`
* Run `$ bin/run_fdd_against_minikube`

There should be a bunch of logging while fiaas-deploy-daemon starts and initializes the required
ThirdPartyResources and/or CustomResourceDefinitions. This is normal.

If you need to test some behavior manually you can deploy applications into minikube via fiaas-deploy-daemon in a few ways:

#### Deploying an application via ThirdPartyResource

In Kubernetes 1.6 and 1.7 you can deploy applications by creating a PaasbetaApplication ThirdPartyResource.

An example PaasbetaApplication:

```yaml
apiVersion: schibsted.io/v1beta
kind: PaasbetaApplication
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
    version: 2
    host: example.com
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
    version: 2
    host: example.com
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

#### Deploying an application via http

either by accessing the web UI at
http://localhost:5000



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
* Environment variables: Add the following two if you wish to pick up pipeline-messages
    * KAFKA_PIPELINE_SERVICE_HOST=adm-internalmod1.finntech.no
    * KAFKA_PIPELINE_SERVICE_PORT=7794
* Python Interpreter: Make sure to add the virtualenv as an SDK, and use that interpreter


#### Tests

* Create a Python tests -> py.test configuration with a suitable name (name of test-file)
* Target: The specific test-file you wish to run
* Python Interpreter: Make sure to add the virtualenv as an SDK, and use that interpreter


finnbuild
---------

The following commands are nice to know:

- `finnbuild execute` and `finnbuild execute test`
    - Executes tests
- `finnbuild execute setup`
    - Make sure needed tools and virtualenv are created, and initialize the virtualenv
- `finnbuild execute build`
    - Runs tests, then builds a binary wheel package
- `finnbuild execute bake`
    - Runs tests, builds package, then makes docker image
- `finnbuild execute run-docker`
    - Runs the docker image, exposing the web-interface on port 5000


fiaas-config
------------

fiaas-deploy-daemon will read a fiaas-config to determine how to deploy your application.
This configuration is a YAML file. If any field is missing, a default value will be used.
The default values, and explanation of their meaning are available at `/defaults` on any
running instance.
