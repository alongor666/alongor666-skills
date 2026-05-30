# v1.20: 实现已迁至 lib/render/ 子包（lib/render/__init__.py）。
# Python 加载 lib.render 时会优先选择 lib/render/ package，本文件作为历史标记保留。
# 所有旧 import 路径（from lib import render_page / from lib.render import render_page）
# 通过 lib/__init__.py 和 lib/render/__init__.py 继续工作，无需修改下游代码。
