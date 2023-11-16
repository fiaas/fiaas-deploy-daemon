# name is used in various places in the templated Kubernetes resources; for example the name of the resources, labels,
# container name etc.
name: fiaas-deploy-daemon

# Configure the image used by the chart. To use different image than the chart points to by default you can update
# `image.tag` and/or `image.repository`.
image:
  repository: fiaas/fiaas-deploy-daemon
  tag: ${RELEASE_VERSION}
  pullPolicy: IfNotPresent

# Set CPU and memory request and limits. It is recommended to set this explicitly. The amount of resources needed may
# depend on how many applications will be deployed in the namespace fiaas-deploy-daemon runs in. The example in the
# comment below shows the expected structure and has the values that fiaas-deply-daemon previously used to set when
# deploying itself. This can be used as a starting point for an appropriate resource configuration for your
# environment.
resources: {}
  # limits:
  #   cpu: 400m
  #   memory: 512Mi
  # requests:
  #   cpu: 200m
  #   memory: 128Mi

# Set fiaas-deploy-daemon configuration under the `configmap.clusterConfig` key. The default includes some flags that
# you likely want to set, but most likely you will want to override this. Refer to the operator guide[1] for details
# on how to configure fiaas-deploy-daemon.
# [1]: https://github.com/fiaas/fiaas-deploy-daemon/blob/master/docs/operator_guide.md
configMap:
  clusterConfig: |-
    enable-crd-support: true
    enable-service-account-per-app: true
    use-networkingv1-ingress: true
    use-apiextensionsv1-crd: true

# Configure whether various RBAC resources should be managed by the helm chart or not. Refer to the RBAC section[2] of
# the operator guide for details.
# [2]: https://github.com/fiaas/fiaas-deploy-daemon/blob/master/docs/operator_guide.md#role-based-access-control-rbac
rbac:
  serviceAccount:
    create: true
    labels: {}
    annotations: {}
  role:
    create: true
    labels: {}
    annotations: {}
    enableCertificates: false
  roleBinding:
    create: true
    labels: {}
    annotations: {}
  clusterRole:
    create: true
    labels: {}
    annotations: {}
  clusterRoleBinding:
    create: true
    labels: {}
    annotations: {}

# Set labels on all resources created by the helm chart. The structure should be a object where the key is the label
# key and value is the label value
labels:
  global: {}

# Set annotations on all resources created by the helm chart. The structure should be a object where the key is the
# annotation key and value is the annotation value
annotations:
  global: {}

# Override configuration on the service resource
service:
  # Set labels on the service resource
  labels: {}
  # Set annotations on the service resource
  annotations: {}
  type: ClusterIP
  port: 5000
  targetPort: 5000

# To make the chart create a Ingress resource, `ingress.enabled` must be set explicitly to `true`. It is necessary to
# also set at least `ingress.host` to get a functional ingress.
ingress:
  enabled: false
  # Set labels on the ingress resource
  labels: {}
  # Set annotations on the ingress resource
  annotations: {}
  # The hostname the ingress should be available from
  host: chart-example.local
  pathType: ImplementationSpecific

  tls:
    # Create TLS section on the ingress resource to support HTTPS. For this to work, the TLS secret that `secretName`
    # points to must already exist / be managed elsewhere. That is, the chart does not create a TLS certificate
    # itself.
    enabled: false
    secretName: chart-example.local

# Override settings on the deployment and pod template
deployment:
  # Set labels on the deployment resource
  labels: {}
  # Set labels on the deployment resource
  annotations: {}
  # By default trigger a redeploy if there is a change in the configMap, to create a new fiaas-deploy-daemon pod using
  # the updated configuration. Set to false to disable this behavior.
  redeployOnConfigMapChange: true
  pod:
    # Set labels on the pod template
    labels: {}
    # Set annotations on the pod template
    annotations:
      prometheus.io/path: /internal-backstage/prometheus
      prometheus.io/port: "5000"
      prometheus.io/scrape: "true"
