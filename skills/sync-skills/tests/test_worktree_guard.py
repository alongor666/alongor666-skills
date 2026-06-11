"""sync-skills 防劫持护栏测试。

背景（2026-06-11 实测事故）：在 linked worktree 内触发 post-checkout 钩子，
`git rev-parse --show-toplevel` 返回 worktree 根，把 ~/.claude/skills 全部软链
指进 worktree；worktree 一删，19 条链全成死链。

护栏两层：
1. 脚本层（cmd 通用）：REPO 落在 linked worktree → 自动改用主仓根（git-common-dir 推导）。
2. 钩子层：生成的 post-merge / post-checkout 在 linked worktree 内直接跳过。

测试全程使用临时仓 + 临时 --dest，不触碰真实 ~/.claude/skills。
"""
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "sync-skills.sh"


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)


def git(*args, cwd):
    # commit.gpgsign=false：宿主若全局强制提交签名，临时仓签名失败会以 128 崩掉夹具
    return run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "-c", "commit.gpgsign=false", *args],
        cwd=cwd,
    )


@pytest.fixture()
def repo_with_worktree(tmp_path):
    """主仓（含 skills/demo 技能）+ 一个 linked worktree。"""
    repo = tmp_path / "repo"
    (repo / "skills" / "demo").mkdir(parents=True)
    (repo / "skills" / "demo" / "SKILL.md").write_text("---\nname: demo\n---\n")
    git("init", "-q", cwd=repo)
    git("add", "-A", cwd=repo)
    git("commit", "-q", "-m", "init", cwd=repo)
    wt = tmp_path / "wt"
    git("worktree", "add", "-q", str(wt), "-b", "t", cwd=repo)
    return repo, wt


def test_link_from_worktree_redirects_to_main_root(repo_with_worktree, tmp_path):
    """--repo 传 worktree：软链必须指回主仓源，而非 worktree 内路径。"""
    repo, wt = repo_with_worktree
    dest = tmp_path / "dest"
    out = run([str(SCRIPT), "link", "--repo", str(wt), "--dest", str(dest)]).stdout
    assert "linked worktree" in out  # 护栏触发并提示
    target = os.path.realpath(dest / "demo")
    assert target == os.path.realpath(repo / "skills" / "demo")
    assert os.path.realpath(str(wt)) not in target


def test_link_from_main_repo_unaffected(repo_with_worktree, tmp_path):
    """普通主仓路径不受护栏影响，行为与原版一致。"""
    repo, _ = repo_with_worktree
    dest = tmp_path / "dest"
    out = run([str(SCRIPT), "link", "--repo", str(repo), "--dest", str(dest)]).stdout
    assert "linked worktree" not in out
    assert os.path.realpath(dest / "demo") == os.path.realpath(repo / "skills" / "demo")


def test_generated_hook_skips_inside_worktree(repo_with_worktree, tmp_path):
    """install-hooks 生成的 post-checkout：worktree 内跳过，主仓内正常补链。"""
    repo, wt = repo_with_worktree
    dest = tmp_path / "dest"
    run([str(SCRIPT), "install-hooks", "--repo", str(repo), "--dest", str(dest)])
    hook = repo / ".githooks" / "post-checkout"
    assert hook.exists()

    # worktree 内执行（模拟分支切换，第三参=1）→ 跳过，不建链
    run(["bash", str(hook), "0", "0", "1"], cwd=wt)
    assert not (dest / "demo").exists()

    # 主仓内执行 → 正常建链指回主仓源
    run(["bash", str(hook), "0", "0", "1"], cwd=repo)
    assert os.path.realpath(dest / "demo") == os.path.realpath(repo / "skills" / "demo")
