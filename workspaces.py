#!/usr/bin/env python3
import json
import hcl
import os
import argparse
import requests
import yaml
from git import Repo


def parse_args():
    parser = argparse.ArgumentParser(description='Create workspaces')
    parser.add_argument('--org', required=True, help='Terraform Enterprise/Cloud organization')
    parser.add_argument('--tfe', required=True, default="app.terraform.io", help='Terraform Enterprise/Cloud address')
    parser.add_argument('--search-suffix', default='.tf', help='File ending when traversing directory structures ' 
                                                               'When the file with this file ending is found we mark' 
                                                               'this directory path for workspace creation')
    # Add subcommands
    subparsers = parser.add_subparsers(dest='command')
    parser_create = subparsers.add_parser('create', help='Create workspaces')
    parser_update = subparsers.add_parser('update', help='Update workspaces')
    parser_delete = subparsers.add_parser('delete', help='Delete workspaces')
    parser_pvar = subparsers.add_parser('push_var', help='Push variables to workspaces')
    subparsers.add_parser('list', help='List workspaces')
    # Define create subcommand
    parser_create.add_argument('directories', nargs='*',
                               help='Directories for which workspaces will be created. Workspace name will be based on '
                                    'the directory structure')
    parser_create.add_argument('--workspaces-file', type=argparse.FileType('r'), help='Yaml file with workspaces\' '''
                                                                                      'definitions')
    parser_create.add_argument('--ssh-key', help='ssh-key to use in the workspaces')
    parser_create.add_argument('--oauth-token-id', help='Terraform vcs oauth token id. Set this variable if you are ' 
                                                        'setting vcs_repo for your workspaces')
    # Define update subcommand
    parser_update.add_argument('workspaces', nargs='*',
                               help='Directories or list of the namespace. If -d passed than specify directories; if '
                                    'not then list the namespaces that you want updated. In case you specify -d then '
                                    'workspace names will be based on the directory structure')
    parser_update.add_argument('--workspaces-file', type=argparse.FileType('r'),
                               help='Yaml file with workspaces\' definitions')
    parser_update.add_argument('-d', action='store_const', const=True, dest='dirs', help='Update workspaces '
                                                                                         'based on directories')
    parser_update.add_argument('--ssh-key', help='ssh-key to use in the workspaces')
    parser_update.add_argument('--oauth-token-id', help='Terraform vcs oauth token id. Set this variable if you are '
                                                        'setting vcs_repo for your workspaces')
    parser_update.add_argument('--exec-mode', choices=['local', 'remote', 'agent'], help='Set execution mode')
    # Define delete subcommand
    parser_delete.add_argument('workspaces', nargs='*',
                               help='Directories or list of the namespace. If -d passed than specify directories; if '
                                    'not then list the namespaces that you want deleted. In case you specify -d then '
                                    'workspace names will be based on the directory structure')
    parser_delete.add_argument('--workspaces-file', type=argparse.FileType('r'),
                               help='Yaml file with workspaces\' definitions')
    parser_delete.add_argument('-d', action='store_const', const=True, dest='dirs', help='Delete workspaces '
                                                                                         'based on directories')
    # Define push_vars subcommand
    parser_pvar.add_argument('workspaces', nargs='*',
                             help='Directories or list of the namespace. If -d passed than specify directories; if '
                                  'not then list the namespaces for which you want the variable to be pushed. In case'
                                  'you specify -d then workspace names will be based on the directory structure')
    parser_pvar.add_argument('--env', '-e', action='store_const', const=True, dest='env_var',
                             help='Sets an environmental variable')
    parser_pvar.add_argument('-d', action='store_const', const=True, dest='dirs', help='Delete workspaces '
                                                                                       'based on directories')
    parser_pvar.add_argument('--name', '-n', required=True, dest='var_name', help='Variable Name')
    parser_pvar.add_argument('--value', '-v', required=True, dest='var_value', help='Variable Value')
    parser_pvar.add_argument('--file', '-f', action='store_const', const=True, dest='var_file', default=False,
                             help='Set this flag if --value is a file')
    parser_pvar.add_argument('--sensitive', '-s', action='store_const', const=True, dest='sensitive', default=False,
                             help='Set this flag is variable is sensitive')
    arguments = parser.parse_args()
    return arguments


def found_tf(directory_path, terminating_file_suffix):
    for f in os.listdir(directory_path):
        if f.endswith(terminating_file_suffix):
            return True
    return False


def remove_tf_tf_cache_dirs(directories):
    a = []
    for d in directories:
        if '.terraform/' in d or '.terragrunt-cache' in d:
            continue
        else:
            a.append(d)
    return a


