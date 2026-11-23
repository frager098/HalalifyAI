"""Shared local/Colab setup for repository-backed student notebooks."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys


DEFAULT_BRANCH = "feature/model-evaluation"
DEFAULT_COLAB_REPOSITORY = Path("/content/HalalifyAI")
PHASE5_SHARED_FOLDER_URL = (
    "https://drive.google.com/drive/folders/1WQNAY14GOl1zznaXXCmF91mjIn-vHQiP"
)


def running_in_colab() -> bool:
    return "google.colab" in sys.modules


def prepare_repository(
    *,
    branch: str = DEFAULT_BRANCH,
    colab_repository: Path = DEFAULT_COLAB_REPOSITORY,
) -> Path:
    """Locate the current repository and verify its active branch."""

    if running_in_colab():
        root = colab_repository.resolve()
    else:
        root = Path.cwd().resolve()
        while root != root.parent and not (root / "src" / "model_training").is_dir():
            root = root.parent

    if not (root / "src" / "model_training").is_dir():
        raise FileNotFoundError(
            "Could not find the HalalifyAI repository. Run the Colab bootstrap "
            "cell first, or open local Jupyter inside the repository."
        )

    current_branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if current_branch != branch:
        raise RuntimeError(
            f"Expected branch {branch!r}, but {root} is on {current_branch!r}."
        )

    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def ensure_phase5_dataset(root: Path) -> Path:
    """Restore the Git-ignored Phase 5 CSV in Colab without mounting Drive."""

    from src.model_training.feature_ablation.phase5_continuation import (
        DATASET,
        EXPECTED_DATASET_SHA256,
    )
    from src.model_training.feature_ablation.feature_inventory import sha256

    destination = root / DATASET
    if destination.is_file():
        actual = sha256(destination)
        if actual != EXPECTED_DATASET_SHA256:
            raise RuntimeError(
                f"Existing Phase 5 dataset differs: expected "
                f"{EXPECTED_DATASET_SHA256}, found {actual}"
            )
        return destination

    if not running_in_colab():
        raise FileNotFoundError(
            f"Missing {destination}. Restore the Phase 5 generated CSV before Phase 6."
        )

    try:
        import gdown
    except ImportError as error:
        raise RuntimeError("Install gdown before restoring the Colab dataset") from error

    download_dir = Path("/content/HalalifyAI-phase5-inputs")
    download_dir.mkdir(parents=True, exist_ok=True)
    downloaded = gdown.download_folder(
        url=PHASE5_SHARED_FOLDER_URL,
        output=str(download_dir),
        quiet=False,
        use_cookies=False,
    )
    if not downloaded:
        raise RuntimeError("The shared Phase 5 artifact folder returned no files")
    matches = list(download_dir.rglob("market_features_and_labels.csv"))
    if len(matches) != 1:
        raise FileNotFoundError(
            "Expected exactly one market_features_and_labels.csv in the shared "
            f"Phase 5 folder; found {len(matches)}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(matches[0], destination)
    actual = sha256(destination)
    if actual != EXPECTED_DATASET_SHA256:
        destination.unlink()
        raise RuntimeError(
            f"Downloaded dataset failed verification: expected "
            f"{EXPECTED_DATASET_SHA256}, found {actual}"
        )
    return destination
