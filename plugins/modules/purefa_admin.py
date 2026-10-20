#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2021, Simon Dodsley (simon@everpuredata.com)
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
module: purefa_admin
version_added: '1.12.0'
short_description: Configure Everpure FlashArray Global Admin settings
description:
- Set global admin settings for the FlashArray
author:
- Everpure Ansible Team (@sdodsley) <pure-ansible-team@everpuredata.com>
options:
  sso:
    description:
    - Enable or disable the array Single Sign-On from Pure1 Manage
    - When omitted the current setting is left unchanged.
    type: bool
  max_login:
    description:
    - Maximum number of failed logins before account is locked
    type: int
  min_password:
    description:
    - Minimum user password length
    default: 1
    type: int
  lockout:
    description:
    - Account lockout duration, in seconds, after max_login exceeded
    - Range between 1 second and 90 days (7776000 seconds)
    - Set to 0 to clear an existing lockout duration.
    - When omitted the current setting is left unchanged.
    type: int
extends_documentation_fragment:
- everpure.flasharray.everpure.fa
"""

EXAMPLES = r"""
- name: Set global login parameters
  everpure.flasharray.purefa_admin:
    sso: false
    max_login: 5
    min_password: 10
    lockout: 300
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592
"""

RETURN = r"""
"""

HAS_PURESTORAGE = True
try:
    from pypureclient.flasharray import AdminSettings
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

MIN_API_VERSION = "2.2"


def main():
    argument_spec = purefa_argument_spec()
    argument_spec.update(
        dict(
            sso=dict(type="bool"),
            max_login=dict(type="int"),
            min_password=dict(type="int", default=1, no_log=False),
            lockout=dict(type="int"),
        )
    )

    module = AnsibleModule(argument_spec, supports_check_mode=True)

    if not HAS_PURESTORAGE:
        module.fail_json(msg="py-pure-client sdk is required for this module")
    if (
        module.params["lockout"] is not None
        and module.params["lockout"] != 0
        and not 1 <= module.params["lockout"] <= 7776000
    ):
        module.fail_json(msg="Lockout must be between 1 and 7776000 seconds")
    array = get_array(module)
    api_version = array.get_rest_version()
    changed = False
    if LooseVersion(MIN_API_VERSION) <= LooseVersion(api_version):
        current_settings = list(array.get_admins_settings().items)[0]
        # sso is tri-state: None leaves the array setting alone, so that
        # False can be used to switch Single Sign-On off
        if (
            module.params["sso"] is not None
            and module.params["sso"] != current_settings.single_sign_on_enabled
        ):
            changed = True
            sso = module.params["sso"]
        else:
            sso = current_settings.single_sign_on_enabled
        if (
            module.params["min_password"]
            and module.params["min_password"] != current_settings.min_password_length
        ):
            changed = True
            min_password = module.params["min_password"]
        else:
            min_password = current_settings.min_password_length
        lockout = getattr(current_settings, "lockout_duration", None)
        if module.params["lockout"] is not None:
            # lockout: 0 clears the duration; the array reports a cleared
            # duration by omitting the field, so None and 0 are the same state
            if (lockout or 0) != module.params["lockout"] * 1000:
                changed = True
                lockout = module.params["lockout"] * 1000
        max_login = getattr(current_settings, "max_login_attempts", None)
        if (
            max_login
            and module.params["max_login"]
            and max_login != module.params["max_login"]
        ):
            changed = True
            max_login = module.params["max_login"]
        elif not max_login and module.params["max_login"]:
            changed = True
            max_login = module.params["max_login"]
        if changed and not module.check_mode:
            settings = {
                "single_sign_on_enabled": sso,
                "min_password_length": min_password,
            }
            # A lockout of 0 must still be sent, so that it clears the
            # duration rather than being dropped as a falsy value
            if lockout is not None:
                settings["lockout_duration"] = lockout
            if max_login:
                settings["max_login_attempts"] = max_login
            admin = AdminSettings(**settings)
            res = array.patch_admins_settings(admin_settings=admin)
            check_response(res, module, "Failed to change Global Admin settings")
    else:
        module.fail_json(msg="Purity version does not support Global Admin settings")
    module.exit_json(changed=changed)


if __name__ == "__main__":
    main()
