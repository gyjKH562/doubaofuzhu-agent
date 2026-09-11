# -*- coding: utf-8 -*-
"""
test_api.py —— 通用 API 手动测试脚本

为什么写它：Swagger 的 Try it out 有两大坑——① 预填示例值（如 article_id=0、
'topic': 'string'），直接点执行会把脏数据写进库；② body 编辑框容易留尾逗号、
删不干净字段。用命令行脚本测接口：所见即所发，绕开所有编辑器坑。

用法（在项目根目录、服务已启动时运行）：
    python scripts/test_api.py get /health
    python scripts/test_api.py post /api/article '{"topic": "测试"}'
    python scripts/test_api.py post /api/refine '{"article_id": 10}'
    python scripts/test_api.py put /api/article/1 '{"topic": "新标题"}'
    python scripts/test_api.py delete /api/article/1

只依赖 Python 标准库（urllib），无需安装任何新包。
"""
import json          # JSON 解析/序列化
import sys           # 读命令行参数
import urllib.error  # HTTP 错误（4xx/5xx）
import urllib.request  # 发 HTTP 请求

# 服务地址：和 .env 的 APP_HOST/APP_PORT 保持一致（改端口时这里同步改）
BASE_URL = "http://127.0.0.1:8000"
# 请求超时（秒）：测试接口等太久就放弃，避免挂死
TIMEOUT = 60


def show_result(status: int, body_text: str) -> None:
    """打印状态码 + 响应体（响应体是 JSON 时美化输出，方便人眼核对）。"""
    print(f"\nHTTP 状态码: {status}")
    try:
        # 尝试把响应体按 JSON 美化（对齐缩进，中文不转义）
        pretty = json.dumps(json.loads(body_text), ensure_ascii=False, indent=2)
        print("响应体:")
        print(pretty)
    except json.JSONDecodeError:
        # 响应体不是合法 JSON（如空响应 204）就原样打印
        print("响应体:", body_text or "(空)")


def main() -> None:
    """命令行入口：解析参数 → 发请求 → 打印结果。"""
    # ① 参数检查：至少要有 method 和 path 两个参数
    if len(sys.argv) < 3:
        print("用法: python scripts/test_api.py <get|post|put|delete> <path> [json_body]")
        print("示例: python scripts/test_api.py post /api/refine '{\"article_id\": 10}'")
        sys.exit(1)  # 非零退出码 = 用法错误

    # ② 取参数：method 转小写，path 必须 / 开头
    method = sys.argv[1].lower()          # 'POST' → 'post'（大小写不敏感）
    path = sys.argv[2]                    # 如 '/api/refine'
    if not path.startswith("/"):          # 防御：漏写 / 会自动补，别让用户报错
        path = "/" + path
    # ③ 可选第三参：JSON body 字符串（POST/PUT 常用）
    body_str = sys.argv[3] if len(sys.argv) > 3 else None

    # ③b POST/PUT 没传 body 时交互式输入：
    #     PowerShell 会把命令行里的双引号剥掉（'{"a": 1}' → {a: 1}），
    #     用 input() 从键盘读就完全没有引号问题——所见即所发。
    if body_str is None and method in ("post", "put"):
        body_str = input("请输入 JSON body（如 {\"article_id\": 10}）: ").strip()
        if not body_str:  # 用户直接回车 = 不想要 body
            body_str = None

    # ④ 构造请求：有 body 就编码成 UTF-8 字节，并声明 Content-Type
    data = None
    headers = {}
    if body_str is not None:
        data = body_str.encode("utf-8")               # 字符串 → 字节（HTTP 传输用字节）
        headers["Content-Type"] = "application/json"  # 告诉服务器 body 是 JSON

    url = BASE_URL + path                              # 拼完整 URL
    req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())

    print(f"请求: {method.upper()} {url}")
    if body_str:
        print(f"body: {body_str}")

    # ⑤ 发请求并处理两类结果：正常响应 / HTTP 错误响应
    try:
        resp = urllib.request.urlopen(req, timeout=TIMEOUT)   # 2xx/3xx：正常路径
        show_result(resp.status, resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # 4xx/5xx：服务器返回了，但状态码是错误——响应体里通常有 detail 可看
        show_result(e.code, e.read().decode("utf-8"))
    except urllib.error.URLError as e:
        # 连不上服务器（服务没启动 / 地址错了）——这是环境问题不是接口问题
        print(f"\n连接失败: {e.reason}")
        print("检查: 服务是否已启动？(python main.py) 端口是否是 8000？")


if __name__ == "__main__":
    main()
