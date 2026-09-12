"""
tests/test_rate_limiter.py —— 限流器单元测试（纯逻辑，不碰网络/数据库）

单元测试的对象：FixedWindowLimiter（第 10 步实现）。
为什么单独测它：限流逻辑是"纯函数式"的（输入 key + 时间 → 输出放行与否），
不依赖任何外部系统，是单元测试最理想的目标。
"""
import pytest  # 测试框架（pytest.raises 等断言工具）

from services.rate_limiter import FixedWindowLimiter  # 被测对象


def test_窗口内前N次请求放行():
    """正常路径：max_requests=3 时，前 3 次都应放行。"""
    limiter = FixedWindowLimiter(max_requests=3, window_seconds=60)  # 每分钟 3 次
    # 连续 3 次都应返回 True（放行并计数）
    assert limiter.allow("ip-1") is True
    assert limiter.allow("ip-1") is True
    assert limiter.allow("ip-1") is True


def test_超过上限被拒绝():
    """边界路径：第 4 次（超出上限）必须被拒绝。"""
    limiter = FixedWindowLimiter(max_requests=3, window_seconds=60)
    for _ in range(3):          # 先用完 3 次额度
        limiter.allow("ip-1")
    assert limiter.allow("ip-1") is False  # 第 4 次：拒绝


def test_不同key计数互相独立():
    """隔离性：A 的请求不影响 B 的额度（限流按 IP 隔离的依据）。"""
    limiter = FixedWindowLimiter(max_requests=1, window_seconds=60)
    assert limiter.allow("ip-a") is True   # A 用掉唯一额度
    assert limiter.allow("ip-b") is True   # B 依然可以（独立计数）
    assert limiter.allow("ip-a") is False  # A 超限


def test_窗口过期后计数重置(monkeypatch):
    """时间推进：窗口过期后，额度应自动恢复（关键的状态重置逻辑）。"""
    # ① 用"假时钟"控制时间：monkeypatch 替换 time.monotonic 的实现
    fake_now = [1000.0]                       # 用列表包一层，闭包可修改
    monkeypatch.setattr(
        "services.rate_limiter.time.monotonic",  # 替换限流器模块里的时钟
        lambda: fake_now[0],                     # 返回当前假时间
    )

    limiter = FixedWindowLimiter(max_requests=2, window_seconds=60)
    assert limiter.allow("ip-1") is True    # 第 1 次
    assert limiter.allow("ip-1") is True    # 第 2 次
    assert limiter.allow("ip-1") is False   # 第 3 次：超限被拒

    fake_now[0] += 61.0                     # ② 模拟 61 秒后（超过 60 秒窗口）
    assert limiter.allow("ip-1") is True    # ③ 窗口重置，重新放行
