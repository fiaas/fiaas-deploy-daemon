name: fiaas-deploy-daemon

image:
  repository: fiaas/fiaas-deploy-daemon
  tag: ${RELEASE_VERSION}
  pullPolicy: IfNotPresent

resources: {}
  # limits:
  #   cpu: 400m
  #   memory: 512Mi
  # requests:
  #   cpu: 200m
  #   memory: 128Mi

configMap:
  clusterConfig: |-
    enable-crd-support: true
    enable-service-account-per-app: true
    use-networkingv1-ingress: true
    use-apiextensionsv1-crd: true

rbac:
  serviceAccount:
    create: true
    labels: {}
    annotations: {}
  role:
    create: true
    labels: {}
    annotations: {}
  roleBinding:
    create: true
    labels: {}
    annotations: {}

labels:
  global: {}
annotations:
  global: {}

service:
  labels: {}
  annotations: {}
  type: ClusterIP
  port: 5000
  targetPort: 5000

ingress:
  enabled: false
  labels: {}
  annotations: {}
  host: chart-example.local
  pathType: ImplementationSpecific

  tls:
    enabled: false
    secretName: chart-example.local

deployment:
  labels: {}
  annotations: {}
  pod:
    labels: {}
    annotations:
      prometheus.io/path: /internal-backstage/prometheus
      prometheus.io/port: "5000"
      prometheus.io/scrape: "true"
