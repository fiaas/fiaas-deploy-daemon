import pytest

from k8s.models.common import ObjectMeta, OwnerReference
from k8s.models.ingress import Ingress

from fiaas_deploy_daemon.deployer.kubernetes.owner_references import OwnerReferences


class TestOwnerReferences(object):

    @pytest.fixture
    def owner_references(self):
        return OwnerReferences()

    @pytest.fixture
    def expected(self, app_spec):
        expected = OwnerReference(apiVersion="fiaas.schibsted.io/v1",
                                  kind="Application",
                                  controller=True,
                                  blockOwnerDeletion=True,
                                  name=app_spec.name,
                                  uid=app_spec.uid)
        return expected

    def test_apply(self, app_spec, owner_references, expected):
        ingress = Ingress(metadata=ObjectMeta())

        owner_references.apply(ingress, app_spec)

        assert ingress.metadata.ownerReferences == [expected]

    def test_apply_with_no_uid(self, app_spec, owner_references):
        ingress = Ingress(metadata=ObjectMeta())
        app_spec = app_spec._replace(uid=None)

        owner_references.apply(ingress, app_spec)

        assert ingress.metadata.ownerReferences == []
