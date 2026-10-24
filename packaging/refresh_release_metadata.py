"""Keep published asset names and checksums consistent after packaging fixes."""
import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wxocr import __version__


def api(endpoint, *args):
    return subprocess.run(['gh', 'api', endpoint, *args], text=True, capture_output=True, check=True).stdout


def main():
    repository = subprocess.check_output(['gh', 'repo', 'view', '--json', 'nameWithOwner', '--jq', '.nameWithOwner'], text=True).strip()
    endpoint = f'repos/{repository}/releases/tags/v{__version__}'
    try:
        release = json.loads(api(endpoint))
    except subprocess.CalledProcessError as exc:
        if '404' in exc.stderr:
            print('No release for the current version yet; nothing to refresh.')
            return
        raise
    for asset in release['assets']:
        if asset['name'] == 'default.txt':
            api(f"repos/{repository}/releases/assets/{asset['id']}", '--method', 'PATCH', '-f', 'name=Windows-README.txt')
    release = json.loads(api(endpoint))
    lines = []
    for asset in sorted(release['assets'], key=lambda a: a['name'].casefold()):
        if asset['name'] == 'SHA256SUMS.txt':
            continue
        digest = asset.get('digest') or ''
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
            raise RuntimeError(f"GitHub did not provide a SHA256 digest for {asset['name']}")
        lines.append(f"{digest.removeprefix('sha256:')}  {asset['name']}\n")
    Path('SHA256SUMS.txt').write_text(''.join(lines), encoding='utf-8')
    subprocess.run(['gh', 'release', 'upload', f'v{__version__}', 'SHA256SUMS.txt', '--clobber', '--repo', repository], check=True)
    print(f'Refreshed v{__version__}: {len(lines)} asset checksums.')


if __name__ == '__main__':
    main()
