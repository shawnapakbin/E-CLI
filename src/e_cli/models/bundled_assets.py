"""bundled_assets.py: Asset manifest and download logic for bundled setup-helper model."""

from pathlib import Path
from typing import Optional

import hashlib
import urllib.request

ASSET_MANIFEST = [
    {
        "name": "qwen2.5-coder-3b.bin",
        "url": "https://huggingface.co/your-org/qwen2.5-coder-3b/resolve/main/model.bin",
        "sha256": "dummysha2563b"
    },
    {
        "name": "qwen2.5-coder-7b.bin",
        "url": "https://huggingface.co/your-org/qwen2.5-coder-7b/resolve/main/model.bin",
        "sha256": "dummysha2567b"
    },
    # Add runtime binaries as needed
]

class BundledAssetManager:
    def __init__(self, asset_dir: Optional[str] = None):
        self.asset_dir = Path(asset_dir or "~/.e-cli/bundled-assets").expanduser()
        self.asset_dir.mkdir(parents=True, exist_ok=True)

    def ensure_assets(self) -> bool:
        """Download and verify all assets in the manifest."""
        all_ok = True
        for asset in ASSET_MANIFEST:
            path = self.asset_dir / asset["name"]
            if not path.exists() or not self.verify_checksum(path, asset["sha256"]):
                print(f"Downloading {asset['name']}...")
                try:
                    urllib.request.urlretrieve(asset["url"], path)
                except Exception as exc:
                    print(f"Failed to download {asset['name']}: {exc}")
                    all_ok = False
                    continue
            if not self.verify_checksum(path, asset["sha256"]):
                print(f"Checksum failed for {asset['name']}")
                all_ok = False
        return all_ok

    def verify_checksum(self, asset_path: Path, expected_sha256: str) -> bool:
        if not asset_path.exists():
            return False
        h = hashlib.sha256()
        with open(asset_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest() == expected_sha256
