import json
import urllib.request

with urllib.request.urlopen('https://api.github.com/repos/ggml-org/llama.cpp/releases/latest', timeout=30) as response:
    release = json.load(response)
print('Release:', release['tag_name'], release['html_url'])
for asset in release['assets']:
    if 'win' in asset['name'] and ('cuda' in asset['name'] or 'vulkan' in asset['name']):
        print(asset['name'], asset['size'], asset['browser_download_url'])