def workspaces_from_directory_structure(directories, search_suffix):
    workspaces = []
    for searched_directory in directories:
        for root, directories, files in os.walk(searched_directory):
            if found_tf(root, search_suffix):
                workspaces.append(root)
            for directory in directories:
                director_path = os.path.join(root, directory)
                if found_tf(director_path, search_suffix):
                    workspaces.append(director_path)
    return list(dict.fromkeys(remove_tf_tf_cache_dirs(workspaces)))


def get_token(tfe):
    if os.environ.get('TF_TOKEN'):
        return os.environ.get('TF_TOKEN')
    if os.path.isfile(os.path.expanduser('~/.terraformrc')):
        with open(os.path.expanduser('~/.terraformrc'), 'r') as fp:
            obj = hcl.load(fp)
            try:
                return obj['credentials'][tfe]["token"]
            except KeyError:
                pass
    else:
        error_message = 'You need to define terraform cloud API token either through TF_TOKEN variable or '\
                        '~/.terraformrc. See: '\
                        'https://www.terraform.io/docs/commands/cli-config.html#available-settings'
        raise Exception(error_message)


class TerraformAPI:
    def __init__(self, tfe, org, token):
        self.tfe = tfe
        self.org = org
        self.token = token
        self.url = 'https://{}/api/v2/organizations/{}/workspaces'.format(tfe, org)
        self.var_url = 'https://{}/api/v2/vars'.format(tfe)
        self.ssh_url = 'https://{}/api/v2/organizations/{}/ssh-keys'.format(tfe, org)
        self.vcs_repo = {}
        self.session = requests.session()
        self.headers = {
            'Authorization': 'Bearer {}'.format(self.token),
            'Content-Type': 'application/vnd.api+json'
        }
        print(Repo('.',search_parent_directories=True).remotes)
        self.identifier = next(Repo('.',search_parent_directories=True).remotes[0].urls).split(':')[1].replace('.git', '')
        print(self.identifier)

    def create_workspace(self, directory_path, oauth_token_id=None, ssh_key=None):
        workspace_name = directory_path.replace('/', '-')
        body = {
            "data": {
                "attributes": {
                    "name": workspace_name,
                    "working-directory": directory_path,
                },
                "type": "workspaces"
            }
        }
        if oauth_token_id:
            vcs_repo = {
                'identifier': self.identifier,
                'oauth-token-id': oauth_token_id
            }
            body['data']['attributes']['vcs-repo'] = vcs_repo
        res = self.session.get(self.url + '/' + workspace_name, headers=self.headers)
        if res.status_code != 200:
            print('Creating workspace = {}'.format(workspace_name))
            res = self.session.post(self.url, headers=self.headers, data=json.dumps(body))
        else:
            print('Workspace = {} already exists'.format(workspace_name))
        if res.status_code not in [200, 201]:
            raise Exception('Status code: {}. Exception: {}'.format(res.status_code, res.content))
        if ssh_key:
            self.update_workspace_ssh_key(workspace_name, ssh_key, directory=False)

    def _get_ssh_key_id(self, ssh_key):
        res = self.session.get(self.ssh_url, headers=self.headers)
        for key in res.json()['data']:
            if key['attributes']['name'] == ssh_key:
                return key['id']
        raise Exception('SSH key not found in the organization')

    def _update_ssh(self, ssh_key, workspace_name):
        res = self.session.get(self.url + '/' + workspace_name, headers=self.headers)
        ssh_key_id = self._get_ssh_key_id(ssh_key)
        workspace_id = res.json()['data']['id']
        body = {
            "data": {
                "attributes": {
                    "id": ssh_key_id
                },
                "type": "workspaces"
            }
        }
        ssh_update_url = 'https://{}/api/v2/workspaces/{}/relationships/ssh-key'.format(self.tfe, workspace_id)
        session = requests.session()
        session.patch(ssh_update_url, headers=self.headers, data=json.dumps(body))

    def update_workspace_ssh_key(self, workspace, ssh_key, directory=False):
        if directory:
            workspace = workspace.replace('/', '-')
        print('Updating workspace = {} with ssh_key = {}'.format(workspace, ssh_key))
        self._update_ssh(ssh_key, workspace)

    def update_workspace(self,
                         workspace,
                         oauth_token_id=None,
                         ssh_key=None,
                         exec_mode=None,
                         directory=False):
        body = {
            'data': {
                'attributes': {},
                'type': 'workspaces'
            }
        }
        if directory:
            workspace = workspace.replace('/', '-')
        if oauth_token_id:
            body['data']['attributes']['vcs-repo'] = {}
            body['data']['attributes']['vcs-repo']['oauth-token-id'] = oauth_token_id
            body['data']['attributes']['vcs-repo']['identifier'] = self.identifier
        if exec_mode:
            body['data']['attributes']['execution-mode'] = exec_mode
            #body['data']['attributes']['operations'] = exec_mode
        if ssh_key:
            self.update_workspace_ssh_key(workspace, ssh_key, directory=directory)
        print('Updating workspace = {} with {}'.format(workspace, json.dumps(body, indent=2)))
        res = self.session.patch(self.url + '/' + workspace, headers=self.headers, data=json.dumps(body))
        if res.status_code not in [200, 201]:
            raise Exception('Status code: {}. Exception: {}'.format(res.status_code, res.content))

    def list_workspaces(self):
        res = self.session.get(self.url, headers=self.headers)
        if res.status_code not in [200, 201]:
            raise Exception('Status code: {}. Exception: {}'.format(res.status_code, res.content))
        for workspace in res.json()['data']:
            print(workspace['attributes']['name'])

    def delete_workspace(self, workspace, directory=False):
        if directory:
            workspace = workspace.replace('/', '-')
        print('Deleting workspace = {}'.format(workspace))
        res = self.session.delete(self.url + '/' + workspace, headers=self.headers)
        if res.status_code not in [200, 201]:
            raise Exception('Status code: {}. Exception: {}'.format(res.status_code, res.content))

    def create_workspaces_from_file(self, workspaces_file):
        for workspace in self.load_workspaces(workspaces_file):
            body = {
                "data": {
                    "attributes": workspace['attributes'],
                    "type": "workspaces"
                }
            }
            print('Creating workspace = {}'.format(workspace['attributes']['name']))
            res = self.session.post(self.url, headers=self.headers, data=json.dumps(body))
            if res.status_code not in [200, 201]:
                raise Exception('Status code: {}. Exception: {}'.format(res.status_code, res.content))

    def delete_workspaces_from_file(self, workspaces_file):
        for ws in self.load_workspaces(workspaces_file):
            print('Deleting workspace = {}'.format(ws['attributes']['name']))
            self.delete_workspace(ws['attributes']['name'])

    def push_varable(self, name, value, workspace, from_file=False, env_var=False, sensitive=False, directory=False):
        if directory:
            workspace = workspace.replace('/', '-')
        res_workspace = self.session.get(self.url + '/' + workspace, headers=self.headers)
        if res_workspace.status_code not in [200, 201]:
            raise Exception('Status code: {}. Exception: {}'.format(res_workspace.status_code, res_workspace.content))
        workspace_id = res_workspace.json()['data']['id']
        if env_var:
            category = 'env'
        else:
            category = 'terraform'
        if from_file:
            with open(value, 'r') as f:
                v = f.read()
                v = v.replace('\n', '')
        else:
            v = value
        body = {
            "data": {
                "type": "vars",
                "attributes": {
                    "key": name,
                    "value": v,
                    "category": category,
                    "hcl": False,
                    "sensitive": sensitive
                },
                "relationships": {
                    "workspace": {
                        "data": {
                            "id": workspace_id,
                            "type": "workspaces"
                        }
                    }
                }
            }
        }
        print('Pushing key = {} into workspace = {}'.format(name, workspace))
        res_value = self.session.post(self.var_url, headers=self.headers, data=json.dumps(body))
        if res_value.status_code not in [200, 201]:
            raise Exception('Status code: {}. Exception: {}'.format(res_value.status_code, res_value.content))

    @staticmethod
    def load_workspaces(workspaces):
        with open(workspaces, 'r') as workspaces:
            return yaml.load(workspaces)


