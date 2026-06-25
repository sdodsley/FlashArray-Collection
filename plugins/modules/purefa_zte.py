#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2026, Simon Dodsley (simon@purestorage.com)
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
module: purefa_zte
version_added: '1.44.0'
short_description: Perform Zero Touch Erasure (ZTE) on a FlashArray
description:
- Securely reset a FlashArray to a factory-fresh state using Zero Touch
  Erasure (ZTE).
- ZTE wipes all drives, generates a NIST SP800-88R1 sanitization certificate
  and optionally reinstalls the array image.
- B(This is an extremely destructive and irreversible operation.) All data on
  the array is permanently and unrecoverably erased.
- Requires Purity//FA 6.6.8, or higher.
- All customer data (pods, protection groups, volumes/snapshots, array
  connections, file systems, directory service, file local users and groups,
  and Active Directory service) must be deleted and eradicated before starting
  ZTE, otherwise the operation will fail immediately.
- ZTE is a multi-phase process. Use I(state=start) to begin the drive wipe,
  I(state=status) to monitor progress and retrieve the sanitization
  certificate, and I(state=finalize) to complete the reset. Use
  I(state=cancel) to cancel a failed reset.
- During the drive wipe the array REST API service is unavailable for a period
  of time (typically around 30 minutes). This is expected behaviour.
author:
- Everpure Ansible Team (@sdodsley) <pure-ansible-team@purestorage.com>
options:
  state:
    description:
    - The ZTE phase to perform.
    - I(start) begins Phase 1, securely wiping the drives and generating the
      sanitization certificate.
    - I(status) returns the current ZTE process status and, when available,
      the sanitization certificate. This is non-destructive.
    - I(finalize) performs Phase 3, finalizing the reset. This permanently
      deletes the sanitization certificate, so ensure it has been saved first.
    - I(cancel) cancels a ZTE process that is in a failed state.
    type: str
    choices: [ start, status, finalize, cancel ]
    default: status
  eradicate:
    description:
    - A safety acknowledgement that must be set to C(true) to perform any
      destructive ZTE phase (I(start) or I(finalize)).
    - Setting this to C(true) confirms that you understand all data on the
      array will be permanently and unrecoverably erased.
    type: bool
    default: false
  preserve_config:
    description:
    - Whether to preserve array configuration data during the drive wipe.
    - Only used when I(state=start).
    type: bool
    default: true
  skip_phonehome_check:
    description:
    - Skip the phonehome connectivity check when starting ZTE.
    - Must be set to C(true) for darksite arrays that do not have connectivity
      to Pure Storage cloud servers, otherwise the reset will fail the
      phonehome connectivity check.
    - Only used when I(state=start).
    type: bool
    default: false
  reinstall_image:
    description:
    - Whether to reinstall the array image when finalizing ZTE.
    - When C(false) (Option 1), existing system-generated data, management
      interface configuration and configuration data are retained.
    - When C(true) (Option 2), the array image is reinstalled and existing
      system-generated data, management interface configuration and
      configuration data are removed.
    - Only used when I(state=finalize).
    type: bool
    default: false
  image_source:
    description:
    - The source of the image used when I(reinstall_image=true).
    - For phoning-home arrays set this to C(auto).
    - For darksite arrays set this to the URL, or file path, of an image
      bundle that the array can access. The image bundle must be the same
      version as the Purity//FA version running on the array.
    - Only used when I(state=finalize) and I(reinstall_image=true).
    type: str
    default: auto
  image_version:
    description:
    - The Purity//FA version of the darksite image bundle referenced by
      I(image_source).
    - Only used when I(state=finalize) and I(reinstall_image=true) for a
      darksite array.
    type: str
extends_documentation_fragment:
- purestorage.flasharray.purestorage.fa
"""

EXAMPLES = r"""
- name: Check current ZTE status and retrieve sanitization certificate
  purestorage.flasharray.purefa_zte:
    state: status
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592
  register: zte

