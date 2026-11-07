"""Install official project-local llama.cpp binaries; do not download or modify models."""
import hashlib
import io
import json
import pathlib
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGET = ROOT / "tools" / "bin" / "llama"

with urllib.request.urlopen("https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=1", timeout=30) as response:
    release = json.load(response)[0]
assets = [a for a in release["assets"] if a["name"].endswith("bin-win-cuda-12.4-x64.zip")]
if len(assets) != 2:
    raise RuntimeError("Expected separate official Windows CUDA 12.4 binary and runtime archives")
TARGET.mkdir(parents=True, exist_ok=True)
evidence = {"release": release["tag_name"], "source": release["html_url"], "assets": []}
for asset in assets:
    print("Downloading", asset["name"], f"{asset['size'] / 1e6:.1f} MB", flush=True)
    with urllib.request.urlopen(asset["browser_download_url"], timeout=90) as response:
        payload = response.read()
    actual = hashlib.sha256(payload).hexdigest()
    expected = asset.get("digest", "").removeprefix("sha256:")
    if not expected or actual != expected:
        raise RuntimeError("Official asset digest is unavailable or does not match; installation stopped")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = pathlib.PurePosixPath(info.filename)
            if name.is_absolute() or ".." in name.parts:
                raise RuntimeError("Invalid archive member")
            path = TARGET / name.name
            path.write_bytes(archive.read(info))
    evidence["assets"].append({"name": asset["name"], "sha256": actual, "source": asset["browser_download_url"]})
(ROOT / "docs" / "evidence" / "llama-installation.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
print("Installed", TARGET / "llama-server.exe", flush=True)
