#!/usr/bin/env python3
"""
Builds the 'repo' branch artifacts for this Unmanic plugin repository.

Run from the repo root:
    python3 scripts/generate_repository.py

What it does:
  1. Reads each plugin dir under source/
  2. Copies info.json, description.md, changelog.md to repo/<plugin_id>/
  3. Creates repo/<plugin_id>/<plugin_id>-<version>.zip (skips if already present)
  4. Writes repo/repo.json and repo/repo.json.md5

After running, commit the repo/ directory to the 'repo' branch and push.
"""
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import zipfile

scripts_directory = os.path.dirname(os.path.realpath(__file__))
project_root = os.path.realpath(os.path.join(scripts_directory, '..'))

repo_source_path = os.path.join(project_root, 'source')
repo_dest_path = os.path.join(project_root, 'repo')
os.makedirs(repo_dest_path, exist_ok=True)


def install_requirements(plugin_source_path):
    requirements_file = os.path.join(plugin_source_path, 'requirements.txt')
    install_target = os.path.join(plugin_source_path, 'site-packages')
    if not os.path.exists(requirements_file):
        print('      - no requirements.txt')
        return
    import pip
    pip.main(['install', '--upgrade', '-r', requirements_file, '--target={}'.format(install_target)])


print("\n>> Processing Plugins\n")

for item in sorted(os.listdir(repo_source_path)):
    item_path = os.path.join(repo_source_path, item)
    if not os.path.isdir(item_path) or item.startswith('.'):
        continue

    info_file = os.path.join(item_path, 'info.json')
    with open(info_file) as f:
        plugin_info = json.load(f)

    for field in ['id', 'name', 'author', 'version', 'tags', 'description']:
        if field not in plugin_info:
            raise Exception(f"Plugin '{item}' is missing '{field}' in info.json")

    dest_dir = os.path.join(repo_dest_path, item)
    plugin_zip_name = "{}-{}.zip".format(item, plugin_info['version'])
    plugin_zip = os.path.join(dest_dir, plugin_zip_name)

    print(f"  -> {plugin_info['name']} v{plugin_info['version']}")

    if os.path.exists(plugin_zip):
        print(f"     WARNING: {plugin_zip_name} already exists — bump version to overwrite")
        print()
        continue

    os.makedirs(dest_dir, exist_ok=True)

    shutil.copy(info_file, dest_dir)
    for pattern in ['*description.*', '*changelog.*', '*icon.*', '*fanart.*']:
        for file in glob.glob(os.path.join(item_path, pattern)):
            shutil.copy(file, dest_dir)

    print(f"     Zipping -> {plugin_zip_name}")
    with zipfile.ZipFile(plugin_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(item_path):
            dirs[:] = [d for d in dirs if d not in ('__pycache__', '.git', '.github', 'site-packages')]
            rel = os.path.relpath(root, item_path)
            for file in files:
                if file.startswith('.git') or file.endswith('.pyc'):
                    continue
                abs_path = os.path.join(root, file)
                arc_name = os.path.relpath(abs_path, item_path)
                zf.write(abs_path, arc_name)

    print()


print(">> Processing Repo Metadata\n")

repo_data = {"repo": {}, "plugins": []}
repo_json_file = os.path.join(repo_dest_path, 'repo.json')
repo_json_md5_file = os.path.join(repo_dest_path, 'repo.json.md5')

for item in sorted(os.listdir(repo_dest_path)):
    item_path = os.path.join(repo_dest_path, item)
    if not os.path.isdir(item_path) or item.startswith('.'):
        continue
    info_file = os.path.join(item_path, 'info.json')
    with open(info_file) as f:
        repo_data['plugins'].append(json.load(f))

with open(os.path.join(project_root, 'config.json')) as f:
    repo_info = json.load(f)

remote_url = subprocess.check_output(['git', 'remote', 'get-url', '--push', 'origin'], cwd=project_root).decode().strip()
repo_path = re.sub(r'^(?:https?://github\.com/)|(?:git@github\.com:)|(?:\.git$)', '', remote_url).strip()
repo_info['repo_data_directory'] = f"https://raw.githubusercontent.com/{repo_path}/repo/"
repo_info['repo_data_url'] = repo_info['repo_data_directory'] + "repo.json"
repo_data['repo'] = repo_info

with open(repo_json_file, 'w') as f:
    json.dump(repo_data, f, indent=4)

checksum = hashlib.md5(open(repo_json_file, 'rb').read()).hexdigest()
with open(repo_json_md5_file, 'w') as f:
    f.write(checksum)

print(f"  repo.json written")
print(f"  MD5: {checksum}")
print()
print("Done. Now commit repo/ to the 'repo' branch and push.")
