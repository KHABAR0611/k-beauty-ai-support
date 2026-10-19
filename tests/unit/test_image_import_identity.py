import copy
import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location("image_cache", Path(__file__).resolve().parents[2] / "infrastructure/cache_qdrant_image.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def identities():
    official = {"os": "linux", "architecture": "amd64", "rootfs": {"diff_ids": ["sha256:layer"]}, "config": {"Entrypoint": ["/qdrant/entrypoint.sh"], "User": "1000"}}
    actual = {"Id": "sha256:containerd-import-id", "Os": "linux", "Architecture": "amd64", "RootFS": {"Layers": ["sha256:layer"]}, "Config": copy.deepcopy(official["config"])}
    return actual, official


def test_containerd_import_id_is_not_config_digest():
    module.verify_loaded_image(*identities())


@pytest.mark.parametrize("change", ["platform", "rootfs", "entrypoint"])
def test_wrong_imported_image_is_rejected(change):
    actual, official = identities()
    if change == "platform":
        actual["Architecture"] = "arm64"
    elif change == "rootfs":
        actual["RootFS"]["Layers"] = ["sha256:other"]
    else:
        actual["Config"]["Entrypoint"] = ["/other"]
    with pytest.raises(ValueError):
        module.verify_loaded_image(actual, official)