- name: Save the sanitization certificate before finalizing
  ansible.builtin.copy:
    content: "{{ zte.zte.sanitization_certificate }}"
    dest: ./sanitization_certificate.txt
  when: zte.zte.sanitization_certificate | length > 0

- name: Start ZTE (Phase 1 - wipe drives)
  purestorage.flasharray.purefa_zte:
    state: start
    eradicate: true
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592

- name: Start ZTE on a darksite array
  purestorage.flasharray.purefa_zte:
    state: start
    eradicate: true
    skip_phonehome_check: true
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592

- name: Finalize ZTE without reinstalling the image (Option 1)
  purestorage.flasharray.purefa_zte:
    state: finalize
    eradicate: true
    reinstall_image: false
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592

- name: Finalize ZTE and reinstall image on a phoning-home array (Option 2)
  purestorage.flasharray.purefa_zte:
    state: finalize
    eradicate: true
    reinstall_image: true
    image_source: auto
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592

- name: Finalize ZTE and reinstall image on a darksite array (Option 2)
  purestorage.flasharray.purefa_zte:
    state: finalize
    eradicate: true
    reinstall_image: true
    image_source: "https://server.example.com/purity_iso.sh"
    image_version: "6.6.8"
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592

- name: Cancel a failed ZTE process
  purestorage.flasharray.purefa_zte:
    state: cancel
    fa_url: 10.10.10.2
    api_token: e31060a7-21fc-e277-6240-25983c6c4592
"""

RETURN = r"""
zte:
  description: The current state of the ZTE process.
  returned: always
  type: dict
  contains:
    status:
      description:
      - The status of the ZTE process, for example C(resetting),
        C(waiting_for_finalize), C(downloading), C(reset_failed),
        C(download_failed), C(reimage_failed) or C(finalized).
      - An empty string indicates that no ZTE process is in progress.
      type: str
      returned: always
    details:
      description: Failure information when the ZTE process has failed.
      type: str
      returned: always
    image_download_progress:
      description: The image download progress when reinstalling the image.
      type: str
      returned: always
    sanitization_certificate:
      description:
      - The NIST SP800-88R1 sanitization certificate generated during the
        drive wipe.
      - This is only available between Phase 1 completing and ZTE being
        finalized. It cannot be retrieved once ZTE is finalized.
      type: str
      returned: always
