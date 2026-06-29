"""cleanup-worktrees 决策矩阵回归测试（正确性 oracle）。

背景：cleanup-worktrees.sh 会执行 `git worktree remove` + `git branch -D`（不可逆），
此前仅有一次性手工沙箱验证、无可重复回归（同仓 sync-skills / extract-backlog /
report-shell 都有 tests/，唯它没有）。本测试在临时 git 仓造 7 类 worktree 场景，
跑 `--dry-run` 断言每类落入正确决策桶（清理 / 待定 / 跳过），把决策矩阵行为锁成 oracle。

全程临时仓 + `--dry-run`，不触碰真实 worktree，不实际删除任何东西。
对照决策矩阵见 ../SKILL.md「决策矩阵」表。
"""
import os
import shutil
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


# ———— --archive 模式专项 oracle（破坏性备份路径，P2）————
#
# --archive 是唯一会「先备份再删」的破坏性路径，决策矩阵里两类候选会进入：
#   ① 脏 + HEAD 已合并(拓扑祖先)      → 备份脏改动(dirty.patch) → --force 删
#   ② clean + 有领先 commit 判不出落地 → 备份领先提交(format-patch) → 删
# 安全网：archive_wt 任一步失败 → 返回非 0 → 调用方拒删（落入 SKIP "备份失败"）。
# 这三条此前零专项测试（仅覆盖 dry-run + 默认删除），是最该覆盖的破坏性路径。
# 全程临时仓 + 临时 $WT_ARCHIVE，不触碰真实 ~/.worktree-archive、不触碰真实 worktree。


def run_archive(repo, skills_dir, archive_root):
    """跑 --archive：CLAUDE_SKILLS_DIR + WT_ARCHIVE 双重指向临时目录（双重隔离）。"""
    env = dict(os.environ, CLAUDE_SKILLS_DIR=str(skills_dir), WT_ARCHIVE=str(archive_root))
    return subprocess.run(
        ["/bin/bash", str(SCRIPT), "--archive"],
        cwd=repo, env=env, capture_output=True, text=True,
    )


def find_archive_dir(archive_root, name):
    """脚本归档落点 = $WT_ARCHIVE/orphan-worktrees-<YYYYMMDD>/<worktree名>/。
    用 glob 跳过日期拼接，返回该 worktree 的归档目录（不存在则 None）。"""
    hits = sorted(Path(archive_root).glob(f"orphan-worktrees-*/{name}"))
    return hits[0] if hits else None


def test_archive_clean_ahead_backs_up_then_removes(tmp_path):
    """② clean + 领先 commit 判不出落地 → --archive 先落 format-patch 再删。

    断言：领先提交补丁(format-patch) / dirty.patch / meta.txt 三件齐落 $WT_ARCHIVE
    → 备份成功才删 worktree（磁盘目录消失 + git 清单移除）。
    """
    repo, wtdir = make_origin_repo(tmp_path)
    path = wtdir / "wt-ahead"
    git("worktree", "add", "-q", str(path), "-b", "claude/ahead", cwd=repo)
    # 领先 1 个 commit（新增文件）、不合并、无 PR → landed() 判不出 → 进 --archive 备份桶
    (path / "ahead.txt").write_text("lead\n")
    git("add", "-A", cwd=path)
    git("commit", "-q", "-m", "ahead-commit", cwd=path)

    skills = tmp_path / "skills_home"; skills.mkdir()
    archive = tmp_path / "wt_archive"
    out = run_archive(repo, skills, archive).stdout

    # 报告：落「清理」桶并标 archived
    buckets = parse_report(out)
    assert "wt-ahead" in buckets["removed"], out
    assert "archived" in buckets["removed"]["wt-ahead"]
    assert "ARCHIVE+REMOVE" in out

    # 备份三件真落盘
    d = find_archive_dir(archive, "wt-ahead")
    assert d is not None and d.is_dir(), f"归档目录未生成: {list(Path(archive).rglob('*'))}"
    patches = [p for p in d.glob("*.patch") if p.name != "dirty.patch"]
    assert patches, f"format-patch 补丁缺失: {[p.name for p in d.iterdir()]}"  # 0001-ahead-commit.patch
    assert "ahead.txt" in patches[0].read_text()          # 补丁确含领先提交内容
    assert (d / "dirty.patch").exists()                    # clean → 空 dirty.patch 仍落盘
    meta = d / "meta.txt"
    assert meta.is_file() and meta.stat().st_size > 0
    meta_text = meta.read_text()
    assert "branch=claude/ahead" in meta_text and "HEAD=" in meta_text

    # 备份成功 → worktree 真删
    assert not path.exists(), "备份成功后 worktree 目录应被删除"
    assert "wt-ahead" not in run(["git", "worktree", "list"], cwd=repo).stdout


