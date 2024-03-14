import pytest
from unittest.mock import create_autospec, patch, call
from k8s.client import NotFound
from k8s.models.role_binding import RoleBinding
from fiaas_deploy_daemon.deployer.kubernetes.role_binding import RoleBindingDeployer
from fiaas_deploy_daemon.deployer.kubernetes.owner_references import OwnerReferences
from fiaas_deploy_daemon.config import Configuration


class TestRoleBindingDeployer:

    @pytest.fixture
    def owner_references(self):
        return create_autospec(OwnerReferences, spec_set=True, instance=True)

    @pytest.fixture
    def deployer(self, owner_references):
        config = create_autospec(Configuration([]), spec_set=True)
        config.list_of_roles = ["test-role-1", "test-role-2"]
        config.list_of_cluster_roles = ["cluster-role-1", "cluster-role-2"]
        return RoleBindingDeployer(config, owner_references)

    @pytest.mark.parametrize(
        "roles_list,role_kind",
        [
            (["test-role-1", "test-role-2"], "Role"),
            (["cluster-role-1", "cluster-role-2"], "ClusterRole"),
        ],
    )
    def test_create_bindings(self, deployer, owner_references, app_spec, roles_list, role_kind):
        with patch.object(RoleBinding, 'get') as mock_get, \
             patch.object(RoleBinding, 'save') as mock_save:

            mock_get.side_effect = NotFound
            deployer._update_or_create_role_bindings(app_spec, roles_list, role_kind, 1, {}, {}, [])

            mock_get.assert_has_calls([
                call(f"{app_spec.name}-1", app_spec.namespace),
                call(f"{app_spec.name}-2", app_spec.namespace)
            ])
            mock_save.assert_has_calls([
                call(),
                call()
            ])
            owner_references.apply.assert_called()

    def test_no_bindings_created_when_no_lists(self, deployer, owner_references, app_spec):
        roles_list = []
        cluster_roles_list = []
        role_kind = "Role"
        cluster_role_kind = "ClusterRole"
        with patch.object(RoleBinding, 'get') as mock_get_try_to_create, \
             patch.object(RoleBinding, 'save') as mock_try_to_save:

            deployer._update_or_create_role_bindings(app_spec, roles_list, role_kind, 1, {}, {}, [])
            deployer._update_or_create_role_bindings(app_spec, cluster_roles_list, cluster_role_kind, 1, {}, {}, [])

            mock_get_try_to_create.assert_not_called()
            mock_try_to_save.assert_not_called()
            owner_references.apply.assert_not_called()

    def test_deploy_full_flow(self, deployer, owner_references, app_spec):
        roles_list = ["test-role-1", "test-role-2"]
        cluster_roles_list = ["cluster-role-1", "cluster-role-2"]
        role_kind = "Role"
        with patch.object(RoleBinding, 'find') as mock_find, \
             patch.object(RoleBindingDeployer, '_update_or_create_role_bindings') as mock_create_role_bindings:

            mock_find.return_value = []

            deployer.deploy(app_spec, {})

            mock_find.assert_called()
            mock_create_role_bindings.assert_has_calls([
                call(app_spec, roles_list, role_kind, 1, {}, {}, []),
                call(app_spec, cluster_roles_list, "ClusterRole", 1, {}, {}, [])
            ])
