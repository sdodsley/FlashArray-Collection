#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2019, Simon Dodsley (simon@everpuredata.com)
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
module: purefa_snmp_agent
version_added: '1.16.0'
short_description: Configure the FlashArray SNMP Agent
description:
- Manage the I(localhost) SNMP Agent on a Everpure FlashArray.
- Only the readable agent settings are compared, which are the version,
  the v3 user, the v3 auth and privacy protocols and whether a v2c
  community string is set. The array returns the community string and the
  passphrases masked, so a change to only the value of I(community),
  I(auth_passphrase) or I(privacy_passphrase) cannot be detected and is
  not applied. Clear the setting with I(state=absent) first to replace it.
author:
- Everpure Ansible Team (@sdodsley) <pure-ansible-team@everpuredata.com>
options:
  state:
    type: str
    description:
    - Used to set or clear the SNMP v2c community string or the SNMP v3
      auth and privacy protocols.
    choices: [ absent, present ]
    default: present
  user:
    type: str
    description:
    - SNMP v3 only. User ID which must be between 1 and 32 characters.
  version:
    type: str
    description:
    - Version of SNMP protocol to use for the manager.
    choices: [ v2c, v3 ]
    default: v2c
  community:
    type: str
    description:
    - SNMP v2c only. Manager community ID under which Purity//FA is to
      communicate with the specified managers.
    - To remove the string set I(state) to I(absent) with I(version)
      set to I(v2c)
  auth_passphrase:
    type: str
    description:
    - SNMP v3 only. Passphrade used by Purity//FA to authenticate the
      array with the specified managers.
    - Must be between 8 and 63 non-space ASCII characters.
  auth_protocol:
    type: str
    description:
    - SNMP v3 only. Encryption protocol to use
    - To remove the privacy and auth protocols set I(state) to
      I(absent) with I(version) set to I(v3)
    choices: [ MD5, SHA ]
  privacy_passphrase:
    type: str
    description:
    - SNMP v3 only. Passphrase to encrypt SNMP messages.
      Must be between 8 and 63 non-space ASCII characters.
  privacy_protocol:
    type: str
    description:
    - SNMP v3 only. Encryption protocol to use
    - To remove the privacy and auth protocols set I(state) to
      I(absent) with I(version) set to I(v3)
    choices: [ AES, DES ]
