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
"""Test class for cloudrun/Service_deployment"""

from gcpdiag import config
from gcpdiag.runbook import cloudrun, snapshot_test_base


class TestInvalidContainer(snapshot_test_base.RulesSnapshotTestBase):
  rule_pkg = cloudrun
  runbook_name = 'cloudrun/service-deployment'
  project_id = 'gcpdiag-cloudrun2-aaaa'
  config.init({'auto': True, 'interface': 'cli'}, project_id)

  rule_parameters = [
      {
          'service_name': 'invalid-container',
          'region': 'us-central1',
      },
      {
          'service_name': 'image-does-not-exist',
          'region': 'us-central1',
      },
      {
          'service_name': 'no-image-permission',
          'region': 'us-central1',
      },
  ]
