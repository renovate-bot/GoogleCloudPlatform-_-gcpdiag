# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Module containing Dataproc cluster creation diagnostic tree and custom steps."""

import json
from datetime import datetime

from gcpdiag import runbook, utils
from gcpdiag.queries import (crm, dataproc, gce, iam, logs, network,
                             networkmanagement)
from gcpdiag.runbook import op
from gcpdiag.runbook.crm import generalized_steps as crm_gs
from gcpdiag.runbook.dataproc import flags
from gcpdiag.runbook.iam import generalized_steps as iam_gs
from gcpdiag.runbook.logs import generalized_steps as logs_gs


class ClusterCreation(runbook.DiagnosticTree):
  """Provides a comprehensive analysis of common issues which affect Dataproc cluster creation.

  This runbook focuses on a range of potential problems for Dataproc clusters on
  Google Cloud Platform. By conducting a series of checks, the runbook aims to
  pinpoint the root cause of cluster creation difficulties.

  The following areas are examined:

  - Stockout errors: Evaluates Logs Explorer logs regarding stockout in the
  region/zone.

  - Quota availability: Checks for the quota availability in Dataproc cluster
  project.

  - Network configuration: Performs GCE Network Connectivity Tests, checks
  necessary firewall rules, external/internal IP configuration.

  - Cross-project configuration: Checks if the service account is not in the
  same
  project and reviews additional
    roles and organization policies enforcement.

  - Shared VPC configuration: Checks if the Dataproc cluster uses a Shared VPC
  network and
  evaluates if right service account roles are added.

  - Init actions script failures: Evaluates Logs Explorer
  logs regarding init actions script failures or timeouts.
  """

  parameters = {
      flags.PROJECT_ID: {
          'type': str,
          'help': 'The Project ID where the Dataproc cluster is located',
          'required': True,
      },
      flags.CLUSTER_NAME: {
          'type': str,
          'help': ('Dataproc cluster Name of an existing/active resource'),
          'deprecated': True,
          'new_parameter': 'dataproc_cluster_name',
      },
      flags.DATAPROC_CLUSTER_NAME: {
          'type': str,
          'help': ('Dataproc cluster Name of an existing/active resource'),
          'required': True,
      },
      flags.REGION: {
          'type': str,
          'help': 'Dataproc cluster Region',
          'required': True,
      },
      flags.CLUSTER_UUID: {
          'type': str,
          'help': 'Dataproc cluster UUID',
          # 'required': True, cannot be required due
          # to limitations on Dataproc API side
      },
      flags.PROJECT_NUMBER: {
          'type': str,
          'help': 'The Project Number where the Dataproc cluster is located',
      },
      flags.SERVICE_ACCOUNT: {
          'type':
              str,
          'help':
              ('Dataproc cluster Service Account used to create the resource'),
      },
      flags.CONSTRAINT: {
          'type':
              bool,
          'help': ('Checks if the Dataproc cluster has an enforced organization'
                   ' policy constraint'),
      },
      flags.STACKDRIVER: {
          'type': str,
          'help': ('Checks if stackdriver logging is enabled for further'
                   ' troubleshooting'),
          'default': True,
      },
      flags.ZONE: {
          'type': str,
          'help': 'Dataproc cluster Zone',
      },
      flags.NETWORK: {
          'type': str,
          'help': 'Dataproc cluster Network',
          'deprecated': True,
          'new_parameter': 'dataproc_network',
      },
      flags.DATAPROC_NETWORK: {
          'type': str,
          'help': 'Dataproc cluster Network',
      },
      flags.SUBNETWORK: {
          'type': str,
          'help': 'Dataproc cluster Subnetwork',
      },
      flags.INTERNAL_IP_ONLY: {
          'type':
              bool,
          'help': ('Checks if the Dataproc cluster has been created with only'
                   ' Internal IP'),
      },
      flags.START_TIME: {
          'type': datetime,
          'help': 'Start time of the issue',
      },
      flags.END_TIME: {
          'type': datetime,
          'help': 'End time of the issue',
      },
      flags.CROSS_PROJECT_ID: {
          'type':
              str,
          'help':
              ('Cross Project ID, where service account is located if it is not'
               ' in the same project as the Dataproc cluster'),
      },
      flags.HOST_VPC_PROJECT_ID: {
          'type': str,
          'help': 'Project ID of the Shared VPC network',
      },
  }

  def legacy_parameter_handler(self, parameters):
    """Handles legacy parameters."""
    if flags.CLUSTER_NAME in parameters:
      parameters[flags.DATAPROC_CLUSTER_NAME] = parameters.pop(
          flags.CLUSTER_NAME)
    if flags.NETWORK in parameters:
      parameters[flags.DATAPROC_NETWORK] = parameters.pop(flags.NETWORK)

  def build_tree(self):
    """Describes step relationships."""
    start = ClusterCreationStart()
    self.add_start(start)
    cluster_details_gateway = ClusterDetailsDependencyGateway()
    self.add_step(parent=start, child=cluster_details_gateway)
    self.add_end(ClusterCreationEnd())


