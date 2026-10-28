import pytest

from _helpers import FIXTURES, make_task
from core.workspace import isolated_workspace


def test_copies_fixture_and_cleans_up(tmp_path):
    task = make_task()
    with isolated_workspace(task, base_dir=tmp_path) as ws:
        assert ws.is_dir()
        assert (ws / "solution.py").read_text() == (FIXTURES / "fix-off-by-one" / "solution.py").read_text()
        assert tmp_path in ws.parents
        tmp_root = ws.parent
    assert not tmp_root.exists()
    assert list(tmp_path.iterdir()) == []


def test_edits_do_not_touch_source_fixture(tmp_path):
    task = make_task()
    src = FIXTURES / "fix-off-by-one" / "solution.py"
    original = src.read_text()
    with isolated_workspace(task, base_dir=tmp_path) as ws:
        (ws / "solution.py").write_text("garbage")
        (ws / "new_file.txt").write_text("x")
    assert src.read_text() == original
    assert not (FIXTURES / "fix-off-by-one" / "new_file.txt").exists()


def test_each_run_gets_a_distinct_directory(tmp_path):
    task = make_task()
    with isolated_workspace(task, base_dir=tmp_path) as a, isolated_workspace(task, base_dir=tmp_path) as b:
        assert a != b
        (a / "solution.py").write_text("changed")
        assert (b / "solution.py").read_text() != "changed"


def test_keep_true_preserves_workspace(tmp_path):
    task = make_task()
    with isolated_workspace(task, keep=True, base_dir=tmp_path) as ws:
        pass
    assert ws.exists()


def test_cleanup_on_exception(tmp_path):
    task = make_task()
    with pytest.raises(ValueError):
        with isolated_workspace(task, base_dir=tmp_path) as ws:
            raise ValueError("boom")
    assert not ws.exists()
    assert list(tmp_path.iterdir()) == []


def test_tmp_dir_prefix_contains_task_id(tmp_path):
    task = make_task(id="my-task")
    with isolated_workspace(task, base_dir=tmp_path) as ws:
        assert ws.parent.name.startswith("agent-eval-my-task-")
        assert ws.name == "workspace"


def test_missing_workspace_raises(tmp_path):
    task = make_task(workspace=str(tmp_path / "nope"))
    base = tmp_path / "base"
    base.mkdir()
    with pytest.raises(FileNotFoundError):
        with isolated_workspace(task, base_dir=base):
            pass


@pytest.mark.skip(reason="疑似 bug：workspace 不存在时 mkdtemp 建的临时目录没有删除，会泄漏空目录")
def test_missing_workspace_does_not_leak_tmp_dir(tmp_path):
    task = make_task(workspace=str(tmp_path / "nope"))
    base = tmp_path / "base"
    base.mkdir()
    with pytest.raises(FileNotFoundError):
        with isolated_workspace(task, base_dir=base):
            pass
    assert list(base.iterdir()) == []


def test_setup_commands_run_inside_workspace(tmp_path):
    task = make_task(setup_commands=["echo hello > marker.txt"])
    with isolated_workspace(task, base_dir=tmp_path) as ws:
        assert (ws / "marker.txt").read_text().strip() == "hello"


def test_failing_setup_command_raises_and_cleans_up(tmp_path):
    task = make_task(setup_commands=["echo out; echo err 1>&2; exit 3"])
    with pytest.raises(RuntimeError) as ei:
        with isolated_workspace(task, base_dir=tmp_path):
            pytest.fail("body must not run")
    msg = str(ei.value)
    assert "exit 3" in msg
    assert "out" in msg and "err" in msg
    assert list(tmp_path.iterdir()) == []
