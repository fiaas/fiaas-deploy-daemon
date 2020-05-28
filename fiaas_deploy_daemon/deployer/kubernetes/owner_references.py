from k8s.models.common import OwnerReference


class OwnerReferences(object):

    def apply(self, k8s_model, app_spec):
        if app_spec.uid:
            owner_reference = OwnerReference(apiVersion="fiaas.schibsted.io/v1",
                                             blockOwnerDeletion=True,
                                             controller=True,
                                             kind="Application",
                                             name=app_spec.name,
                                             uid=app_spec.uid)

            k8s_model.metadata.ownerReferences = [owner_reference]
