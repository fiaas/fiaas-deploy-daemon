import logging

from k8s.models.common import ObjectMeta
from k8s.models.role_binding import RoleBinding, RoleRef, Subject
from k8s.client import NotFound
from fiaas_deploy_daemon.specs.models import AppSpec
from fiaas_deploy_daemon.deployer.kubernetes.owner_references import OwnerReferences

LOG = logging.getLogger(__name__)


class RoleBindingDeployer:
    def __init__(self, config, owner_references):
        self._config = config
        self._owner_references: OwnerReferences = owner_references

    def deploy(self, app_spec: AppSpec):
        self._create_role_bindings(app_spec, self._config.list_of_roles, "Role", 1)
        self._create_role_bindings(app_spec, self._config.list_of_cluster_roles, "ClusterRole", 1 + len(self._config.list_of_roles))

    def _create_role_bindings(self, app_spec: AppSpec, roles_list, role_kind, counter):
        LOG.info("Creating RoleBindings for %s", app_spec.name)
        namespace = app_spec.namespace

        if self._config.enable_service_account_per_app:
            service_account_name = app_spec.name
        else:
            service_account_name = "default"

        for i, role_name in enumerate(roles_list):
            role_binding_name = f"{app_spec.name}-{counter}"
            try:
                role_binding = RoleBinding.get(role_binding_name, namespace)
            except NotFound:
                role_binding = RoleBinding()

            role_binding.metadata = ObjectMeta(
                name=role_binding_name, namespace=namespace
            )

            role_ref = RoleRef(kind=role_kind, apiGroup="rbac.authorization.k8s.io", name=role_name)
            subject = Subject(kind="ServiceAccount", name=service_account_name, namespace=namespace)
            role_binding.roleRef = role_ref
            role_binding.subjects = [subject]
            self._owner_references.apply(role_binding, app_spec)
            role_binding.save()

            counter += 1

    def delete(self, app_spec):
        LOG.info("Deleting rolebinding for %s", f"{app_spec.name}")
        try:
            RoleBinding.delete(f"{app_spec.name}", app_spec.namespace)
        except NotFound:
            pass

    def _owned_by_fiaas(self, service_account):
        return any(
            ref.apiVersion == "fiaas.schibsted.io/v1" and ref.kind == "Application"
            for ref in service_account.metadata.ownerReferences
        )
