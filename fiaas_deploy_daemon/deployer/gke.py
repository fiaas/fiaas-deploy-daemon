from googleapiclient import discovery
from googleapiclient.errors import HttpError
from oauth2client.client import GoogleCredentials
from six.moves import http_client
import time
import os
import sys
import configargparse

GCE_PROJECT_ID = "fiaas-gke"
GCE_REGION = "europe-west1"
DNS_TIME_TO_LIVE = "300"


class Gke(object):

    def __init__(self, env):
        self.env = env
        self.dns_managed_zone = self._get_gc_project_id() + "-" + env
        self.dns_suffix = "k8s-gke." + env + ".finn.no"
        self.gce_service = None
        self.dns_service = None

    @staticmethod
    def _get_gc_project_id():
        return os.getenv('GCE_PROJECT_ID', GCE_PROJECT_ID)

    @staticmethod
    def _get_gc_region():
        return os.getenv('GCE_REGION', GCE_REGION)

    def get_or_create_static_ip(self, app_name):
        ip = self._get_existing_static_ip(app_name)
        if ip is None:
            self._reserve_ip_address(app_name)
            ip = self._get_existing_static_ip(app_name)

        return ip

    def _reserve_ip_address(self, app_name):
        address_name = self._address_name(app_name)
        operation = self._get_gce_service().addresses().insert(project=self._get_gc_project_id(),
                                                               region=self._get_gc_region(), body={"name": address_name}).execute()
        self._wait_for_result(operation[u'name'])

    def _get_existing_static_ip(self,  app_name):
        address_name = self._address_name(app_name)
        try:
            result = self._get_gce_service().addresses().get(project=self._get_gc_project_id(),
                                                             region=self._get_gc_region(), address=address_name).execute()
            return result[u'address'] if result is not None else None
        except HttpError as e:
            if e.resp.status == http_client.NOT_FOUND:
                return None
            else:
                raise e

    def _address_name(self, app_name):
        return app_name + "-k8s-" + self.env

    def get_or_create_dns(self, app_name, ip):
        a_name = app_name + "." + self.dns_suffix + "."
        rrset = self._get_resource_record_set(a_name)
        if rrset is None:
            self._create_dns_record(a_name, ip)
        elif self._get_ip_from_dns(rrset) != ip:
            self._update_dns_record(a_name, self._get_ip_from_dns(rrset), ip)

    def _get_resource_record_set(self, a_name):
        try:
            result = self._get_dns_service().resourceRecordSets().list(project=self._get_gc_project_id(),
                                                                       managedZone=self.dns_managed_zone,
                                                                       name=a_name).execute()
            return result[u'rrsets'] if len(result[u'rrsets']) > 0 else None
        except HttpError as e:
            if e.resp.status == http_client.NOT_FOUND:
                return None
            else:
                raise e

    def _create_dns_record(self, a_name, ip):
        additions = [{
            'name': a_name,
            'type': "A",
            'rrdatas': [ip],
            "ttl": DNS_TIME_TO_LIVE
        }]

        body = {"additions": additions, "type": "A", "name": a_name}
        self._get_dns_service().changes().create(project=self._get_gc_project_id(),
                                                 managedZone=self.dns_managed_zone,
                                                 body=body).execute()

    def _update_dns_record(self, a_name, old_ip, ip):
        deletions = [{
            'name': a_name,
            'type': "A",
            'rrdatas': [old_ip],
            "ttl": DNS_TIME_TO_LIVE
        }]
        additions = [{
            'name': a_name,
            'type': "A",
            'rrdatas': [ip],
            "ttl": DNS_TIME_TO_LIVE
        }]

        body = {"deletions": deletions, "additions": additions, "type": "A", "name": a_name}
        self._get_dns_service().changes().create(project=self._get_gc_project_id(),
                                                 managedZone=self.dns_managed_zone,
                                                 body=body).execute()

    def _get_ip_from_dns(self, rrset):
        return rrset[0][u'rrdatas'][0] if rrset is not None and len(rrset) == 1 else None

    def _get_dns_service(self):
        if self.dns_service is not None:
            return self.dns_service

        credentials = GoogleCredentials.get_application_default()
        self.dns_service = discovery.build('dns', 'v1', credentials=credentials)
        return self.dns_service

    def _get_gce_service(self):
        if self.gce_service is not None:
            return self.gce_service

        credentials = GoogleCredentials.get_application_default()
        self.gce_service = discovery.build('compute', 'v1', credentials=credentials)
        return self.gce_service

    def _wait_for_result(self, operation):
        while True:
            result = self.gce_service.regionOperations().get(
                    project=self._get_gc_project_id(),
                    region=self._get_gc_region(),
                    operation=operation).execute()

            if result['status'] == 'DONE':
                return result
            else:
                time.sleep(1)

    @staticmethod
    def create_dns_with_static_ip():
        parser = configargparse.ArgParser()
        parser.add_argument('env', help="the environment (dev|ci|prod)", default=None)
        parser.add_argument('app', help="name of the app, will be the first part of the dns entry", default=None)

        options = parser.parse_args()

        gke = Gke(options.env)
        ip = gke.get_or_create_static_ip(options.app)
        gke.get_or_create_dns(options.app, ip)
        return ip

if __name__ == '__main__':
    ip = Gke.create_dns_with_static_ip()
    sys.stdout.write(ip)
    sys.exit(os.EX_OK)
