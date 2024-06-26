# Copyright 2023 Google LLC
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

# Lint as: python3
"""Test code in notebooks.py"""

from unittest import mock

from gcpdiag import models
from gcpdiag.queries import apis_stub, notebooks

DUMMY_PROJECT_NAME = 'gcpdiag-notebooks1-aaaa'
DUMMY_PROJECT_NAME2 = 'gcpdiag-notebooks2-aaaa'
DUMMY_INSTANCE_NAME = 'gcpdiag-notebooks1instance-aaaa'
DUMMY_INSTANCE_OK_NAME = 'notebooks2instance-ok'
DUMMY_INSTANCE_PROVISIONING_STUCK_NAME = 'notebooks2instance-provisioning-stuck'
DUMMY_ZONE = 'us-west1-a'
DUMMY_REGION = 'us-west1'
DUMMY_INSTANCE_FULL_PATH_NAME = \
  f'projects/{DUMMY_PROJECT_NAME}/locations/{DUMMY_ZONE}/instances/{DUMMY_INSTANCE_NAME}'
DUMMY_INSTANCE_OK_FULL_PATH_NAME = \
  f'projects/{DUMMY_PROJECT_NAME2}/locations/{DUMMY_ZONE}/instances/{DUMMY_INSTANCE_OK_NAME}'
DUMMY_RUNTIME_NAME = 'gcpdiag-notebooks1runtime-aaaa'
DUMMY_RUNTIME_FULL_PATH_NAME = \
  f'projects/{DUMMY_PROJECT_NAME}/locations/{DUMMY_REGION}/runtimes/{DUMMY_RUNTIME_NAME}'
DUMMY_PERM = 'domain:google.com'
DUMMY_HEALTH_STATE = notebooks.HealthStateEnum('UNHEALTHY')
DUMMY_IS_UPGRADEABLE = True
DUMMY_NOT_UPGRADEABLE = False


@mock.patch('gcpdiag.queries.apis.get_api', new=apis_stub.get_api_stub)
class TestNotebooks:
  """Test Vertex AI Workbench Notebooks"""

  def test_get_instances(self):
    context = models.Context(project_id=DUMMY_PROJECT_NAME)
    instances = notebooks.get_instances(context=context)
    assert DUMMY_INSTANCE_FULL_PATH_NAME in instances

  def test_get_runtimes(self):
    context = models.Context(project_id=DUMMY_PROJECT_NAME)
    runtimes = notebooks.get_runtimes(context=context)
    assert DUMMY_RUNTIME_FULL_PATH_NAME in runtimes

  def test_get_instance_health(self):
    context = models.Context(project_id=DUMMY_PROJECT_NAME)
    instance_health_state = notebooks.get_instance_health_state(
        context=context, name=DUMMY_INSTANCE_FULL_PATH_NAME)
    assert DUMMY_HEALTH_STATE == instance_health_state

  def test_instance_is_upgradeable(self):
    context = models.Context(project_id=DUMMY_PROJECT_NAME)
    instance_is_upgradeable = notebooks.instance_is_upgradeable(
        context=context, notebook_instance=DUMMY_INSTANCE_FULL_PATH_NAME)
    assert DUMMY_IS_UPGRADEABLE == instance_is_upgradeable.get('upgradeable')

  def test_get_instance(self):
    instance = notebooks.get_workbench_instance(
        project_id=DUMMY_PROJECT_NAME2,
        zone=DUMMY_ZONE,
        instance_name=DUMMY_INSTANCE_OK_NAME)
    assert DUMMY_INSTANCE_OK_NAME in instance.name

  def test_instance_check_upgradability(self):
    instance_upgradability = notebooks.workbench_instance_check_upgradability(
        project_id=DUMMY_PROJECT_NAME2,
        workbench_instance_name=DUMMY_INSTANCE_OK_FULL_PATH_NAME)
    assert DUMMY_NOT_UPGRADEABLE == instance_upgradability.get('upgradeable')
