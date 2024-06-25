# Copyright 2024 Google LLC
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
"""Module containing steps to analyse knowns issue logged into Serial Console logs"""

import mimetypes

import googleapiclient.errors

from gcpdiag import config, runbook
from gcpdiag.queries import crm, gce
from gcpdiag.runbook import op
from gcpdiag.runbook.gce import constants as gce_const
from gcpdiag.runbook.gce import flags
from gcpdiag.runbook.gce import generalized_steps as gce_gs


class SerialLogAnalyser(runbook.DiagnosticTree):
  """ GCE VM Serial log analyser

    This runbook is designed to assist you in investigating the serial console logs of a vm.

    Key Investigation Areas:

    Boot Issues:
        - Check for Boot issues happening due to Kernel Panics
        - Check for GRUB related issues.
        - Check if system failed to find boot disk.
        - Check if Filesystem corruption is causing issues with system boot.
        - Check if "/" Filesystem consumption is causing issues with system boot.

    Memory crunch issues:
        - Check if OOM kills happened on the VM or any other memory related issues.

    Network related issues:
        - Check if metadata server became unreachable since last boot.
        - Check if there are any time sync related errors.

    SSHD checks:
        - Check if we have logs related to scuccessful startup of SSHD service.

    Google Guest Agent checks:
        - Check if we have logs related to scuccessful startup of Google Guest Agent.
    """

  # Specify parameters common to all steps in the diagnostic tree class.
  parameters = {
      flags.PROJECT_ID: {
          'type': str,
          'help':
              ('The Project ID associated with the VM for which you want to \
                analyse the Serial logs.'),
          'required': True
      },
      flags.NAME: {
          'type': str,
          'help':
              'The name of the VM, for which you want to analyse the Serial logs.'
              ' Or provide the id i.e -p name=<str>',
          'required': True
      },
      flags.ID: {
          'type': str,
          'help':
              'The instance-id of the VM, for which you want to analyse the Serial logs.'
              ' Or provide the id i.e -p id=<int>'
      },
      flags.ZONE: {
          'type': str,
          'help': 'The Google Cloud zone where the VM is located.',
          'required': True
      },
      flags.SERIAL_CONSOLE_FILE: {
          'type': str,
          'help': 'Absolute path of files contailing the Serial console logs,'
                  ' in case if gcpdiag is not able to reach the VM Serial logs.'
                  ' i.e -p serial_console_file="filepath1,filepath2" ',
      }
  }

  def build_tree(self):
    """Building Decision Tree"""
    start = FetchVmDetails()
    self.add_start(step=start)

    # Checking if all logs available since last boot of the instance
    log_start_point = gce_gs.VmSerialLogsCheck()
    log_start_point.template = 'vm_serial_log::serial_log_start_point'
    log_start_point.positive_pattern = gce_const.SERIAL_LOG_START_POINT
    self.add_step(parent=start, child=log_start_point)

    # Check for Boot related issues
    kernel_panic = gce_gs.VmSerialLogsCheck()
    kernel_panic.template = 'vm_serial_log::kernel_panic'
    kernel_panic.negative_pattern = gce_const.KERNEL_PANIC_LOGS
    self.add_step(parent=log_start_point, child=kernel_panic)

    # Checking for Filesystem corruption related errors
    fs_corruption = gce_gs.VmSerialLogsCheck()
    fs_corruption.template = 'vm_serial_log::linux_fs_corruption'
    fs_corruption.negative_pattern = gce_const.FS_CORRUPTION_MSG
    self.add_step(parent=log_start_point, child=fs_corruption)

    # Checking for Filesystem utilization related messages
    fs_util = gce_gs.VmSerialLogsCheck()
    fs_util.template = 'vm_performance::high_disk_utilization_error'
    fs_util.negative_pattern = gce_const.DISK_EXHAUSTION_ERRORS
    self.add_step(parent=log_start_point, child=fs_util)

    # Checking for OOM related errors
    oom_errors = gce_gs.VmSerialLogsCheck()
    oom_errors.template = 'vm_performance::memory_error'
    oom_errors.negative_pattern = gce_const.OOM_PATTERNS
    self.add_step(parent=log_start_point, child=oom_errors)

    # Checking for network related errors
    network_issue = gce_gs.VmSerialLogsCheck()
    network_issue.template = 'vm_serial_log::network_errors'
    network_issue.negative_pattern = gce_const.NETWORK_ERRORS
    self.add_step(parent=log_start_point, child=network_issue)

    # Checking for Time Sync related errors
    timesync_issue = gce_gs.VmSerialLogsCheck()
    timesync_issue.template = 'vm_serial_log::time_sync_issue'
    timesync_issue.negative_pattern = gce_const.TIME_SYNC_ERROR
    self.add_step(parent=log_start_point, child=timesync_issue)

    # Check for issues in SSHD configuration or behavior.
    sshd_check = gce_gs.VmSerialLogsCheck()
    sshd_check.template = 'vm_serial_log::sshd'
    sshd_check.positive_pattern = gce_const.GOOD_SSHD_PATTERNS
    self.add_step(parent=log_start_point, child=sshd_check)

    # Check for Guest Agent status
    guest_agent_check = gce_gs.VmSerialLogsCheck()
    guest_agent_check.template = 'vm_serial_log::guest_agent'
    guest_agent_check.positive_pattern = gce_const.GUEST_AGENT_STATUS_MSG
    self.add_step(parent=log_start_point, child=guest_agent_check)

    self.add_end(AnalysingSerialLogsEnd())