class ClusterCreationStart(runbook.StartStep):
  """Initiates diagnostics for SSH Cluster Creation issues.

  This step interacts with the Dataproc API to get the cluster for investigation.
  When the cluster is found and it is in `ERROR` state, the cluster details
  are then used to set variables to be used by the subsequent child steps.
  """

  def execute(self):
    """
    Initiating diagnostics for Cluster Creation issues.
    """
    project = crm.get_project(op.get(flags.PROJECT_ID))
    op.put('cluster_exists', False)

    try:
      cluster = dataproc.get_cluster(project=op.get(flags.PROJECT_ID),
                                     region=op.get(flags.REGION),
                                     cluster_name=op.get(
                                         flags.DATAPROC_CLUSTER_NAME))
    except utils.GcpApiError as err:
      op.add_skipped(
          project,
          reason=
          (f'Could not get cluster {op.get(flags.DATAPROC_CLUSTER_NAME)}'
           f'in region {op.get(flags.REGION)} and project {op.get(flags.PROJECT_ID)}'
           f'due to {err}'))
    else:
      if cluster:
        op.put('cluster_exists', True)
        if cluster.status == 'ERROR':
          op.info(f'Cluster {op.get(flags.DATAPROC_CLUSTER_NAME)} in project' \
          f'{op.get(flags.PROJECT_ID)} is in error state')
          # set parameters required for the next stepsruinvestigates that require cluster details
          if not cluster.is_stackdriver_logging_enabled:
            op.put(flags.STACKDRIVER, cluster.is_stackdriver_logging_enabled)

          if not op.get(flags.SERVICE_ACCOUNT):
            if cluster.vm_service_account_email:
              op.put(flags.SERVICE_ACCOUNT, cluster.vm_service_account_email)
              op.info(f'Service Account:{cluster.vm_service_account_email}')

          if not op.get(flags.DATAPROC_NETWORK):
            if cluster.gce_network_uri:
              op.put(flags.DATAPROC_NETWORK, cluster.gce_network_uri)
              op.info(f'Network: {cluster.gce_network_uri}')

          if network.get_network_from_url(op.get(flags.DATAPROC_NETWORK)):
            op.put(
                flags.HOST_VPC_PROJECT_ID,
                network.get_network_from_url(op.get(
                    flags.DATAPROC_NETWORK)).project_id,
            )
        else:
          op.add_skipped(
              project,
              reason=
              (f'Cluster {op.get(flags.DATAPROC_CLUSTER_NAME)} in project '
               f'{op.get(flags.PROJECT_ID)} is not in error state due to cluster '
               f'creation issues, please choose another issue category to investigate.'
              ))


class ClusterCreationStockout(runbook.Step):
  """Check for cluster creation due to stockout"""

  def execute(self):
    """Check for stockout entries in Cloud logging"""
    stockout_error_logs = [
        'ZONE_RESOURCE_POOL_EXHAUSTED',
        'does not have enough resources available to fulfill the request',
        'resource pool exhausted',
        'does not exist in zone',
    ]
    message_filter = '"' + '" OR "'.join(stockout_error_logs) + '"'
    check_stockout_issue = logs_gs.CheckIssueLogEntry()
    check_stockout_issue.project_id = op.get(flags.PROJECT_ID)
    check_stockout_issue.filter_str = get_log_filter(
        cluster_name=op.get(flags.DATAPROC_CLUSTER_NAME),
        message_filter=f'protoPayload.status.message=~({message_filter})',
        log_id='cloudaudit.googleapis.com/activity',
    )
    check_stockout_issue.template = 'logging::dataproc_cluster_stockout'
    check_stockout_issue.resource_name = op.get(flags.DATAPROC_CLUSTER_NAME)
    check_stockout_issue.issue_pattern = stockout_error_logs
    self.add_child(child=check_stockout_issue)


