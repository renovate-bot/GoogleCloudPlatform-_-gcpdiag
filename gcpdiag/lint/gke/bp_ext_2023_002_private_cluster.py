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
""" GKE clusters are private clusters.

A private cluster is a type of VPC-native cluster that only depends on internal IP addresses.
Nodes, Pods, and Services in a private cluster require unique subnet IP address ranges.

Private clusters are used when the applications and services are needed to be isolated from
the outside connections completely.
This ensures the workloads are private and not exposed to untrusted sources.

"""

from gcpdiag import lint, models
from gcpdiag.queries import gke

clusters_by_project = {}


def prepare_rule(context: models.Context):
  clusters_by_project[context.project_id] = gke.get_clusters(context)


def run_rule(context: models.Context, report: lint.LintReportRuleInterface):
  clusters = clusters_by_project[context.project_id]
  if not clusters:
    report.add_skipped(None, 'no clusters found')
  for _, c in sorted(clusters.items()):
    if not c.is_private:
      report.add_failed(c, ' is a public cluster')
    else:
      report.add_ok(c)