extends_documentation_fragment:
- everpure.flasharray.everpure.fa
"""

EXAMPLES = r"""
- name: Clear SNMP agent v2c community string
  everpure.flasharray.purefa_snmp_agent:
    version: v2c
    state: absent
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592
- name: Clear SNMP agent v3 auth and privacy protocols
  everpure.flasharray.purefa_snmp_agent:
    version: v3
    user: admin
    state: absent
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592
- name: Update v2c SNMP agent
  everpure.flasharray.purefa_snmp_agent:
    version: v2c
    community: public
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592
- name: Update v3 SNMP manager
  everpure.flasharray.purefa_snmp_agent:
    version: v3
    user: admin
    auth_protocol: MD5
    auth_passphrase: password
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592
"""

RETURN = r"""
"""

HAS_PURESTORAGE = True
try:
    from pypureclient import flasharray
except ImportError:
    HAS_PURESTORAGE = False

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
)

MIN_REQUIRED_API_VERSION = "2.1"


def _current_agent(module, array):
    """Return the readable settings of the SNMP agent.

    The SDK model raises AttributeError for fields the array did not send,
    and cleared settings come back as empty strings, so every field is read
    with a default and normalised to None when unset.
    """
    res = array.get_snmp_agents()
    check_response(res, module, "Failed to get SNMP agent configuration")
    agent = list(res.items)[0]
    v2c = getattr(agent, "v2c", None)
    v3 = getattr(agent, "v3", None)
    return {
        "version": getattr(agent, "version", None),
        # The community is masked, so only whether one is set is readable
        "community_set": bool(getattr(v2c, "community", None)),
        "user": getattr(v3, "user", None) or None,
        "auth_protocol": getattr(v3, "auth_protocol", None) or None,
        "privacy_protocol": getattr(v3, "privacy_protocol", None) or None,
    }


def update_agent(module, array):
    """Update SNMP Agent"""
    changed = False
    current = _current_agent(module, array)
    version_change = current["version"] != module.params["version"]
    if module.params["version"] == "v2c":
        if module.params["state"] == "present" and module.params["community"]:
            community = module.params["community"]
        else:
            community = ""
        # The community value is masked, so a change is only detectable as
        # a switch between set and cleared.
        if version_change or bool(community) != current["community_set"]:
            changed = True
        if changed and not module.check_mode:
            res = array.patch_snmp_agents(
                snmp_agent=flasharray.SnmpAgentPatch(
                    name="localhost",
                    version="v2c",
                    v2c=flasharray.SnmpV2c(community=community),
                )
            )
            check_response(res, module, "Failed to update SNMP agent")
    else:
        if module.params["state"] == "absent":
            # Clearing the protocols; the passphrases go with them
            if (
                version_change
                or current["auth_protocol"]
                or current["privacy_protocol"]
                or current["user"] != module.params["user"]
            ):
                changed = True
            v3 = flasharray.SnmpV3Patch(
                auth_protocol="",
                privacy_protocol="",
                user=module.params["user"],
            )
        else:
            # Only the supplied settings are sent, so only those are compared.
            # Passphrases are masked by the array and cannot be compared.
            if version_change or current["user"] != module.params["user"]:
                changed = True
            v3_settings = {"user": module.params["user"]}
            if module.params["auth_protocol"]:
                if current["auth_protocol"] != module.params["auth_protocol"]:
                    changed = True
                v3_settings["auth_protocol"] = module.params["auth_protocol"]
                v3_settings["auth_passphrase"] = module.params["auth_passphrase"]
            if module.params["privacy_protocol"]:
                if current["privacy_protocol"] != module.params["privacy_protocol"]:
                    changed = True
                v3_settings["privacy_protocol"] = module.params["privacy_protocol"]
                v3_settings["privacy_passphrase"] = module.params["privacy_passphrase"]
            v3 = flasharray.SnmpV3Patch(**v3_settings)

        if changed and not module.check_mode:
            res = array.patch_snmp_agents(
                snmp_agent=flasharray.SnmpAgentPatch(
                    name="localhost",
                    version=module.params["version"],
                    v3=v3,
                )
            )
            check_response(res, module, "Failed to update SNMP agent")

    module.exit_json(changed=changed)


def main():
    argument_spec = purefa_argument_spec()
    argument_spec.update(
        dict(
            state=dict(type="str", default="present", choices=["absent", "present"]),
            user=dict(type="str"),
            auth_passphrase=dict(type="str", no_log=True),
            auth_protocol=dict(type="str", choices=["MD5", "SHA"]),
            privacy_passphrase=dict(type="str", no_log=True),
            privacy_protocol=dict(type="str", choices=["AES", "DES"]),
            version=dict(type="str", default="v2c", choices=["v2c", "v3"]),
            community=dict(type="str"),
        )
    )

    required_together = [
        ["auth_passphrase", "auth_protocol"],
        ["privacy_passphrase", "privacy_protocol"],
    ]

    module = AnsibleModule(
        argument_spec,
        required_together=required_together,
        supports_check_mode=True,
    )

    array = get_array(module)
    api_version = array.get_rest_version()

    if LooseVersion(MIN_REQUIRED_API_VERSION) > LooseVersion(api_version):
        module.fail_json(
            msg="FlashArray REST version not supported. "
            "Minimum version required: {0}".format(MIN_REQUIRED_API_VERSION)
        )
    array = get_array(module)

    if module.params["version"] == "v3":
        if not module.params["user"]:
            module.fail_json(msg="version is v3 but the following is missing: user")
        if module.params["auth_passphrase"] and not (
            8 <= len(module.params["auth_passphrase"]) <= 32
        ):
            module.fail_json(msg="auth_password must be between 8 and 32 characters")
        if module.params["privacy_passphrase"] and not (
            8 <= len(module.params["privacy_passphrase"]) <= 63
        ):
            module.fail_json(msg="privacy_password must be between 8 and 63 characters")
    update_agent(module, array)
    module.exit_json(changed=False)


if __name__ == "__main__":
    main()