class ClusterCreationQuota(runbook.Step):
  """Check for cluster creation errors due to insufficient quota"""

  def execute(self):
    """Check for quota entries in Cloud logging"""
    quota_log_match_str = 'Insufficient .* quota'
    check_quota_issues = logs_gs.CheckIssueLogEntry()
    check_quota_issues.project_id = op.get(flags.PROJECT_ID)
    check_quota_issues.filter_str = get_log_filter(
        cluster_name=op.get(flags.DATAPROC_CLUSTER_NAME),
        message_filter=f'protoPayload.status.message=~"{quota_log_match_str}"',
        log_id='cloudaudit.googleapis.com/activity',
    )
    check_quota_issues.template = 'logging::dataproc_cluster_quota'
    check_quota_issues.resource_name = op.get(flags.DATAPROC_CLUSTER_NAME)
    check_quota_issues.issue_pattern = [quota_log_match_str]

    self.add_child(child=check_quota_issues)


class ClusterDetailsDependencyGateway(runbook.Gateway):
  """Decision point for child steps that require cluster details and those that dont.

  Uses cluster details from the Dataproc API set in the start step to reduce scope of
  errors from invalid input
  """

  def execute(self):
    """Execute child steps depending on if they require details from existing cluster or not"""

    cluster_exists = op.get('cluster_exists', False)
    if cluster_exists:
      # add child steps that depend on cluster details from the API
      self.add_child(CheckInitScriptFailure())
      self.add_child(CheckClusterNetwork())
      self.add_child(InternalIpGateway())
      self.add_child(ServiceAccountExists())
      self.add_child(CheckSharedVPCRoles())
    else:
      # add child steps that do not depend on cluster details from the API
      self.add_child(ClusterCreationQuota())
      self.add_child(ClusterCreationStockout())