def test_archive_dirty_merged_backs_up_dirty_then_removes(tmp_path):
    """① 脏 + HEAD 已合并(拓扑祖先) → --archive 先落 dirty.patch 再 --force 删。

    构造："worktree 的提交已并入 origin/main(故 HEAD 是其拓扑祖先) + 残留未提交脏改动"。
    断言 dirty.patch 真含脏改动内容 + meta.txt 落盘 → 备份成功才删（且 force 删脏 worktree）。
    """
    repo, wtdir = make_origin_repo(tmp_path)
    path = wtdir / "wt-dirty-merged"
    git("worktree", "add", "-q", str(path), "-b", "claude/dirty-merged", cwd=repo)
    # worktree 提交 C1 → 把 C1 并入 origin/main → HEAD 成为 origin/main 的拓扑祖先（已落地）
    (path / "g.txt").write_text("merged-work\n")
    git("add", "-A", cwd=path)
    git("commit", "-q", "-m", "merged-commit", cwd=path)
    git("merge", "--no-ff", "-m", "merge dirty-merged", "claude/dirty-merged", cwd=repo)
    git("push", "-q", "origin", "main", cwd=repo)
    # worktree 残留未提交脏改动：改 tracked 文件，确保 `git diff HEAD` 捕获到内容
    (path / "f.txt").write_text("DIRTY-RESIDUE\n")

    skills = tmp_path / "skills_home"; skills.mkdir()
    archive = tmp_path / "wt_archive"
    out = run_archive(repo, skills, archive).stdout

    buckets = parse_report(out)
    assert "wt-dirty-merged" in buckets["removed"], out
    assert "archived" in buckets["removed"]["wt-dirty-merged"]
    assert "脏残留" in out and "HEAD已合并" in out

    d = find_archive_dir(archive, "wt-dirty-merged")
    assert d is not None and d.is_dir()
    dirty = d / "dirty.patch"
    assert dirty.is_file() and "DIRTY-RESIDUE" in dirty.read_text()  # 脏改动真备份
    meta = d / "meta.txt"
    assert meta.is_file() and meta.stat().st_size > 0
    assert "branch=claude/dirty-merged" in meta.read_text()
    # HEAD 是 origin/main 拓扑祖先 → format-patch(origin/main..HEAD) 必空（无领先提交）
    assert not [p for p in d.glob("*.patch") if p.name != "dirty.patch"]

    # 备份成功 → 脏 worktree 被 --force 删
    assert not path.exists(), "备份成功后脏 worktree 应被 --force 删除"
    assert "wt-dirty-merged" not in run(["git", "worktree", "list"], cwd=repo).stdout


