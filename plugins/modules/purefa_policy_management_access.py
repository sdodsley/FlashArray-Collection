#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2026, Simon Dodsley (simon@everpuredata.com)
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

ANSIBLE_METADATA = {
    "metadata_version": "1.1",
    "status": ["preview"],
    "supported_by": "community",
}

DOCUMENTATION = r"""
---
module: purefa_policy_management_access
version_added: '1.44.0'
short_description: Manage management-access (RBAC) policies on Everpure FlashArrays
description:
- Create, delete and modify management-access policies on Everpure FlashArrays.
- A management-access policy grants a role a set of permissions scoped to a
  resource, such as a realm, and is the object used for realm-scoped RBAC.
- These policies are also reported by M(everpure.flasharray.purefa_info).
author:
- Everpure Ansible Team (@sdodsley) <pure-ansible-team@everpuredata.com>
options:
  name:
    description:
    - The name of the management-access policy.
    type: str
    required: true
  state:
    description:
    - Define whether the policy should exist or not.
    type: str
    default: present
    choices: [ absent, present ]
  enabled:
    description:
    - Define whether the policy is enabled and grants its permissions.
    type: bool
    default: true
  aggregation_strategy:
    description:
    - How the permissions from this policy combine with other policies that
      apply to the same user.
    - C(least-common-permissions) restricts users to no more than the access
      defined here.
    - C(all-permissions) allows users to also receive access from other
      policies that apply to them.
    type: str
    default: all-permissions
    choices: [ all-permissions, least-common-permissions ]
  rename:
    description:
    - New name for an existing management-access policy.
    type: str
  rules:
    description:
    - List of scoped-role rules that make up the policy.
    - Replaces the full set of rules on the policy when provided.
    type: list
    elements: dict
    suboptions:
      role:
        description:
        - Name of the role granted by this rule, for example C(storage) or
          C(array_admin).
        type: str
        required: true
      scope:
        description:
        - Name of the resource the role is scoped to, for example a realm name.
        type: str
        required: true
      resource_type:
        description:
        - Type of the scoped resource.
        type: str
        default: realms
  context:
    description:
    - Name of fleet member on which to perform the operation.
    - This requires the array receiving the request is a member of a fleet
      and the context name to be a member of the same fleet.
    type: str
    default: ""
extends_documentation_fragment:
- everpure.flasharray.everpure.fa
"""

EXAMPLES = r"""
- name: Create a realm-scoped management-access policy for the storage role
  everpure.flasharray.purefa_policy_management_access:
    name: myrealm_admin
    aggregation_strategy: least-common-permissions
    rules:
      - role: storage
        scope: myrealm
        resource_type: realms
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592

- name: Disable a management-access policy
  everpure.flasharray.purefa_policy_management_access:
    name: myrealm_admin
    enabled: false
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592

- name: Delete a management-access policy
  everpure.flasharray.purefa_policy_management_access:
    name: myrealm_admin
    state: absent
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592
"""

RETURN = r"""
"""

MIN_API_VERSION = "2.36"
CONTEXT_VERSION = "2.38"

HAS_PYPURECLIENT = True
try:
    from pypureclient.flasharray import (
        PolicyManagementAccessPost,
        PolicyManagementAccessPatch,
        PolicyrulemanagementaccessRules,
        ReferenceNoId,
        ReferenceWithType,
    )
except ImportError:
    HAS_PYPURECLIENT = False

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.everpure.flasharray.plugins.module_utils.purefa import (
    get_array,
    purefa_argument_spec,
)
from ansible_collections.everpure.flasharray.plugins.module_utils.version import (
    LooseVersion,
)
from ansible_collections.everpure.flasharray.plugins.module_utils.api_helpers import (
    check_response,
    get_with_context,
    post_with_context,
    patch_with_context,
    delete_with_context,
)


def _desired_rules(module):
    """Normalised (role, scope, resource_type) tuples from module params"""
    return sorted(
        (rule["role"], rule["scope"], rule["resource_type"])
        for rule in (module.params["rules"] or [])
    )


def _current_rules(policy):
    """Normalised (role, scope, resource_type) tuples from an existing policy"""
    current = []
    for rule in getattr(policy, "rules", None) or []:
        current.append(
            (
                getattr(rule.role, "name", None),
                getattr(rule.scope, "name", None),
                getattr(rule.scope, "resource_type", None),
            )
        )
    return sorted(current)