class CheckClusterNetwork(runbook.Step):
  """Verify that the nodes in the cluster can communicate with each other.

  The Compute Engine Virtual Machine instances (VMs) in a Dataproc cluster must
  be able to communicate with each other using ICMP, TCP (all ports), and UDP
  (all ports) protocols.
  """

  template = 'network::cluster_network'

  def execute(self):
    """Verify network connectivity among nodes in the cluster."""
    # Gathering cluster details.
    cluster = dataproc.get_cluster(project=op.get(flags.PROJECT_ID),
                                   region=op.get(flags.REGION),
                                   cluster_name=op.get(
                                       flags.DATAPROC_CLUSTER_NAME))
    # Skip this step if the cluster does not exist
    if cluster is None:
      op.add_uncertain(
          cluster,
          reason=op.prep_msg(op.UNCERTAIN_REASON),
          remediation=op.prep_msg(op.UNCERTAIN_REMEDIATION),
      )
    else:
      # Add the zone of the cluster
      if not op.get(flags.ZONE):
        if cluster.zone:
          op.put(flags.ZONE, cluster.zone)
          op.info(f'Zone: {cluster.zone}')

      # retrieve the zone from the cluster
      cluster_zone = op.get(flags.ZONE)
      if cluster_zone is None:
        op.add_skipped(
            cluster,
            reason=('Zone cannot be retrieved from the cluster. Zone:'
                    f' {cluster_zone}'),
        )
        return
      # Skip DPGKE clusters
      if not cluster.is_gce_cluster:
        op.add_skipped(
            cluster,
            reason='This is a Dataproc on GKE cluster, skipping this step.',
        )
      # Skip single node clusters
      if cluster.is_single_node_cluster:
        op.add_skipped(
            cluster,
            reason='This is a single node cluster, skipping this step.')
      # target (master node or master node 0)
      if cluster.is_ha_cluster:
        target = gce.get_instance(
            project_id=op.get(flags.PROJECT_ID),
            zone=cluster_zone,
            instance_name=f'{cluster.name}-m-0',
        )
      else:
        target = gce.get_instance(
            project_id=op.get(flags.PROJECT_ID),
            zone=cluster_zone,
            instance_name=f'{cluster.name}-m',
        )
      target_ip = target.get_network_ip_for_instance_interface(
          cluster.gce_network_uri)
      # source (worker node 0)
      source = gce.get_instance(
          project_id=op.get(flags.PROJECT_ID),
          zone=cluster_zone,
          instance_name=f'{cluster.name}-w-0',
      )
      source_ip = source.get_network_ip_for_instance_interface(
          cluster.gce_network_uri)

      is_connectivity_fine = True

      # run connectivity tests between master and worker
      op.info('Running connectivity tests.')
      # ICMP
      op.info('ICMP test.')
      connectivity_test_result = networkmanagement.run_connectivity_test(
          project_id=op.get(flags.PROJECT_ID),
          src_ip=str(source_ip)[:-3],
          dest_ip=str(target_ip)[:-3],
          dest_port=None,
          protocol='ICMP',
      )
      op.info('Connectivity test result: ' +
              connectivity_test_result['reachabilityDetails']['result'])
      if (connectivity_test_result['reachabilityDetails']['result']
          != 'REACHABLE'):
        is_connectivity_fine = False
        for trace in connectivity_test_result['reachabilityDetails']['traces']:
          op.info('Endpoint details: ' +
                  json.dumps(trace['endpointInfo'], indent=2))
          last_step = None
          for step in trace['steps']:
            last_step = step
          op.info('Last step: ' + json.dumps(last_step, indent=2))
          op.info('Full list of steps: ' + json.dumps(trace['steps'], indent=2))
        op.info('ICMP traffic must be allowed. Check the result of the'
                ' connectivity ' +
                'test to verify what is blocking the traffic, ' +
                'in particular Last step and Full list of steps.')
      # TCP
      op.info('TCP test.')
      connectivity_test_result = networkmanagement.run_connectivity_test(
          project_id=op.get(flags.PROJECT_ID),
          src_ip=str(source_ip)[:-3],
          dest_ip=str(target_ip)[:-3],
          dest_port=8088,
          protocol='TCP',
      )
      op.info('Connectivity test result: ' +
              connectivity_test_result['reachabilityDetails']['result'])
      if (connectivity_test_result['reachabilityDetails']['result']
          != 'REACHABLE'):
        is_connectivity_fine = False
        for trace in connectivity_test_result['reachabilityDetails']['traces']:
          op.info('Endpoint details: ' +
                  json.dumps(trace['endpointInfo'], indent=2))
          last_step = None
          for step in trace['steps']:
            last_step = step
          op.info('Last step: ' + json.dumps(last_step, indent=2))
          op.info('Full list of steps: ' + json.dumps(trace['steps'], indent=2))
        op.info(
            'TCP traffic must be allowed. Check the result of the connectivity'
            ' test' + 'to verify what is blocking the traffic, ' +
            'in particular Last step and Full list of steps.')
      # UCP
      op.info('UDP test.')
      connectivity_test_result = networkmanagement.run_connectivity_test(
          project_id=op.get(flags.PROJECT_ID),
          src_ip=str(source_ip)[:-3],
          dest_ip=str(target_ip)[:-3],
          dest_port=8088,
          protocol='UDP',
      )
      op.info('Connectivity test result: ' +
              connectivity_test_result['reachabilityDetails']['result'])
      if (connectivity_test_result['reachabilityDetails']['result']
          != 'REACHABLE'):
        is_connectivity_fine = False
        for trace in connectivity_test_result['reachabilityDetails']['traces']:
          op.info('Endpoint details: ' +
                  json.dumps(trace['endpointInfo'], indent=2))
          last_step = None
          for step in trace['steps']:
            last_step = step
          op.info('Last step: ' + json.dumps(last_step, indent=2))
          op.info('Full list of steps: ' + json.dumps(trace['steps'], indent=2))
        op.info(
            'UDP traffic must be allowed. Check the result of the connectivity'
            ' test ' + 'to verify what is blocking the traffic, ' +
            'in particular Last step and Full list of steps.')

      if is_connectivity_fine:
        op.add_ok(cluster,
                  op.prep_msg(op.SUCCESS_REASON, cluster_name=cluster.name))
      else:
        op.add_failed(
            cluster,
            reason=op.prep_msg(op.FAILURE_REASON, cluster_name=cluster.name),
            remediation=op.prep_msg(op.FAILURE_REMEDIATION),
        )