def workspaces_list(workspaces, search_suffix, directory):
    if directory:
        return workspaces_from_directory_structure(workspaces, search_suffix)
    else:
        return args.workspaces


if __name__ == '__main__':
    args = parse_args()
    tf_api = TerraformAPI(tfe=args.tfe, org=args.org, token=get_token(args.tfe))

    if args.command == 'create':
        directory_paths = workspaces_from_directory_structure(args.directories, args.search_suffix)
        for directory_path in directory_paths:
            tf_api.create_workspace(directory_path, oauth_token_id=args.oauth_token_id, ssh_key=args.ssh_key)
        if args.workspaces_file:
            tf_api.create_workspaces_from_file(args.workspaces_file)

    if args.command == 'list':
        tf_api.list_workspaces()

    if args.command == 'delete':
        for ws in workspaces_list(args.workspaces, args.search_suffix, args.dirs):
            tf_api.delete_workspace(ws, args.dirs)
        if args.workspaces_file:
            tf_api.delete_workspaces_from_file(args.workspaces_file)

    if args.command == 'update':
        for ws in workspaces_list(args.workspaces, args.search_suffix, args.dirs):
            tf_api.update_workspace(ws,
                                    oauth_token_id=args.oauth_token_id,
                                    ssh_key=args.ssh_key,
                                    exec_mode=args.exec_mode,
                                    directory=args.dirs)

    if args.command == 'push_var':
        for ws in workspaces_list(args.workspaces, args.search_suffix, args.dirs):
            tf_api.push_varable(args.var_name,
                                args.var_value,
                                ws,
                                from_file=args.var_file,
                                env_var=args.env_var,
                                sensitive=args.sensitive,
                                directory=args.dirs)