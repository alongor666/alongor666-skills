"""cleanup-worktrees 决策矩阵回归测试（正确性 oracle）。

背景：cleanup-worktrees.sh 会执行 `git worktree remove` + `git branch -D`（不可逆），
此前仅有一次性手工沙箱验证、无可重复回归（同仓 sync-skills / extract-backlog /
report-shell 都有 tests/，唯它没有）。本测试在临时 git 仓造 7 类 worktree 场景，
跑 `--dry-run` 断言每类落入正确决策桶（清理 / 待定 / 跳过），把决策矩阵行为锁成 oracle。

全程临时仓 + `--dry-run`，不触碰真实 worktree，不实际删除任何东西。
对照决策矩阵见 ../SKILL.md「决策矩阵」表。
"""
import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "cleanup-worktrees.sh"
# 远超 macOS pid_max(默认 99998)，ps -p 必然查无此进程 → 模拟陈旧锁(持锁进程已死)
DEAD_PID = 999999


def run(cmd, cwd=None, check=True):
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True)


def git(*args, cwd):
    # commit.gpgsign=false：宿主若全局强制签名，临时仓签名会以 128 崩掉夹具（同仓约定）
    return run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "-c", "commit.gpgsign=false", *args],
        cwd=cwd,
    )


def make_origin_repo(tmp_path):
    """造 origin(bare) + 主仓(main 已 push) + 空 .claude/worktrees/，返回 (repo, wtdir)。"""
    origin = tmp_path / "origin.git"
    run(["git", "init", "--bare", "-q", str(origin)])
    repo = tmp_path / "repo"
    run(["git", "clone", "-q", str(origin), str(repo)])
    (repo / "f.txt").write_text("base\n")
    git("checkout", "-q", "-b", "main", cwd=repo)
    git("add", "-A", cwd=repo)
    git("commit", "-q", "-m", "init", cwd=repo)
    git("push", "-q", "-u", "origin", "main", cwd=repo)
    wtdir = repo / ".claude" / "worktrees"
    wtdir.mkdir(parents=True)
    return repo, wtdir


def run_cleanup(repo, skills_dir, mode=None):
    """跑清理脚本，把 CLAUDE_SKILLS_DIR 指向临时目录（不触碰真实 ~/.claude/skills）。"""
    env = dict(os.environ, CLAUDE_SKILLS_DIR=str(skills_dir))
    cmd = ["/bin/bash", str(SCRIPT)] + ([mode] if mode else [])
    return subprocess.run(cmd, cwd=repo, env=env, capture_output=True, text=True)


def parse_report(text):
    """把脚本结构化报告解析成 {bucket: {name: body_line}}。bucket ∈ removed/listed/skipped。"""
    buckets = {"removed": {}, "listed": {}, "skipped": {}}
    cur = None
    for line in text.splitlines():
        if line.startswith("====") or line.startswith("worktree "):
            cur = None
            continue
        if line.startswith("清理 "):
            cur = "removed"; continue
        if line.startswith("待定 "):
            cur = "listed"; continue
        if line.startswith("跳过 "):
            cur = "skipped"; continue
        s = line.strip()
        if cur and s[:1] in {"✓", "•", "-"}:  # ✓ • -
            body = s[1:].strip()
            if not body or body.startswith("（无）"):  # （无）
                continue
            name = body.split(":")[0].split(" [")[0].split(" ")[0].strip()
            buckets[cur][name] = body
    return buckets


@pytest.fixture()
def scenario(tmp_path):
    """造 origin(bare) + 主仓 + 7 类 worktree，跑一次 --dry-run，返回 (buckets, report)。"""
    repo, wtdir = make_origin_repo(tmp_path)

    def add(name, branch=None, detach=False):
        path = wtdir / name
        if detach:
            git("worktree", "add", "-q", "--detach", str(path), "HEAD", cwd=repo)
        else:
            git("worktree", "add", "-q", str(path), "-b", branch, cwd=repo)
        return path

    def commit_in(path, fname, content="new\n", msg="ahead"):
        (path / fname).write_text(content)
        git("add", "-A", cwd=path)
        git("commit", "-q", "-m", msg, cwd=path)

    # 1) REMOVE：clean + HEAD=origin/main（拓扑祖先）
    add("wt-remove", "claude/remove")
    # 2) LIST：clean + 领先 1 commit、未落地
    commit_in(add("wt-ahead", "claude/ahead"), "x.txt")
    # 3) SKIP：locked + 持锁进程存活（用测试进程自身 pid，必活）
    add("wt-locked", "claude/locked")
    git("worktree", "lock", "--reason", f"session pid {os.getpid()}",
        str(wtdir / "wt-locked"), cwd=repo)
    # 4) REMOVE：陈旧锁（死 pid）解锁后 → clean + 祖先
    add("wt-stale", "claude/stale")
    git("worktree", "lock", "--reason", f"session pid {DEAD_PID}",
        str(wtdir / "wt-stale"), cwd=repo)
    # 5) SKIP：脏 + HEAD 未落地（领先 commit + 未提交改动）
    p = add("wt-dirty", "claude/dirty")
    commit_in(p, "y.txt")
    (p / "y.txt").write_text("dirtier\n")  # 制造脏
    # 6) SKIP：detached HEAD
    add("wt-detached", detach=True)
    # 7) SKIP：分支前缀不在白名单
    add("wt-prefix", "feature/x")

    res = run(["/bin/bash", str(SCRIPT), "--dry-run"], cwd=repo)
    return parse_report(res.stdout), res.stdout


