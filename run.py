"""三角债智能梳理与净额轧差系统 —— 本地启动入口。"""
from __future__ import annotations

import argparse
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

# 桌面快捷方式以无控制台方式启动时，把运行日志写入 data/server.log
if "--log" in sys.argv:
    try:
        _log_path = Path(__file__).resolve().parent / "data" / "server.log"
        _log_path.parent.mkdir(parents=True, exist_ok=True)
        _log_handle = open(_log_path, "a", encoding="utf-8", buffering=1)
        sys.stdout = _log_handle
        sys.stderr = _log_handle
        print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] 启动请求")
    except OSError:
        pass

from app.config import DATA_DIR
from app.server import DebtServer
from app.service import AppService, ServiceError


def port_available(host: str, port: int) -> bool:
    """连接测试：端口已有服务监听时返回 False，避免共用 8765 等常用端口。"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.25)
            return sock.connect_ex((host, port)) != 0
    except OSError:
        return False


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="三角债智能梳理与净额轧差系统")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址（默认仅本机）")
    parser.add_argument("--port", type=int, default=8765, help="监听端口")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--seed", action="store_true", help="首次启动时载入示例数据")
    parser.add_argument("--reset", action="store_true", help="清空本地数据后启动")
    parser.add_argument("--log", action="store_true", help="启动日志写入 data/server.log")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    service = AppService()
    if args.reset:
        service.reset_all()
        print("已清空本地业务数据。")
    if args.seed:
        try:
            result = service.seed_demo(force=args.reset)
            print(result.get("message") or "示例数据已载入。")
        except ServiceError as exc:
            print(f"示例数据未载入：{exc}")

    port = args.port
    server = None
    for candidate in range(port, port + 20):
        if not port_available(args.host, candidate):
            continue
        try:
            server = DebtServer(service, host=args.host, port=candidate)
            server.start(background=True)
            port = candidate
            break
        except OSError:
            continue
    if server is None:
        print("无法绑定本地端口，请使用 --port 指定其他端口。")
        return 1

    url = f"http://{args.host}:{port}"
    runtime_path = DATA_DIR / "runtime.url"
    try:
        runtime_path.parent.mkdir(parents=True, exist_ok=True)
        runtime_path.write_text(url, encoding="utf-8")
    except OSError:
        runtime_path = None

    print("=" * 66)
    print("  三角债智能梳理与净额轧差系统  V1.0")
    print("  本体规则推理 · 债务图谱 · 最小交易笔数轧差 · 本地数据闭环")
    print(f"  访问地址：{url}")
    print("  数据与密钥仅保存在本机 data/ 与 config/ 目录")
    print("  按 Ctrl+C 停止服务")
    print("=" * 66)

    if not args.no_browser:
        threading.Thread(target=lambda: (time.sleep(0.8), webbrowser.open(url)), daemon=True).start()

    try:
        while server.thread and server.thread.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n正在停止服务……")
        server.stop()
    finally:
        if runtime_path:
            try:
                runtime_path.unlink()
            except OSError:
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
