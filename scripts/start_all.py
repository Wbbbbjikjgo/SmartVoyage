"""Start the full SmartVoyage stack (registry + agents + gateway + web).

用法::

    python scripts/start_all.py
    python scripts/start_all.py --no-web
    python scripts/start_all.py --only registry weather

所有 A2A Agent 都会自行通过 stdio 拉起所需的 MCP Server，无需单独启动 MCP
进程，也无需为 MCP 分配端口。
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SERVICES: List[Tuple[str, str]] = [
    ("registry", "registry.server"),
    ("weather", "agents.weather"),
    ("flight", "agents.flight"),
    ("hotel", "agents.hotel"),
    ("train", "agents.train"),
    ("itinerary", "agents.itinerary"),
    ("api", "api.main"),
]

WEB_CMD = [
    sys.executable,
    "-m",
    "streamlit",
    "run",
    "web/app.py",
    "--server.port",
    "8501",
    "--server.address",
    "127.0.0.1",
]


def _env() -> Dict[str, str]:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = str(ROOT)
    return env


def _init_database() -> None:
    """Create tables and the default user before starting services."""
    try:
        from models.database import close_db, init_db, seed_default_user

        init_db()
        seed_default_user()
        close_db()
        print("[init] MySQL 表结构与默认用户已就绪")
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] MySQL 初始化失败，Itinerary Agent 将返回明确数据库错误: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Start SmartVoyage services")
    parser.add_argument(
        "--no-web", action="store_true", help="不启动 Streamlit 前端"
    )
    parser.add_argument(
        "--only",
        nargs="*",
        choices=[name for name, _ in SERVICES] + ["web"],
        help="只启动指定的服务",
    )
    args = parser.parse_args()

    selected = [
        (name, module)
        for name, module in SERVICES
        if not args.only or name in args.only
    ]

    env = _env()
    processes: Dict[str, subprocess.Popen] = {}

    _init_database()

    try:
        for name, module in selected:
            print(f"[start] {name}: python -m {module}")
            processes[name] = subprocess.Popen(
                [sys.executable, "-m", module],
                cwd=str(ROOT),
                env=env,
            )
            # 给注册中心和 Agent 一点启动时间
            time.sleep(2.5 if name == "registry" else 1.5)

        if not args.no_web and (not args.only or "web" in args.only):
            print("[start] web: streamlit run web/app.py")
            processes["web"] = subprocess.Popen(WEB_CMD, cwd=str(ROOT), env=env)

        print("\n所有服务已启动。按 Ctrl+C 停止。\n")
        while True:
            for name, proc in list(processes.items()):
                code = proc.poll()
                if code is not None:
                    print(f"[exit] {name} exited with code {code}")
                    return
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n正在停止所有服务...")
    finally:
        for name, proc in reversed(list(processes.items())):
            if proc.poll() is None:
                print(f"[stop] {name}")
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                        capture_output=True,
                    )
                else:
                    proc.terminate()
        for name, proc in processes.items():
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