class FetchVmDetails(runbook.StartStep):
  """Fetching VM details ..."""

  template = 'vm_attributes::running'

  def execute(self):
    """Fetching VM details"""

    project = crm.get_project(op.get(flags.PROJECT_ID))
    try:
      vm = gce.get_instance(project_id=op.get(flags.PROJECT_ID),
                            zone=op.get(flags.ZONE),
                            instance_name=op.get(flags.NAME))
    except googleapiclient.errors.HttpError:
      op.add_skipped(
          project,
          reason=('Instance {} does not exist in zone {} or project {}').format(
              op.get(flags.NAME), op.get(flags.ZONE), op.get(flags.PROJECT_ID)))
    else:
      if vm and vm.is_running:
        # Check for instance id and instance name
        if not op.get(flags.ID):
          op.put(flags.ID, vm.id)
        elif not op.get(flags.NAME):
          op.put(flags.NAME, vm.name)
      else:
        op.add_failed(vm,
                      reason=op.prep_msg(op.FAILURE_REASON,
                                         vm_name=vm.name,
                                         status=vm.status),
                      remediation=op.prep_msg(op.FAILURE_REMEDIATION,
                                              vm_name=vm.name,
                                              status=vm.status))

    # file sanity checks
    if op.get(flags.SERIAL_CONSOLE_FILE):
      for file in op.get(flags.SERIAL_CONSOLE_FILE).split(','):
        try:
          with open(file, 'rb') as f:
            results = mimetypes.guess_type(file)[0]
            if results and not results.startswith('text/'):
              # Peek at content for further clues
              content_start = f.read(1024)  # Read a small chunk
              # Check for gzip and xz magic number (first two bytes)
              if content_start.startswith(
                  b'\x1f\x8b') or content_start.startswith(b'\xfd'):
                op.add_skipped(
                    vm,
                    reason=('File {} appears to be compressed, not plain text.'
                           ).format(file))
              else:
                # If not gzip or tar, try simple text encoding detection (UTF-8, etc.)
                try:
                  content_start.decode()
                except UnicodeDecodeError:
                  op.add_skipped(
                      vm,
                      reason=('File {} does not appear to be plain text.'
                             ).format(file))

        except FileNotFoundError:
          op.add_skipped(
              vm,
              reason=('The file {} does not exists. Please verify if '
                      'you have provided the correct absolute file path'
                     ).format(file))


class AnalysingSerialLogsEnd(runbook.EndStep):
  """Finalizing Serial console Log Analysis..."""

  def execute(self):
    """Finalizing Serial console Log Analysis..."""
    if not config.get(flags.INTERACTIVE_MODE):
      response = op.prompt(
          kind=op.CONFIRMATION,
          message=
          f'Are you able to find issues related to {op.get(flags.NAME)}?',
          choice_msg='Enter an option: ')
      if response == op.NO:
        op.info(message=op.END_MESSAGE)
