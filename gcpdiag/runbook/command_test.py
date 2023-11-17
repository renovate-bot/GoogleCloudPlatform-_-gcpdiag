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
"""Test code in command.py."""

from gcpdiag import runbook
from gcpdiag.runbook import command

MUST_HAVE_MODULES = {'gce'}


class Test:
  """Unit tests for command."""

  # pylint: disable=protected-access
  def test_flatten_multi_arg(self):
    assert not list(command._flatten_multi_arg([]))
    assert list(command._flatten_multi_arg(['gce/test'])) == ['gce/test']

  # pylint: disable=protected-access
  def test_init_args_parser(self):
    parser = command._init_runbook_args_parser()
    args = parser.parse_args(['product/runbook', '--project', 'myproject'])
    assert args.project == 'myproject'
    assert args.runbook == ['product/runbook']
    assert args.billing_project is None
    assert args.auth_adc is False
    assert args.auth_key is None
    assert args.verbose == 0
    assert args.within_days == 1
    assert args.logging_ratelimit_requests is None
    assert args.logging_ratelimit_period_seconds is None
    assert args.logging_page_size is None
    assert args.logging_fetch_max_entries is None
    assert args.logging_fetch_max_time_seconds is None
    assert args.auto is False

  # pylint: disable=protected-access
  def test_provided_init_args_parser(self):
    parser = command._init_runbook_args_parser()
    args = parser.parse_args(
        ['product/runbook', '--project', 'myproject', '--auto'])
    assert args.auto is True
    args = parser.parse_args([
        'product/runbook', '--project', 'myproject', '--parameter', 'test=test'
    ])
    assert args.parameter == {'test': 'test'}

  # pylint: disable=protected-access
  def test_load_repository_rules(self):
    repo = runbook.RunbookRuleRepository()
    command._load_repository_rules(repo)
    modules = {r.product for r in repo.rules_to_run}
    assert MUST_HAVE_MODULES.issubset(modules)