"""

HAS_PURESTORAGE = True
try:
    from pypureclient import flasharray
except ImportError:
    HAS_PURESTORAGE = False

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.purestorage.flasharray.plugins.module_utils.purefa import (
    get_array,
    purefa_argument_spec,
)
from ansible_collections.purestorage.flasharray.plugins.module_utils.version import (
    LooseVersion,
)
from ansible_collections.purestorage.flasharray.plugins.module_utils.api_helpers import (
    check_response,
)

MIN_REQUIRED_API_VERSION = "2.34"

# Statuses that indicate a ZTE process is actively running or awaiting action
ACTIVE_STATES = frozenset(
    [
        "resetting",
        "waiting_for_finalize",
        "downloading",
        "downloaded",
    ]
)


def get_erasure(array):
    """Return the current erasure (factory reset) object, or None.

    A successful Option 1 finalize leaves no erasure in progress, in which case
    ``get_arrays_erasures`` returns an empty item list.
    """
    res = array.get_arrays_erasures()
    if res.status_code != 200:
        return None
    items = list(res.items)
    return items[0] if items else None


def erasure_facts(current):
    """Build the return dict from an erasure object."""
    if current is None:
        return {
            "status": "",
            "details": "",
            "image_download_progress": "",
            "sanitization_certificate": "",
        }
    return {
        "status": getattr(current, "status", "") or "",
        "details": getattr(current, "details", "") or "",
        "image_download_progress": getattr(current, "image_download_progress", "")
        or "",
        "sanitization_certificate": getattr(current, "sanitization_certificate", "")
        or "",
    }


def zte_status(module, array, current):
    """Report the current ZTE status. Non-destructive."""
    module.exit_json(changed=False, zte=erasure_facts(current))


def start_zte(module, array, current):
    """Phase 1 - securely wipe the drives and generate the sanitization cert."""
    if not module.params["eradicate"]:
        module.fail_json(
            msg="To start ZTE the `eradicate` parameter must be set to true. "
            "This permanently and unrecoverably erases all data on the array."
        )
    if current is not None and getattr(current, "status", "") in ACTIVE_STATES:
        # A reset is already in progress - nothing to do
        module.exit_json(changed=False, zte=erasure_facts(current))
    changed = True
    if not module.check_mode:
        preserve = ["all"] if module.params["preserve_config"] else []
        res = array.post_arrays_erasures(
            eradicate_all_data=True,
            preserve_configuration_data=preserve,
            skip_phonehome_check=module.params["skip_phonehome_check"],
        )
        check_response(res, module, "Failed to start ZTE")
        current = get_erasure(array)
    module.exit_json(changed=changed, zte=erasure_facts(current))


def finalize_zte(module, array, current):
    """Phase 3 - finalize the reset."""
    if not module.params["eradicate"]:
        module.fail_json(
            msg="To finalize ZTE the `eradicate` parameter must be set to true. "
            "This permanently deletes the sanitization certificate."
        )
    if current is None:
        module.fail_json(msg="There is no ZTE process to finalize")
    changed = True
    if not module.check_mode:
        kwargs = dict(
            finalize=True,
            eradicate_all_data=True,
            delete_sanitization_certificate=True,
            reinstall_image=module.params["reinstall_image"],
        )
        if module.params["reinstall_image"]:
            kwargs["erasure_patch"] = flasharray.ArrayErasurePatch(
                image_source=module.params["image_source"],
                image_version=module.params["image_version"],
            )
        res = array.patch_arrays_erasures(**kwargs)
        check_response(res, module, "Failed to finalize ZTE")
        current = get_erasure(array)
    module.exit_json(changed=changed, zte=erasure_facts(current))


def cancel_zte(module, array, current):
    """Cancel a ZTE process that is in a failed state."""
    if current is None:
        module.exit_json(changed=False, zte=erasure_facts(current))
    changed = True
    if not module.check_mode:
        res = array.delete_arrays_erasures()
        check_response(res, module, "Failed to cancel ZTE")
        current = get_erasure(array)
    module.exit_json(changed=changed, zte=erasure_facts(current))


def main():
    argument_spec = purefa_argument_spec()
    argument_spec.update(
        dict(
            state=dict(
                type="str",
                default="status",
                choices=["start", "status", "finalize", "cancel"],
            ),
            eradicate=dict(type="bool", default=False),
            preserve_config=dict(type="bool", default=True),
            skip_phonehome_check=dict(type="bool", default=False),
            reinstall_image=dict(type="bool", default=False),
            image_source=dict(type="str", default="auto"),
            image_version=dict(type="str"),
        )
    )

    module = AnsibleModule(argument_spec, supports_check_mode=True)

    if not HAS_PURESTORAGE:
        module.fail_json(msg="py-pure-client sdk is required for this module")

    array = get_array(module)
    api_version = array.get_rest_version()

    if LooseVersion(MIN_REQUIRED_API_VERSION) > LooseVersion(api_version):
        module.fail_json(
            msg="FlashArray REST version not supported. "
            "Minimum version required: {0}".format(MIN_REQUIRED_API_VERSION)
        )

    current = get_erasure(array)

    state = module.params["state"]
    if state == "start":
        start_zte(module, array, current)
    elif state == "finalize":
        finalize_zte(module, array, current)
    elif state == "cancel":
        cancel_zte(module, array, current)
    else:
        zte_status(module, array, current)


if __name__ == "__main__":
    main()