class InternalIpGateway(runbook.Gateway):
  """Check if the cluster is using internal IP only.

  Check if the Dataproc cluster that is isolated from the public internet
  whose VM instances communicate over a private IP subnetwork (cluster VMs are
  not assigned public IP addresses).
  """

  def execute(self):
    """Checking if the cluster is using internal IP only."""
    # Gathering cluster details.
    cluster = dataproc.get_cluster(project=op.get(flags.PROJECT_ID),
                                   region=op.get(flags.REGION),
                                   cluster_name=op.get(
                                       flags.DATAPROC_CLUSTER_NAME))
    is_internal_ip_only = None
    # If cluster cannot be found, gather details from flags
    if cluster is None:
      is_internal_ip_only = op.get(flags.INTERNAL_IP_ONLY)
      if is_internal_ip_only is None:
        op.add_skipped(
            cluster,
            'The cluster and the internalIpOnly config cannot be found,'
            ' skipping this step. ' +
            'Please provide internal_ip_only as input parameter ' +
            'if the cluster is deleted or keep the cluster in error state.',
        )
        return
      subnetwork_uri = op.get(flags.SUBNETWORK)
      if subnetwork_uri is None:
        op.add_skipped(
            cluster,
            'The cluster and the subnetworkUri config cannot be found, skipping'
            ' this step. '
            'Please provide subnetwork_uri as input parameter '
            'if the cluster is deleted or keep the cluster in error state.',
        )
        return
    else:
      is_internal_ip_only = cluster.is_internal_ip_only
      subnetwork_uri = cluster.gce_subnetwork_uri
    # Add the related configs of the cluster
    if is_internal_ip_only is not None and subnetwork_uri is not None:
      # Add the internal IP config of the cluster
      if not op.get(flags.INTERNAL_IP_ONLY):
        if cluster.is_internal_ip_only is not None:
          op.put(flags.INTERNAL_IP_ONLY, cluster.is_internal_ip_only)
          op.info(f'Internal IP only: {cluster.is_internal_ip_only}')
      # Add the subnetwork of the cluster
      if not op.get(flags.SUBNETWORK):
        op.put(flags.SUBNETWORK, subnetwork_uri)
        op.add_ok(cluster, reason=f'Subnetwork: {subnetwork_uri}')
    # If the cluster is in private subnet, check that PGA is enabled
    # otherwise end this step
    if is_internal_ip_only:
      self.add_child(child=CheckPrivateGoogleAccess())
    else:
      op.add_ok(cluster, reason='The cluster is in a public subnet.')


class CheckPrivateGoogleAccess(runbook.Step):
  """Check if the subnetwork of the cluster has private google access enabled.

  Checking if the subnetwork of the cluster has private google access enabled.
  """

  template = 'network::private_google_access'

  def execute(self):
    """Checking if the subnetwork of the cluster has private google access enabled."""
    # taking cluster details
    cluster = dataproc.get_cluster(project=op.get(flags.PROJECT_ID),
                                   region=op.get(flags.REGION),
                                   cluster_name=op.get(
                                       flags.DATAPROC_CLUSTER_NAME))
    subnetwork_uri = op.get(flags.SUBNETWORK)
    subnetwork_obj = network.get_subnetwork_from_url(subnetwork_uri)

    if subnetwork_obj.is_private_ip_google_access():
      op.add_ok(
          cluster,
          reason=op.prep_msg(op.SUCCESS_REASON, subnetwork_uri=subnetwork_uri),
      )

    else:
      op.add_failed(
          cluster,
          reason=op.prep_msg(op.FAILURE_REASON, subnetwork_uri=subnetwork_uri),
          remediation=op.prep_msg(op.FAILURE_REMEDIATION),
      )


