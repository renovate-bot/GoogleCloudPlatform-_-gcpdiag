# Lint as: python3
"""Queries related to GCP Kubernetes Engine clusters."""

import functools
import logging
import re
from typing import Dict, Iterable, List, Mapping

import googleapiclient.errors

from gcp_doctor import config, models, utils
from gcp_doctor.queries import apis


class NodePool(models.Resource):
  """Represents a GKE node pool."""

  def __init__(self, project_id, resource_data):
    super().__init__(project_id=project_id)
    self._resource_data = resource_data

  def get_full_path(self) -> str:
    # https://container.googleapis.com/v1/projects/gcpd-gke-1-9b90/
    #   locations/europe-west1/clusters/gke2/nodePools/default-pool
    m = re.match(r'https://container.googleapis.com/v1/(.*)',
                 self._resource_data.get('selfLink', ''))
    if not m:
      raise RuntimeError('can\'t parse selfLink of nodepool resource')
    return m.group(1)

  def get_short_path(self) -> str:
    path = self.get_full_path()
    path = re.sub(r'^projects/', '', path)
    path = re.sub(r'/locations/', '/', path)
    path = re.sub(r'/zones/', '/', path)
    path = re.sub(r'/clusters/', '/', path)
    path = re.sub(r'/nodePools/', '/', path)
    return path

  @property
  def service_account(self) -> str:
    sa = self._resource_data.get('config', {}).get('serviceAccount', None)
    if sa == 'default':
      return f'{self.project_nr}-compute@developer.gserviceaccount.com'
    else:
      return sa


class Cluster(models.Resource):
  """Represents a GKE cluster.

  https://cloud.google.com/kubernetes-engine/docs/reference/rest/v1/projects.locations.clusters#Cluster
  """
  _resource_data: dict

  def __init__(self, project_id, resource_data):
    super().__init__(project_id=project_id)
    self._resource_data = resource_data

  @property
  def name(self) -> str:
    return self._resource_data['name']

  @property
  def location(self) -> str:
    return self._resource_data['location']

  def get_full_path(self) -> str:
    if utils.is_region(self._resource_data['location']):
      return (f'projects/{self.project_id}/'
              f'locations/{self.location}/clusters/{self.name}')
    else:
      return (f'projects/{self.project_id}/'
              f'zones/{self.location}/clusters/{self.name}')

  def get_short_path(self) -> str:
    path = self.get_full_path()
    path = re.sub(r'^projects/', '', path)
    path = re.sub(r'/locations/', '/', path)
    path = re.sub(r'/zones/', '/', path)
    path = re.sub(r'/clusters/', '/', path)
    return path

  def has_logging_enabled(self) -> bool:
    return self._resource_data['loggingService'] != 'none'

  def has_monitoring_enabled(self) -> bool:
    return self._resource_data['monitoringService'] != 'none'

  @property
  def nodepools(self) -> Iterable[NodePool]:
    nodepools: List[NodePool] = []
    for n in self._resource_data.get('nodePools', []):
      nodepools.append(NodePool(self.project_id, n))
    return nodepools


@functools.lru_cache(maxsize=None)
def get_clusters(context: models.Context) -> Mapping[str, Cluster]:
  """Get a list of Cluster matching the given context."""
  clusters: Dict[str, Cluster] = {}
  container_api = apis.get_api('container', 'v1')
  for project_id in context.projects:
    logging.info('fetching list of GKE clusters in project %s', project_id)
    query = container_api.projects().locations().clusters().list(
        parent=f'projects/{project_id}/locations/-')
    try:
      resp = query.execute(num_retries=config.API_RETRIES)
      if 'clusters' not in resp:
        return clusters
      for resp_c in resp['clusters']:
        # verify that we some minimal data that we expect
        if 'name' not in resp_c or 'location' not in resp_c:
          raise RuntimeError(
              'missing data in projects.locations.clusters.list response')
        if not context.match_project_resource(
            location=resp_c['location'], labels=resp_c.get('resourceLabels')):
          continue
        c = Cluster(project_id=project_id, resource_data=resp_c)
        clusters[c.get_full_path()] = c
    except googleapiclient.errors.HttpError as err:
      errstr = utils.http_error_message(err)
      # TODO: implement proper exception classes
      raise ValueError(
          f'can\'t list clusters for project {project_id}: {errstr}') from err
  return clusters
