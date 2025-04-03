# Copyright 2025 Google LLC
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
"""Test class for gce/GuestosBootup"""

from gcpdiag import config
from gcpdiag.runbook import gce, snapshot_test_base


class Test(snapshot_test_base.RulesSnapshotTestBase):
  rule_pkg = gce
  runbook_name = 'gce/guestos-bootup'
  config.init({'auto': True, 'interface': 'cli'})

  rule_parameters = [{
      'project_id': 'gcpdiag-gce-vm-performance',
      'instance_name': 'faulty-linux-ssh',
      'zone': 'europe-west2-a'
  }, {
      'project_id': 'gcpdiag-gce-vm-performance',
      'instance_name': 'valid-linux-ssh',
      'zone': 'europe-west2-a'
  }]
