import pytest
from unittest.mock import create_autospec, patch, call
from k8s.client import NotFound
from k8s.models.common import ObjectMeta, OwnerReference
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

    @pytest.fixture
    def cr_A_role_binding(self):
        role_binding = create_autospec(RoleBinding, spec_set=True, instance=True)
        role_binding.roleRef.kind = "ClusterRole"
        role_binding.roleRef.name = "RoleA"
        return role_binding
    
    @pytest.fixture
    def r_A_role_binding(self):
        role_binding = create_autospec(RoleBinding, spec_set=True, instance=True)
        role_binding.roleRef.kind = "Role"
        role_binding.roleRef.name = "RoleA"
        return role_binding

    @pytest.mark.parametrize(
        "roles_list,role_kind",
        [
            (["test-role-1", "test-role-2"], "Role"),
            (["cluster-role-1", "cluster-role-2"], "ClusterRole"),
        ],
    )
    def test_create_bindings_with_empty_role_bindings(self, deployer, owner_references, app_spec, roles_list, role_kind):
        with patch.object(RoleBinding, 'save') as mock_save:

            deployer._update_or_create_role_bindings(app_spec, roles_list, role_kind, {}, {}, [])

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
        with patch.object(RoleBinding, 'save') as mock_try_to_save:

            deployer._update_or_create_role_bindings(app_spec, roles_list, role_kind, {}, {}, [])
            deployer._update_or_create_role_bindings(app_spec, cluster_roles_list, cluster_role_kind, {}, {}, [])

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
                call(app_spec, roles_list, role_kind, {}, {}, []),
                call(app_spec, cluster_roles_list, "ClusterRole", {}, {}, [])
            ])

    def test_create_bindings_with_role_in_role_bindings_not_owned_by_fiaas(self, deployer, owner_references, app_spec, r_A_role_binding):    

        deployer._update_or_create_role_bindings(app_spec, ["RoleA"], "Role", {}, {}, [r_A_role_binding])

        r_A_role_binding.save.assert_not_called()
        owner_references.apply.assert_not_called()

    def test_create_bindings_with_role_in_role_bindings_owned_by_fiaas(self, deployer, owner_references, app_spec, r_A_role_binding):  
        r_A_role_binding.metadata = ObjectMeta(ownerReferences=[OwnerReference(apiVersion="fiaas.schibsted.io/v1", kind="Application")])

        deployer._update_or_create_role_bindings(app_spec, ["RoleA"], "Role", {}, {}, [r_A_role_binding])

        r_A_role_binding.save.assert_called()
        owner_references.apply.assert_called()

    def test_create_bindings_with_role_in_role_bindings_owned_by_fiaas_as_cluster_role(self, deployer, owner_references, app_spec,
                                                                                       cr_A_role_binding):
        with patch.object(RoleBinding, 'save') as mock_save:
            
            cr_A_role_binding.metadata = ObjectMeta(ownerReferences=[OwnerReference(apiVersion="fiaas.schibsted.io/v1", kind="Application")])

            deployer._update_or_create_role_bindings(app_spec, ["RoleA"], "Role", {}, {}, [cr_A_role_binding])

            cr_A_role_binding.save.assert_not_called()
            mock_save.assert_called()
            owner_references.apply.assert_called()
    
    def test_create_bindings_with_multiple_cases(self, deployer, owner_references, app_spec, r_A_role_binding, cr_A_role_binding):
        with patch.object(RoleBinding, 'save') as mock_save:
        
            cr_A_role_binding.metadata = ObjectMeta(ownerReferences=[OwnerReference(apiVersion="fiaas.schibsted.io/v1", kind="Application")])
            r_A_role_binding.metadata = ObjectMeta(ownerReferences=[OwnerReference(apiVersion="fiaas.schibsted.io/v1", kind="Application")])
            role_binding = create_autospec(RoleBinding, spec_set=True, instance=True)
            role_binding.roleRef.kind = "Role"
            role_binding.roleRef.name = "RoleC"
            
            deployer._update_or_create_role_bindings(app_spec, ["RoleA", "RoleB", "RoleC"], "Role", {}, {}, [cr_A_role_binding, r_A_role_binding, role_binding])

            cr_A_role_binding.save.assert_not_called()
            r_A_role_binding.save.assert_called()
            role_binding.save.assert_not_called()
            mock_save.assert_called()
            owner_references.apply.assert_called()

    def clean_role_bindings_should_delete_roles_not_in_role_list(self, deployer):
        r_role_binding = create_autospec(RoleBinding, spec_set=True, instance=True)
        r_role_binding.roleRef.kind = "Role"
        r_role_binding.roleRef.name = "test-role-1"
        cr_role_binding = create_autospec(RoleBinding, spec_set=True, instance=True)
        cr_role_binding.roleRef.kind = "ClusterRole"
        cr_role_binding.roleRef.name = "test-role-1"
        r2_role_binding = create_autospec(RoleBinding, spec_set=True, instance=True)
        r2_role_binding.roleRef.kind = "Role"
        r2_role_binding.roleRef.name = "test-role-3"
        cr2_role_binding = create_autospec(RoleBinding, spec_set=True, instance=True)
        cr2_role_binding.roleRef.kind = "ClusterRole"
        cr2_role_binding.roleRef.name = "test-role-3"
        cr2_role_binding.metadata = ObjectMeta(ownerReferences=[OwnerReference(apiVersion="fiaas.schibsted.io/v1", kind="Application")])

        role_bindings = [r_role_binding, cr_role_binding, r2_role_binding, cr2_role_binding]

        deployer._clean_not_needed_role_bindings(role_bindings)

        assert len(role_bindings) == 2
        assert r_role_binding in role_bindings
        assert cr_role_binding in role_bindings
        assert r2_role_binding not in role_bindings
        assert cr2_role_binding not in role_bindings
        r_role_binding.delete.assert_not_called()
        cr_role_binding.delete.assert_not_called()
        r2_role_binding.delete.assert_not_called()
        cr2_role_binding.delete.assert_called()