def _build_rules(module):
    """Build the SDK rule objects from module params"""
    return [
        PolicyrulemanagementaccessRules(
            role=ReferenceNoId(name=rule["role"]),
            scope=ReferenceWithType(
                name=rule["scope"], resource_type=rule["resource_type"]
            ),
        )
        for rule in (module.params["rules"] or [])
    ]


def get_policy(module, array):
    """Return the management-access policy or None"""
    res = get_with_context(
        array,
        "get_policies_management_access",
        CONTEXT_VERSION,
        module,
        names=[module.params["name"]],
    )
    if res.status_code == 200:
        policies = list(res.items)
        if policies:
            return policies[0]
    return None


def create_policy(module, array):
    """Create a management-access policy"""
    changed = True
    if not module.check_mode:
        res = post_with_context(
            array,
            "post_policies_management_access",
            CONTEXT_VERSION,
            module,
            names=[module.params["name"]],
            policy=PolicyManagementAccessPost(
                enabled=module.params["enabled"],
                aggregation_strategy=module.params["aggregation_strategy"],
                rules=_build_rules(module),
            ),
        )
        check_response(
            res,
            module,
            f"Failed to create management access policy {module.params['name']}",
        )
    module.exit_json(changed=changed)


def update_policy(module, array, policy):
    """Update a management-access policy"""
    changed = False
    patch_kwargs = {}
    if module.params["enabled"] != getattr(policy, "enabled", None):
        patch_kwargs["enabled"] = module.params["enabled"]
    if module.params["aggregation_strategy"] != getattr(
        policy, "aggregation_strategy", None
    ):
        patch_kwargs["aggregation_strategy"] = module.params["aggregation_strategy"]
    if module.params["rules"] is not None and _desired_rules(module) != _current_rules(
        policy
    ):
        patch_kwargs["rules"] = _build_rules(module)

    if patch_kwargs:
        changed = True
        if not module.check_mode:
            res = patch_with_context(
                array,
                "patch_policies_management_access",
                CONTEXT_VERSION,
                module,
                names=[module.params["name"]],
                policy=PolicyManagementAccessPatch(**patch_kwargs),
            )
            check_response(
                res,
                module,
                f"Failed to update management access policy {module.params['name']}",
            )

    if module.params["rename"] and module.params["rename"] != module.params["name"]:
        changed = True
        if not module.check_mode:
            res = patch_with_context(
                array,
                "patch_policies_management_access",
                CONTEXT_VERSION,
                module,
                names=[module.params["name"]],
                policy=PolicyManagementAccessPatch(name=module.params["rename"]),
            )
            check_response(
                res,
                module,
                f"Failed to rename management access policy {module.params['name']}",
            )
    module.exit_json(changed=changed)


def delete_policy(module, array):
    """Delete a management-access policy"""
    changed = True
    if not module.check_mode:
        res = delete_with_context(
            array,
            "delete_policies_management_access",
            CONTEXT_VERSION,
            module,
            names=[module.params["name"]],
        )
        check_response(
            res,
            module,
            f"Failed to delete management access policy {module.params['name']}",
        )
    module.exit_json(changed=changed)


def main():
    argument_spec = purefa_argument_spec()
    argument_spec.update(
        dict(
            name=dict(type="str", required=True),
            state=dict(type="str", default="present", choices=["absent", "present"]),
            enabled=dict(type="bool", default=True),
            aggregation_strategy=dict(
                type="str",
                default="all-permissions",
                choices=["all-permissions", "least-common-permissions"],
            ),
            rename=dict(type="str"),
            rules=dict(
                type="list",
                elements="dict",
                options=dict(
                    role=dict(type="str", required=True),
                    scope=dict(type="str", required=True),
                    resource_type=dict(type="str", default="realms"),
                ),
            ),
            context=dict(type="str", default=""),
        )
    )

    module = AnsibleModule(argument_spec, supports_check_mode=True)

    if not HAS_PYPURECLIENT:
        module.fail_json(msg="py-pure-client sdk is required for this module")

    state = module.params["state"]
    array = get_array(module)
    api_version = array.get_rest_version()
    if LooseVersion(MIN_API_VERSION) > LooseVersion(api_version):
        module.fail_json(
            msg="Management access policies require Purity//FA 6.6.9, or higher "
            "(REST 2.36)."
        )

    policy = get_policy(module, array)

    if state == "present" and not policy:
        create_policy(module, array)
    elif state == "present" and policy:
        update_policy(module, array, policy)
    elif state == "absent" and policy:
        delete_policy(module, array)
    else:
        module.exit_json(changed=False)


if __name__ == "__main__":
    main()