ALL_WORKTREES = [
    "wt-remove", "wt-ahead", "wt-locked", "wt-stale",
    "wt-dirty", "wt-detached", "wt-prefix",
]


def test_clean_ancestor_removed(scenario):
    """clean + 拓扑祖先 → REMOVE。"""
    buckets, _ = scenario
    assert "wt-remove" in buckets["removed"]


def test_stale_lock_unlocked_then_removed(scenario):
    """陈旧锁（持锁进程已死）→ 解锁提示 + 按 clean 重判为 REMOVE。"""
    buckets, report = scenario
    assert "wt-stale" in buckets["removed"]
    assert "可安全解锁" in report  # 可安全解锁


def test_clean_ahead_listed(scenario):
    """clean + 有领先 commit、判不出落地 → 默认 LIST（建议 --archive）。"""
    buckets, _ = scenario
    assert "wt-ahead" in buckets["listed"]


def test_locked_alive_skipped(scenario):
    """locked + 持锁进程存活 → SKIP（保护运行中会话），优先级高于可删。"""
    buckets, _ = scenario
    assert "wt-locked" in buckets["skipped"]
    reason = buckets["skipped"]["wt-locked"]
    assert "持锁" in reason or "运行中" in reason  # 持锁 / 运行中


def test_dirty_unlanded_skipped(scenario):
    """脏 + HEAD 未落地 → SKIP（可能有未保存工作）。"""
    buckets, _ = scenario
    assert "wt-dirty" in buckets["skipped"]
    assert "未落地" in buckets["skipped"]["wt-dirty"]  # 未落地


def test_detached_skipped(scenario):
    """detached HEAD → SKIP。"""
    buckets, _ = scenario
    assert "wt-detached" in buckets["skipped"]
    assert "detached" in buckets["skipped"]["wt-detached"]


def test_prefix_not_whitelisted_skipped(scenario):
    """分支前缀不在白名单 → SKIP。"""
    buckets, _ = scenario
    assert "wt-prefix" in buckets["skipped"]
    assert "前缀" in buckets["skipped"]["wt-prefix"]  # 前缀


def test_dry_run_removes_nothing(scenario):
    """--dry-run 必须零实际删除：报告末尾 worktree 清单仍含全部 7 个。"""
    _, report = scenario
    for n in ALL_WORKTREES:
        assert n in report, f"{n} 不应在 --dry-run 后消失"


def test_dry_run_keeps_worktree_dirs_on_disk(tmp_path):
    """--dry-run 强断言：可删候选(clean+祖先)的目录在磁盘上仍留存、git 清单逐字不变。

    （补 test_dry_run_removes_nothing 的弱点：后者仅查名字在报告文本，
    而 dry-run 候选名也会出现在「清理」列表，无法区分留存 vs 候选。）
    """
    repo, wtdir = make_origin_repo(tmp_path)
    git("worktree", "add", "-q", str(wtdir / "wt-remove"), "-b", "claude/remove", cwd=repo)
    skills = tmp_path / "skills_home"
    skills.mkdir()
    before = run(["git", "worktree", "list"], cwd=repo).stdout
    run_cleanup(repo, skills, mode="--dry-run")
    after = run(["git", "worktree", "list"], cwd=repo).stdout
    assert (wtdir / "wt-remove").is_dir(), "dry-run 不得删除磁盘上的 worktree 目录"
    assert before == after, "dry-run 后 git worktree 清单必须逐字不变"


# ———— 软链自愈收尾（P1）oracle ————

def test_selfcheck_warns_and_suggests_fix_on_dead_link(tmp_path):
    """实际删除后，CLAUDE_SKILLS_DIR 下有死链 → 报告必须预警并给出修复命令。"""
    repo, wtdir = make_origin_repo(tmp_path)
    git("worktree", "add", "-q", str(wtdir / "wt-remove"), "-b", "claude/remove", cwd=repo)
    skills = tmp_path / "skills_home"
    skills.mkdir()
    (skills / "ghost").symlink_to(tmp_path / "nonexistent_target")  # 故意造死链
    out = run_cleanup(repo, skills).stdout  # 默认模式（非 dry-run）→ 真删 wt-remove
    assert "死软链" in out
    assert "ghost" in out
    assert "修复" in out and "sync-skills.sh" in out  # 探到兄弟 sync-skills → 给具体命令


def test_selfcheck_silent_when_links_healthy(tmp_path):
    """实际删除后，软链全健康 → 不得有任何死链预警（零误报）。"""
    repo, wtdir = make_origin_repo(tmp_path)
    git("worktree", "add", "-q", str(wtdir / "wt-remove"), "-b", "claude/remove", cwd=repo)
    skills = tmp_path / "skills_home"
    skills.mkdir()
    real = tmp_path / "real_skill"
    real.mkdir()
    (skills / "alive").symlink_to(real)  # 健康链
    out = run_cleanup(repo, skills).stdout
    assert "死软链" not in out


def test_selfcheck_skipped_in_dry_run(tmp_path):
    """--dry-run 没真删任何东西 → 即便有死链也不触发自检（避免空预警）。"""
    repo, wtdir = make_origin_repo(tmp_path)
    git("worktree", "add", "-q", str(wtdir / "wt-remove"), "-b", "claude/remove", cwd=repo)
    skills = tmp_path / "skills_home"
    skills.mkdir()
    (skills / "ghost").symlink_to(tmp_path / "nonexistent_target")
    out = run_cleanup(repo, skills, mode="--dry-run").stdout
    assert "死软链" not in out
