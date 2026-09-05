"""
goal_parser.py — 从 Lean 验证输出中解析当前未闭合目标（unsolved goals）。

Lean 失败时，error 消息通常形如：
  unsolved goals
  case h
  this : ...
  ⊢ x = 60
或者多目标：
  unsolved goals
  ⊢ x = 60
  ⊢ y = 30

目标以 '⊢' 开始，可能跨多行（PP 折叠）。本模块用正则提取所有目标，
作为"当前待证目标栈"，供 goal 逐步搜索的下一步建议使用。
"""
import re

GOAL_MARK = '⊢'
# 目标体：从 '⊢' 后抓取，直到下一个 '⊢' 或连续两个换行（空行）为止
_GOAL_SPLIT = re.compile(r'⊢|\n\s*\n')


def extract_goals(lean_output: str) -> list:
    """从 Lean 输出提取所有未闭合目标，每条一个字符串。无目标返回 []。"""
    if not lean_output:
        return []
    goals = []
    for m in re.finditer(GOAL_MARK, lean_output):
        rest = lean_output[m.end():]
        nxt = _GOAL_SPLIT.search(rest)
        g = rest[:nxt.start()] if nxt else rest
        g = g.strip()
        if g:
            goals.append(g)
    # 去重（保持顺序）
    seen = []
    for g in goals:
        if g and g not in seen:
            seen.append(g)
    return seen


def max_goals(lean_output: str, cap: int = 5) -> list:
    """提取目标并截断到前 cap 条（避免目标过多撑爆 prompt）。"""
    return extract_goals(lean_output)[:cap]
