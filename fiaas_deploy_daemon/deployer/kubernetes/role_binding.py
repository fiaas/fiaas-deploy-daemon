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
        self._owner_references: OwnerReferences = owner_references
        self._list_of_roles = config.list_of_roles
        self._list_of_cluster_roles = config.list_of_cluster_roles

    def deploy(self, app_spec: AppSpec, labels):
        custom_annotations = {}
        custom_labels = labels
        custom_labels = merge_dicts(app_spec.labels.role_binding, custom_labels)
        custom_annotations = merge_dicts(app_spec.annotations.role_binding, custom_annotations)
        # Getting list of rolebindings with the label app=app_name
        role_bindings = RoleBinding.find(name=app_spec.name, namespace=app_spec.namespace)
        self._clean_not_needed_role_bindings(role_bindings)
        counter = 1
        self._update_or_create_role_bindings(app_spec, self._list_of_roles, "Role", counter, custom_annotations, custom_labels,
                                             role_bindings)
        self._update_or_create_role_bindings(app_spec, self._list_of_cluster_roles, "ClusterRole", counter, custom_annotations,
                                             custom_labels, role_bindings)

    def _update_or_create_role_bindings(self, app_spec: AppSpec, roles_list, role_kind, counter, custom_annotations, custom_labels,
                                        role_bindings):
        LOG.info("Creating RoleBindings for %s", app_spec.name)
        namespace = app_spec.namespace

        service_account_name = app_spec.name

        for role_name in roles_list:
            role_binding = self._find_role_in_role_bindings(role_kind, role_name, role_bindings)
            if role_binding:
                if self._owned_by_fiaas(role_binding):
                    role_binding_name = role_binding.metadata.name
                else:
                    LOG.info(
                        "Aborting the creation of a roleBinding for Application: %s with %s: %s",
                        app_spec.name,
                        role_kind,
                        role_name
                    )
                    break
            else:
                while (True):
                    role_binding_name = f"{app_spec.name}-{counter}"
                    try:
                        role_binding = RoleBinding.get(role_binding_name, namespace)
                        counter += 1
                    except NotFound:
                        role_binding = RoleBinding()
                        counter += 1
                        break
            self._deploy_role_binding(app_spec, role_kind, custom_annotations, custom_labels, namespace,
                                      service_account_name, role_name, role_binding, role_binding_name)

    def _deploy_role_binding(self, app_spec, role_kind, custom_annotations, custom_labels, namespace,
                             service_account_name, role_name, role_binding, role_binding_name):
        role_binding.metadata = ObjectMeta(
                            name=role_binding_name, namespace=namespace, labels=custom_labels, annotations=custom_annotations
                        )

        role_ref = RoleRef(kind=role_kind, apiGroup="rbac.authorization.k8s.io", name=role_name)
        subject = Subject(kind="ServiceAccount", name=service_account_name, namespace=namespace)
        role_binding.roleRef = role_ref
        role_binding.subjects = [subject]
        self._owner_references.apply(role_binding, app_spec)
        role_binding.save()

    def _find_role_in_role_bindings(self, role_kind, role_name, role_bindings: list[RoleBinding]):
        for role_binding in role_bindings:
            if role_binding.roleRef.kind == role_kind and role_binding.roleRef.name == role_name:
                return role_binding
            return None

    def _clean_not_needed_role_bindings(self, role_bindings: list[RoleBinding]):
        for role_binding in role_bindings:
            if not self._check_if_matches(role_binding):
                if self._owned_by_fiaas(role_binding):
                    RoleBinding.delete(role_binding.metadata.name, role_binding.metadata.namespace)
                    role_bindings.remove(role_binding)

    def _owned_by_fiaas(self, role_binding):
        return any(
            ref.apiVersion == "fiaas.schibsted.io/v1" and ref.kind == "Application"
            for ref in role_binding.metadata.ownerReferences
        )

    # Check if matches the role_binding with any role or clusterRole in the list_of_roles or list_of_cluster_roles
    def _check_if_matches(self, role_binding):
        return (not (role_binding.roleRef.kind == "Role" and role_binding.roleRef.name in self._list_of_roles)
                and not (role_binding.roleRef.kind == "ClusterRole" and role_binding.roleRef.name in self._list_of_cluster_roles))
