import logging

from k8s.models.common import ObjectMeta
from k8s.models.role_binding import RoleBinding, RoleRef, Subject
from k8s.client import NotFound
from fiaas_deploy_daemon.specs.models import AppSpec
from fiaas_deploy_daemon.deployer.kubernetes.owner_references import OwnerReferences
from fiaas_deploy_daemon.tools import merge_dicts

LOG = logging.getLogger(__name__)


class RoleBindingDeployer:
    def __init__(self, config, owner_references):
        self._config = config
        self._owner_references: OwnerReferences = owner_references

    def deploy(self, app_spec: AppSpec, labels):
        custom_annotations = {}
        custom_labels = labels
        custom_labels = merge_dicts(app_spec.labels.role_binding, custom_labels)
        custom_annotations = merge_dicts(app_spec.annotations.role_binding, custom_annotations)
        self._create_role_bindings(app_spec, self._config.list_of_roles, "Role", 1, custom_annotations, custom_labels)
        self._create_role_bindings(app_spec, self._config.list_of_cluster_roles, "ClusterRole", 1 + len(self._config.list_of_roles),
                                   custom_annotations, custom_labels)

    def _create_role_bindings(self, app_spec: AppSpec, roles_list, role_kind, counter, custom_annotations, custom_labels):
        LOG.info("Creating RoleBindings for %s", app_spec.name)
        namespace = app_spec.namespace

        service_account_name = app_spec.name

        for role_name in roles_list:
            role_binding_name = f"{app_spec.name}-{counter}"
            try:
                role_binding = RoleBinding.get(role_binding_name, namespace)
            except NotFound:
                role_binding = RoleBinding()

            role_binding.metadata = ObjectMeta(
                name=role_binding_name, namespace=namespace, labels=custom_labels, annotations=custom_annotations
            )

            role_ref = RoleRef(kind=role_kind, apiGroup="rbac.authorization.k8s.io", name=role_name)
            subject = Subject(kind="ServiceAccount", name=service_account_name, namespace=namespace)
            role_binding.roleRef = role_ref
            role_binding.subjects = [subject]
            self._owner_references.apply(role_binding, app_spec)
            role_binding.save()

            counter += 1

    def _owned_by_fiaas(self, role_binding):
        return any(
            ref.apiVersion == "fiaas.schibsted.io/v1" and ref.kind == "Application"
            for ref in role_binding.metadata.ownerReferences
        )
