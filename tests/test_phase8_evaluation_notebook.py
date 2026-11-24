import json
from pathlib import Path


NOTEBOOK = Path("notebooks/phase8_one_time_evaluation.ipynb")


def test_phase8_notebook_is_local_and_colab_portable():
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    source = "\n".join(
        "".join(cell.get("source", [])) for cell in notebook["cells"]
    )
    assert "/content/HalalifyAI" in source
    assert "git" in source and "clone" in source
    assert "feature/model-evaluation" in source
    assert "--single-branch" in source
    assert "'fetch', 'origin', REPO_REF" in source
    assert "'pull', '--ff-only', 'origin', REPO_REF" in source
    assert "google.colab" in source
    assert "Colab left Files sidebar" in source
    assert "files.upload()" not in source
    assert "Path('/content') / name" in source
    assert "reserved_features_and_labels.csv" in source
    assert "runner_validation.json" in source
    assert "run_one_time_evaluation" in source
    assert "Commit and push feature/model-evaluation first" in source
    assert "D:\\" not in source
    assert all(cell.get("execution_count") is None for cell in notebook["cells"] if cell["cell_type"] == "code")
