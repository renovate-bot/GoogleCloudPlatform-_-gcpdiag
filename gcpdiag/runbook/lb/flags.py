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
"""Contains LB specific flags"""
# pylint: disable=unused-wildcard-import, wildcard-import
from gcpdiag.runbook.iam.flags import *

BACKEND_SERVICE_NAME = 'backend_service_name'
CERTIFICATE_NAME = 'certificate_name'
REGION = 'region'
FORWARDING_RULE_NAME = 'forwarding_rule_name'
BACKEND_LATENCY_THRESHOLD = 'backend_latency_threshold'
REQUEST_COUNT_THRESHOLD = 'request_count_threshold'
ERROR_RATE_THRESHOLD = 'error_rate_threshold'
