#!/usr/bin/env python3
"""回归：注册位置判定必须同时做到「不假绿」与「不假红」，且与客户端种类无关。

本用例全部走显式参数（--mcp-config / --registry-cmd / --registries）并把数据表
指向临时表，因此不依赖运行机器的真实 MCP 配置，也不依赖任何特定客户端。

覆盖两种通用形态 × 三个方向：

1. 入口指向别的 checkout → 必须不是 ready，且必须点明「不一致」（假绿防线）
2. 入口指向本地 dist     → 必须 ready（假红防线）
3. 哪里都没注册          → 必须不是 ready，且不崩
4. TOML 形态与 CLI 形态  → 与 JSON 形态给出同样的判定
5. 配置里的相对入口       → 按配置文件所在目录解析
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_lanhu_mcp.py"


def run_check(skill, out, *, mcp_configs=(), registry_cmds=(), registries=None, extra_path=None):
    """调用检查脚本；数据表默认由调用方指定，避免受本机真实配置影响。"""
    env = dict(os.environ)
    if extra_path:
        env["PATH"] = f"{extra_path}{os.pathsep}{env.get('PATH', '')}"
    argv = [sys.executable, str(SCRIPT), "--skill-dir", str(skill), "--output", str(out)]
    for cfg in mcp_configs:
        argv += ["--mcp-config", str(cfg)]
    for cmd in registry_cmds:
        argv += ["--registry-cmd", cmd]
    if registries is not None:
        argv += ["--registries", str(registries)]
    proc = subprocess.run(argv, capture_output=True, text=True, env=env)
    if not out.exists():
        raise SystemExit(f"检查脚本未产出结果：{(proc.stderr or proc.stdout).strip()[:400]}")
    return json.loads(out.read_text())


def write_json_config(path, entrypoint, *, relative=False):
    """写一份最小 MCP JSON 配置。relative=True 时写相对入口，用于验证解析基准。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    written = os.path.relpath(entrypoint, path.parent) if relative else str(entrypoint)
    path.write_text(json.dumps({
        "mcpServers": {
            "lanhu-mcp": {
                "type": "stdio",
                "command": "/usr/bin/python3",
                "args": [written],
                "env": {"LANHU_COOKIE": "placeholder"},
            }
        }
    }), encoding="utf-8")
    return path


def write_toml_config(path, entrypoint):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "[mcp_servers.lanhu-mcp]\n"
        'command = "/usr/bin/python3"\n'
        f'args = ["{entrypoint}"]\n'
        "\n"
        "[mcp_servers.lanhu-mcp.env]\n"
        'LANHU_COOKIE = "placeholder"\n'
        'LANHU_AUTHORIZATION = "placeholder"\n',
        encoding="utf-8",
    )
    return path


