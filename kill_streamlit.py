#!/usr/bin/env python3
"""
关闭所有 Streamlit 应用（安全版本）
功能：查找并终止所有 Streamlit 相关进程（排除自身）

用法: python3 kill_streamlit.py
"""

import subprocess
import signal
import os
import sys


def find_streamlit_pids():
    """查找所有 Streamlit 进程的 PID"""
    pids = []
    try:
        result = subprocess.run(
            ['pgrep', '-f', 'streamlit'],
            capture_output=True,
            text=True
        )
        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if line and line.isdigit():
                pid = int(line)
                # 排除当前进程
                if pid != os.getpid():
                    pids.append(pid)
    except Exception:
        pass
    return pids


def find_port_pids(ports=[8501, 8502, 8503]):
    """查找占用 Streamlit 端口的进程 PID"""
    pids = []
    for port in ports:
        try:
            result = subprocess.run(
                ['lsof', '-ti', f':{port}'],
                capture_output=True,
                text=True
            )
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if line and line.isdigit():
                    pid = int(line)
                    if pid not in pids:
                        pids.append(pid)
        except Exception:
            pass
    return pids


def kill_processes(pids, timeout=3):
    """终止进程列表"""
    killed = []
    failed = []
    
    for pid in pids:
        try:
            # 先尝试 SIGTERM
            os.kill(pid, signal.SIGTERM)
            killed.append(pid)
        except ProcessLookupError:
            pass  # 进程已不存在
        except PermissionError:
            failed.append((pid, "权限不足"))
        except Exception as e:
            failed.append((pid, str(e)))
    
    # 等待进程结束
    import time
    time.sleep(timeout)
    
    # 对未结束的进程使用 SIGKILL
    for pid in killed[:]:  # 复制列表
        try:
            os.kill(pid, 0)  # 检查进程是否还存在
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            killed.remove(pid)  # 已结束
        except PermissionError:
            failed.append((pid, "无法强制终止"))
    
    return killed, failed


def main():
    print("🔍 正在查找 Streamlit 进程...\n")
    
    # 排除自身
    current_pid = os.getpid()
    print(f"当前进程 PID: {current_pid}\n")
    
    # 查找 Streamlit 进程
    streamlit_pids = find_streamlit_pids()
    streamlit_pids = [p for p in streamlit_pids if p != current_pid]
    
    # 查找端口进程
    port_pids = find_port_pids()
    port_pids = [p for p in port_pids if p != current_pid]
    
    # 合并去重
    all_pids = list(set(streamlit_pids + port_pids))
    
    if not all_pids:
        print("✅ 未发现 Streamlit 进程")
        print("\n" + "=" * 50)
        print("  所有 Streamlit 应用已关闭")
        print("=" * 50 + "\n")
        return
    
    print(f"📊 发现 {len(all_pids)} 个相关进程:")
    
    # 获取进程信息
    for pid in all_pids:
        try:
            result = subprocess.run(
                ['ps', '-p', str(pid), '-o', 'comm='],
                capture_output=True, text=True
            )
            cmd = result.stdout.strip() or "Unknown"
            print(f"   PID {pid}: {cmd}")
        except Exception:
            print(f"   PID {pid}: (无法获取信息)")
    
    print(f"\n🛑 正在终止 {len(all_pids)} 个进程...")
    
    killed, failed = kill_processes(all_pids)
    
    print(f"\n📈 结果:")
    print(f"   ✅ 已终止: {len(killed)} 个")
    if failed:
        print(f"   ❌ 失败: {len(failed)} 个")
        for pid, err in failed:
            print(f"      PID {pid}: {err}")
    
    # 验证
    print("\n🔍 验证...")
    remaining = find_streamlit_pids()
    remaining = [p for p in remaining if p != current_pid]
    
    if remaining:
        print(f"⚠️  仍有 {len(remaining)} 个进程:")
        for pid in remaining:
            print(f"   PID {pid}")
    else:
        print("✅ 所有 Streamlit 进程已关闭")
    
    print("\n" + "=" * 50)
    print("  Streamlit 清理完成")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()