class ServiceAccountExists(runbook.Gateway):
  """Verify service account and permissions in Dataproc cluster project or another project.

  Decides whether to check for service account roles
  - in CROSS_PROJECT_ID, if specified by customer
  - in PROJECT_ID
  """

  template = 'permissions::projectcheck'

  def execute(self):
    """Checking service account project."""
    sa_email = op.get(flags.SERVICE_ACCOUNT)
    project = crm.get_project(op.get(flags.PROJECT_ID))
    op.info(op.get(flags.SERVICE_ACCOUNT))
    if sa_email is None:
      op.add_skipped(
          project,
          reason='Service account not provided as input parameter',
      )
      return
    sa_exists = iam.is_service_account_existing(email=sa_email,
                                                billing_project_id=op.get(
                                                    flags.PROJECT_ID))
    cross_project = op.get(flags.CROSS_PROJECT_ID)
    # Only check in cross project when the flag is provided
    sa_exists_cross_project = False
    if cross_project:
      sa_exists_cross_project = iam.is_service_account_existing(
          email=sa_email, billing_project_id=cross_project)

    if sa_exists:
      op.info(
          'VM Service Account associated with Dataproc cluster was found in the'
          ' same project')
      op.info('Checking permissions.')
      # Check for Service Account permissions
      sa_permission_check = iam_gs.IamPolicyCheck()
      sa_permission_check.project = op.get(flags.PROJECT_ID)
      sa_permission_check.principal = (
          f'serviceAccount:{op.get(flags.SERVICE_ACCOUNT)}')
      sa_permission_check.require_all = True
      sa_permission_check.roles = ['roles/dataproc.worker']
      self.add_child(child=sa_permission_check)
    elif sa_exists_cross_project:
      op.info('VM Service Account associated with Dataproc cluster was found in'
              ' cross project')
      # Check if constraint is enforced
      op.info('Checking constraints on service account project.')
      orgpolicy_constraint_check = crm_gs.OrgPolicyCheck()
      orgpolicy_constraint_check.project = op.get(flags.CROSS_PROJECT_ID)
      orgpolicy_constraint_check.constraint = (
          'constraints/iam.disableCrossProjectServiceAccountUsage')
      orgpolicy_constraint_check.is_enforced = False
      self.add_child(orgpolicy_constraint_check)

      # Check Service Account roles
      op.info('Checking roles in service account project.')
      sa_permission_check = iam_gs.IamPolicyCheck()
      sa_permission_check.project = op.get(flags.CROSS_PROJECT_ID)
      sa_permission_check.principal = (
          f'serviceAccount:{op.get(flags.SERVICE_ACCOUNT)}')
      sa_permission_check.require_all = True
      sa_permission_check.roles = [
          'roles/iam.serviceAccountUser',
          'roles/dataproc.worker',
      ]
      self.add_child(child=sa_permission_check)

      # Check Service Agent Service Account roles
      op.info('Checking service agent service account roles on service account'
              ' project.')
      # project = crm.get_project(op.get(flags.PROJECT_ID))
      service_agent_sa = (
          f'service-{project.number}@dataproc-accounts.iam.gserviceaccount.com')
      service_agent_permission_check = iam_gs.IamPolicyCheck()
      service_agent_permission_check.project = op.get(flags.CROSS_PROJECT_ID)
      service_agent_permission_check.principal = (
          f'serviceAccount:{service_agent_sa}')
      service_agent_permission_check.require_all = True
      service_agent_permission_check.roles = [
          'roles/iam.serviceAccountUser',
          'roles/iam.serviceAccountTokenCreator',
      ]
      self.add_child(child=service_agent_permission_check)

      # Check Compute Agent Service Account
      op.info('Checking compute agent service account roles on service account'
              ' project.')
      compute_agent_sa = (
          f'service-{project.number}@compute-system.iam.gserviceaccount.com')
      compute_agent_permission_check = iam_gs.IamPolicyCheck()
      compute_agent_permission_check.project = op.get(flags.CROSS_PROJECT_ID)
      compute_agent_permission_check.principal = (
          f'serviceAccount:{compute_agent_sa}')
      compute_agent_permission_check.require_all = True
      compute_agent_permission_check.roles = [
          'roles/iam.serviceAccountTokenCreator'
      ]
      self.add_child(child=compute_agent_permission_check)
    elif cross_project and not sa_exists_cross_project:
      op.add_failed(
          project,
          reason=op.prep_msg(
              op.FAILURE_REASON,
              service_account=op.get(flags.SERVICE_ACCOUNT),
              project_id=op.get(flags.PROJECT_ID),
              cross_project_id=cross_project,
          ),
          remediation=op.prep_msg(op.FAILURE_REMEDIATION),
      )
    else:
      op.add_uncertain(
          project,
          reason=op.prep_msg(
              op.UNCERTAIN_REASON,
              service_account=op.get(flags.SERVICE_ACCOUNT),
              project_id=op.get(flags.PROJECT_ID),
          ),
          remediation=op.prep_msg(op.UNCERTAIN_REMEDIATION),
      )