def write_cli_stub(bin_dir, entrypoint, *, name="fake-mcp-cli"):
    """写一个中性名字的注册查询命令替身，模拟 kind: cli 的输出。"""
    bin_dir.mkdir(parents=True, exist_ok=True)
    stub = bin_dir / name
    stub.write_text(
        "#!/usr/bin/env bash\n"
        "cat <<'EOF'\n"
        "lanhu-mcp\n"
        "  enabled: true\n"
        "  transport: stdio\n"
        "  command: /usr/bin/python3\n"
        f"  args: {entrypoint}\n"
        "  cwd: -\n"
        "  env: LANHU_AUTHORIZATION=*****, LANHU_COOKIE=*****\n"
        "EOF\n"
        "exit 0\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return stub


def main():
    problems = []

    def expect(condition, message):
        if not condition:
            problems.append(message)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        skill = tmp / "skill"
        dist = skill / "lanhu-mcp" / "lanhu_mcp_server.py"
        dist.parent.mkdir(parents=True)
        dist.write_text("# stub\n")

        empty_table = tmp / "empty-table.json"
        empty_table.write_text(json.dumps({"registries": []}), encoding="utf-8")

        elsewhere = tmp / "other-checkout" / "lanhu-mcp" / "lanhu_mcp_server.py"
        elsewhere.parent.mkdir(parents=True)
        elsewhere.write_text("# other checkout\n")

        # —— 方向 1：JSON 配置指向别的 checkout ——
        cfg_bad = write_json_config(tmp / "wrong" / "mcp.json", elsewhere)
        data = run_check(skill, tmp / "out-wrong.json", mcp_configs=[cfg_bad], registries=empty_table)
        expect(data.get("status") != "ready",
               f"入口指向别的 checkout 却报告 ready（假绿）：{data.get('status')}")
        expect(data.get("entrypointMatches") is False, "entrypointMatches 应为 false")
        expect(bool(data.get("registeredEntrypoint")),
               "需要记录已发现的入口，否则无法审计")
        expect(any("不一致" in reason for reason in data.get("blockingReasons") or []),
               f"未点明入口与本地 dist 不一致：{data.get('blockingReasons')}")
        expect((data.get("readyRegistries") or []) == [],
               f"readyRegistries 应为空：{data.get('readyRegistries')}")

        # —— 方向 2：JSON 配置指向本地 dist，用相对入口验证解析基准 ——
        cfg_ok = write_json_config(tmp / "right" / "mcp.json", dist, relative=True)
        data = run_check(skill, tmp / "out-right.json", mcp_configs=[cfg_ok], registries=empty_table)
        expect(data.get("status") == "ready",
               f"入口指向本地 dist 却不是 ready（假红）：{data.get('blockingReasons')}")
        expect(data.get("entrypointMatches") is True, "entrypointMatches 应为 true")
        first = (data.get("registrations") or [{}])[0]
        expect((first.get("credentials") or {}).get("LANHU_COOKIE") is True,
               "未记录凭据键是否已配置（只判键，不取值）")

        # —— 方向 3：哪里都没注册 ——
        data = run_check(skill, tmp / "out-none.json", registries=empty_table)
        expect(data.get("status") != "ready", "没有任何注册却报告 ready")
        expect(any("未在任何" in reason for reason in data.get("blockingReasons") or []),
               f"未说明「哪里都没找到」：{data.get('blockingReasons')}")
        expect("suggestedRegistrations" in data,
               "阻塞时应给出与客户端无关的通用注册片段")

        # —— 方向 4：TOML 形态 ——
        toml_ok = write_toml_config(tmp / "toml" / "config.toml", dist)
        table = tmp / "toml-table.json"
        table.write_text(json.dumps({
            "serverName": "lanhu-mcp",
            "registries": [{
                "id": "toml-shape",
                "kind": "mcp-toml",
                "serverTablePath": ["mcp_servers"],
                "locations": [str(toml_ok)],
            }],
        }), encoding="utf-8")
        data = run_check(skill, tmp / "out-toml.json", registries=table)
        expect(data.get("status") == "ready",
               f"TOML 配置指向本地 dist 却不是 ready：{data.get('blockingReasons')}")
        expect(data.get("readyRegistries") == ["toml-shape"],
               f"readyRegistries 应为 ['toml-shape']：{data.get('readyRegistries')}")

        # —— 方向 5：CLI 形态（中性名字的替身，不绑定任何客户端） ——
        bin_dir = tmp / "fakebin"
        write_cli_stub(bin_dir, elsewhere)
        data = run_check(skill, tmp / "out-cli-bad.json", registries=empty_table,
                         registry_cmds=["fake-mcp-cli"], extra_path=bin_dir)
        expect(data.get("status") != "ready", "CLI 形态指向别的 checkout 却报告 ready")
        expect(any("不一致" in reason for reason in data.get("blockingReasons") or []),
               f"CLI 形态未点明不一致：{data.get('blockingReasons')}")

        write_cli_stub(bin_dir, dist)
        data = run_check(skill, tmp / "out-cli-ok.json", registries=empty_table,
                         registry_cmds=["fake-mcp-cli"], extra_path=bin_dir)
        expect(data.get("status") == "ready",
               f"CLI 形态指向本地 dist 却不是 ready：{data.get('blockingReasons')}")

        # 命令不存在时只能记为未命中，不能崩。
        data = run_check(skill, tmp / "out-cli-missing.json", registries=empty_table,
                         registry_cmds=["definitely-not-a-real-cli-xyz"])
        expect(data.get("status") != "ready", "命令不存在却报告 ready")
        expect((data.get("registrations") or [{}])[0].get("error") == "executable-not-found",
               f"命令不存在时应记为 executable-not-found：{(data.get('registrations') or [{}])[0]}")

        # —— 数据表缺失/损坏时仍要能用显式参数 ——
        data = run_check(skill, tmp / "out-no-table.json", mcp_configs=[cfg_ok],
                         registries=tmp / "absent-table.json")
        expect(data.get("status") == "ready",
               f"数据表缺失时显式 --mcp-config 应仍生效：{data.get('blockingReasons')}")
        expect((data.get("registriesTable") or {}).get("error") == "table-missing",
               "应记录数据表缺失这一事实")

    for problem in problems:
        print(problem)
    if problems:
        return 1

    print("注册位置判定：JSON/TOML/CLI 三种形态均不假绿、不假红，缺表与缺命令不崩")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
