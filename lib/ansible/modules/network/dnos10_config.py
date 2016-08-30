#!/usr/bin/python
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
#

DOCUMENTATION = """
---
module: dnos10_config
version_added: "2.2"
author: "Senthil Kumar Ganesan (@skg_net)
short_description: Manage Dell OS10 configuration sections
description:
  - Dell OS10 configurations use a simple block indent file sytanx
    for segementing configuration into sections.  This module provides
    an implementation for working with Dell OS10 configuration sections in
    a deterministic way.
extends_documentation_fragment: dnos10
options:
  lines:
    description:
      - The ordered set of commands that should be configured in the
        section.  The commands must be the exact same commands as found
        in the device running-config.  Be sure to note the configuration
        command syntax as some commands are automatically modified by the
        device config parser.
    required: false
    default: null
    aliases: ['commands']
  parents:
    description:
      - The ordered set of parents that uniquely identify the section
        the commands should be checked against.  If the parents argument
        is omitted, the commands are checked against the set of top
        level or global commands.
    required: false
    default: null
  src:
    description:
      - Specifies the source path to the file that contains the configuration
        or configuration template to load.  The path to the source file can
        either be the full path on the Ansible control host or a relative
        path from the playbook or role root dir.  This argument is mutually
        exclusive with O(lines).
    required: false
    default: null
  before:
    description:
      - The ordered set of commands to push on to the command stack if
        a change needs to be made.  This allows the playbook designer
        the opportunity to perform configuration commands prior to pushing
        any changes without affecting how the set of commands are matched
        against the system
    required: false
    default: null
  after:
    description:
      - The ordered set of commands to append to the end of the command
        stack if a changed needs to be made.  Just like with I(before) this
        allows the playbook designer to append a set of commands to be
        executed after the command set.
    required: false
    default: null
  match:
    description:
      - Instructs the module on the way to perform the matching of
        the set of commands against the current device config.  If
        match is set to I(line), commands are matched line by line.  If
        match is set to I(strict), command lines are matched with respect
        to position.  If match is set to I(exact), command lines
        must be an equal match.  Finally, if match is set to I(none), the
        module will not attempt to compare the source configuration with
        the running configuration on the remote device.
    required: false
    default: line
    choices: ['line', 'strict', 'exact', 'none']
  replace:
    description:
      - Instructs the module on the way to perform the configuration
        on the device.  If the replace argument is set to I(line) then
        the modified lines are pushed to the device in configuration
        mode.  If the replace argument is set to I(block) then the entire
        command block is pushed to the device in configuration mode if any
        line is not correct
    required: false
    default: line
    choices: ['line', 'block']
  update_config:
    description:
      - This arugment will either cause or prevent the changed commands
        from being sent to the remote device.  The set to true, the
        remote Dell OS10 device will be configured with the updated commands
        and when set to false, the remote device will not be updated.
    required: false
    default: yes
    choices: ['yes', 'no']
  backup_config:
    description:
      - This argument will cause the module to create a full backup of
        the current C(running-config) from the remote device before any
        changes are made.  The backup file is written to the C(backup)
        folder in the playbook root directory.  If the directory does not
        exist, it is created.
    required: false
    default: no
    choices: ['yes', 'no']
"""

EXAMPLES = """
- dnos10_config:
    lines: ['hostname {{ inventory_hostname }}']
    force: yes

- dnos10_config:
    lines:
      - 10 permit ip host 1.1.1.1 any log
      - 20 permit ip host 2.2.2.2 any log
      - 30 permit ip host 3.3.3.3 any log
      - 40 permit ip host 4.4.4.4 any log
      - 50 permit ip host 5.5.5.5 any log
    parents: ['ip access-list extended test']
    before: ['no ip access-list extended test']
    match: exact

- dnos10_config:
    lines:
      - 10 permit ip host 1.1.1.1 any log
      - 20 permit ip host 2.2.2.2 any log
      - 30 permit ip host 3.3.3.3 any log
      - 40 permit ip host 4.4.4.4 any log
    parents: ['ip access-list extended test']
    before: ['no ip access-list extended test']
    replace: block

- dnos10_config:
    commands: "{{lookup('file', 'datcenter1.txt')}}"
    parents: ['ip access-list test']
    before: ['no ip access-list test']
    replace: block

"""

RETURN = """
updates:
  description: The set of commands that will be pushed to the remote device
  returned: always
  type: list
  sample: ['...', '...']

responses:
  description: The set of responses from issuing the commands on the device
  retured: when not check_mode
  type: list
  sample: ['...', '...']
"""
from ansible.module_utils.netcfg import NetworkConfig, dumps, ConfigLine
from ansible.module_utils.dnos10 import NetworkModule, dnos10_argument_spec
from ansible.module_utils.dnos10 import get_config, get_sublevel_config 

def get_candidate(module):
    candidate = NetworkConfig(indent=1)
    if module.params['src']:
        candidate.load(module.params['src'])
    elif module.params['lines']:
        parents = module.params['parents'] or list()
        candidate.add(module.params['lines'], parents=parents)
    return candidate


def main():

    argument_spec = dict(
        lines=dict(aliases=['commands'], type='list'),
        parents=dict(type='list'),

        src=dict(type='path'),

        before=dict(type='list'),
        after=dict(type='list'),

        match=dict(default='line',
                   choices=['line', 'strict', 'exact', 'none']),
        replace=dict(default='line', choices=['line', 'block']),

        update_config=dict(type='bool', default=True),
        backup_config=dict(type='bool', default=False)
    )
    argument_spec.update(dnos10_argument_spec)

    mutually_exclusive = [('lines', 'src')]

    module = NetworkModule(argument_spec=argument_spec,
                           connect_on_load=False,
                           mutually_exclusive=mutually_exclusive,
                           supports_check_mode=True)

    module.check_mode = not module.params['update_config']

    parents = module.params['parents'] or list()

    match = module.params['match']
    replace = module.params['replace']
    before = module.params['before']
    result = dict(changed=False, saved=False)

    candidate = get_candidate(module)

    if module.params['match'] != 'none':
        config = get_config(module)
        if parents:
            contents = get_sublevel_config(config, module)
            config = NetworkConfig(contents=contents, indent=1)
        configobjs = candidate.difference(config, match=match, replace=replace)

    else:
        configobjs = candidate.items

    if module.params['backup_config']:
        result['__backup__'] = module.cli('show running-config')[0]

    commands = list()
    if configobjs:
        commands = dumps(configobjs, 'commands')
        commands = commands.split('\n')

        if module.params['before']:
            commands[:0] = module.params['before']

        if module.params['after']:
            commands.extend(module.params['after'])

        if not module.check_mode:
            response = module.config.load_config(commands)
            result['responses'] = response

            if module.params['save_config']:
                module.config.save_config()
                result['saved'] = True

        result['changed'] = True

    result['updates'] = commands
    result['connected'] = module.connected

    module.exit_json(**result)

if __name__ == '__main__':
    main()