class CheckSharedVPCRoles(runbook.Step):
  """Verify if dataproc cluster is using Shared VPC.

  Checks for missing roles.
  """

  def execute(self):
    """Verify service account roles based on Shared VPC."""
    project = crm.get_project(op.get(flags.PROJECT_ID))
    if op.get(flags.HOST_VPC_PROJECT_ID) and (op.get(flags.HOST_VPC_PROJECT_ID)
                                              != op.get(flags.PROJECT_ID)):
      # Check Service Agent Service Account role:
      service_agent_sa = (
          f'service-{project.number}@dataproc-accounts.iam.gserviceaccount.com')
      service_agent_vpc_permission_check = iam_gs.IamPolicyCheck()
      service_agent_vpc_permission_check.project = op.get(
          flags.HOST_VPC_PROJECT_ID)
      service_agent_vpc_permission_check.principal = (
          f'serviceAccount:{service_agent_sa}')
      service_agent_vpc_permission_check.require_all = True
      service_agent_vpc_permission_check.roles = ['roles/compute.networkUser']
      self.add_child(child=service_agent_vpc_permission_check)

      # Check Google APIs Service Account
      op.info('Checking Google APIs service account roles on host VPC project.')
      api_sa = f'{project.number}@cloudservices.gserviceaccount.com'
      api_vpc_permission_check = iam_gs.IamPolicyCheck()
      api_vpc_permission_check.project = op.get(flags.HOST_VPC_PROJECT_ID)
      api_vpc_permission_check.principal = f'serviceAccount:{api_sa}'
      api_vpc_permission_check.require_all = True
      api_vpc_permission_check.roles = ['roles/compute.networkUser']
      self.add_child(child=api_vpc_permission_check)
    else:
      op.add_skipped(project,
                     reason='Cluster is not using a Shared VPC network')


class CheckInitScriptFailure(runbook.Step):
  """Verify if dataproc cluster init script failed.

  The initialization action provided during cluster creation failed to install.
  """
  template = 'logs_related::cluster_init'

  def execute(self):
    """Verify Cluster init script failure."""

    init_script_log_match = 'Initialization action failed'
    cluster_name = op.get(flags.DATAPROC_CLUSTER_NAME)
    project = crm.get_project(op.get(flags.PROJECT_ID))

    log_search_filter = f"""resource.type="cloud_dataproc_cluster"
    jsonPayload.message=~"{init_script_log_match}"
    resource.labels.cluster_name="{cluster_name}"
    severity=ERROR
    log_id("google.dataproc.agent")"""

    log_entries = logs.realtime_query(
        project_id=op.get(flags.PROJECT_ID),
        filter_str=log_search_filter,
        start_time=op.get(flags.START_TIME),
        end_time=op.get(flags.END_TIME),
    )
    if log_entries:
      op.add_failed(
          project,
          reason=op.prep_msg(op.FAILURE_REASON,
                             cluster_name=op.get(flags.DATAPROC_CLUSTER_NAME)),
          remediation=op.prep_msg(op.FAILURE_REMEDIATION),
      )
    else:
      op.add_ok(
          project,
          reason=op.prep_msg(
              op.SUCCESS_REASON,
              cluster_name=op.get(flags.DATAPROC_CLUSTER_NAME),
              project_id=op.get(flags.PROJECT_ID),
          ),
      )


class ClusterCreationEnd(runbook.EndStep):
  """The end step of the runbook.

  It points out all the failed steps to the user.
  """

  def execute(self):
    """This is the end step of the runbook."""
    if op.get('cluster_exists', False):
      op.info(
          """Please visit all the FAIL steps and address the suggested remediations.
          If the cluster is still not able to be provisioned successfully,
          run the runbook again and open a Support case. If you are missing
          Service Account permissions, but are not able to see the Service Agent
          Service Account go to the IAM page and check 'Include Google-provided
          role grants'
        """)
    else:
      op.info(
          f"""Some steps were skipped because cluster {op.get(flags.DATAPROC_CLUSTER_NAME)}
          could not be found in project {op.get(flags.PROJECT_ID)}. Most steps in this runbook
          require that the cluster is in `ERROR` state and has not been deleted.
          If the cluster was in `ERROR` and has been deleted, please create the cluster again and
          rerun this runbook before deleting the cluster to rule out any cluster creation issues."""
      )


def get_log_filter(
    cluster_name,
    message_filter,
    log_id,
):
  """Returns log filter string for given parameters.

  Args:
    cluster_name:
    message_filter:
    log_id:
  """

  log_search_filter = f"""
    resource.type="cloud_dataproc_cluster"
    {message_filter}
    resource.labels.cluster_name="{cluster_name}"
    severity=ERROR
    log_id("{log_id}")
    """
  return log_search_filter