def test_archive_backup_failure_refuses_delete(tmp_path):
    """安全网：archive_wt 备份失败(返回非 0) → 拒删 worktree，落 SKIP "备份失败"。

    构造备份必失败：把 $WT_ARCHIVE 指向一个【普通文件】，脚本
    `mkdir -p "<文件>/orphan-worktrees-.../<name>"` 必因路径中段是文件而失败
    → archive_wt 在第一步 `mkdir -p ... || return 1` 即返回 1。
    确定性、与运行用户/权限无关（即便 root，over-a-file 的 mkdir 也报 Not a directory）。
    这是 --archive 最关键的安全断言：备份没成 → 绝不能删。
    """
    repo, wtdir = make_origin_repo(tmp_path)
    path = wtdir / "wt-ahead"
    git("worktree", "add", "-q", str(path), "-b", "claude/ahead", cwd=repo)
    (path / "ahead.txt").write_text("lead\n")
    git("add", "-A", cwd=path)
    git("commit", "-q", "-m", "ahead-commit", cwd=path)

    skills = tmp_path / "skills_home"; skills.mkdir()
    blocker = tmp_path / "archive_is_a_file"   # 普通文件，非目录 → mkdir -p 必失败
    blocker.write_text("x")
    out = run_archive(repo, skills, blocker).stdout

    buckets = parse_report(out)
    assert "wt-ahead" not in buckets["removed"], "备份失败时绝不能删除"
    assert "wt-ahead" in buckets["skipped"], out
    reason = buckets["skipped"]["wt-ahead"]
    assert "备份失败" in reason and ("拒绝删除" in reason or "安全网" in reason)

    # worktree 必须原封不动留存
    assert path.is_dir(), "备份失败 → worktree 目录必须留存"
    assert "wt-ahead" in run(["git", "worktree", "list"], cwd=repo).stdout
    # blocker 仍是文件（没被脏写成目录），即确无任何真备份产物落地
    assert blocker.is_file()


# ———— 活跃会话 cwd 保护 oracle（补 git-lock 盲区，P1）————
#
# EnterWorktree / 多代理扇出创建的 worktree 默认【不打 git lock】；旧版仅认 git lock 的
# "运行中会话保护"，会把"活跃会话正坐着、但分支已落地(clean+祖先)"的 worktree 当零损失删掉，
# 把运行中会话的工作目录从底下抽走（真实事故：分支已 squash 合并、会话仍在该目录工作）。
# 本测试起一个活进程把 cwd 钉在【会被判 REMOVE】的 worktree 内，跑【默认模式真删】，
# 断言它反被 SKIP 且磁盘目录留存——证明 lsof-cwd 守卫真护住了运行中会话（不止认 git lock）。
# 全程临时仓 + 临时 sleep 子进程，收尾必 terminate；lsof 缺失则跳过（项目无关，优雅降级）。


@pytest.mark.skipif(shutil.which("lsof") is None, reason="需要 lsof 做活跃会话 cwd 检测")
def test_live_cwd_holder_protected_even_when_landed(tmp_path):
    """活进程 cwd 在 worktree 内（未 git-lock）+ 分支已落地 → SKIP 且目录留存。"""
    repo, wtdir = make_origin_repo(tmp_path)
    path = wtdir / "wt-live"
    # clean + HEAD=origin/main(拓扑祖先) → 旧版必判 REMOVE（零损失自动删）
    git("worktree", "add", "-q", str(path), "-b", "claude/live", cwd=repo)
    # 不 git-lock；起活进程把 cwd 钉在 worktree 内（模拟 EnterWorktree 的运行中会话）
    holder = subprocess.Popen(["sleep", "30"], cwd=str(path))
    try:
        skills = tmp_path / "skills_home"; skills.mkdir()
        out = run_cleanup(repo, skills).stdout  # 默认模式：真删未受保护的可删项
        buckets = parse_report(out)
        assert "wt-live" not in buckets["removed"], f"活跃会话 worktree 不得被删:\n{out}"
        assert "wt-live" in buckets["skipped"], out
        reason = buckets["skipped"]["wt-live"]
        assert "活" in reason or "运行中" in reason or "cwd" in reason
        # 磁盘 + git 清单双证：受保护目录留存
        assert path.is_dir(), "受保护的 worktree 目录必须留存"
        assert "wt-live" in run(["git", "worktree", "list"], cwd=repo).stdout
    finally:
        holder.terminate()
        holder.wait()
