"""
R3 · P1 批量验证提速 —— 把多个题目的多个候选放进同一份 Lean 文件，只 `import Mathlib` 一次。

为什么快：`lake env lean` 的耗时大头是 `import Mathlib`（每次编译都要摊一次）。
把 N 个 (题目, 候选) 拼进一个文件，import 只付一次，N 个候选全部判对错。
正确性裁定仍完全交给 Lean（×严格验证锚）。

复用：`src/lean_verifier.py` 的 `LeanVerifier` 与已验证的错误行号→候选映射逻辑。
"""
import os
import re
import sys
import time
from typing import List, Dict, Optional

# 让 R3 代码能用 src 里已验证好的验证锚
_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'src')
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from lean_verifier import LeanVerifier, VerifyResult  # noqa: E402


def _strip_theorem_name(statement: str) -> str:
    """`theorem foo ...` → ` ...`（保留 binders/结论/`:= by`），供复用改名 x0..xN。"""
    return re.sub(r'^theorem\s+\w+', '', statement)


def batch_verify_many(entries: List[Dict], verifier: LeanVerifier,
                      temp_dir: Optional[str] = None,
                      chunk: int = 200,
                      import_line: str = 'import Mathlib') -> Dict:
    """一次编译验证大量 (题目, 候选)。

    Args:
        entries: [{'key': str, 'theorem_statement': str, 'proof_code': str}, ...]
        verifier: LeanVerifier
        temp_dir: 临时目录
        chunk: 每份文件最多条数（防单文件过大/错误行号错位）
        import_line: import 行（默认 'import Mathlib' 全量，安全）；可按需传
                     'import Mathlib.Tactic' 等较小 import 加速（B 类降本 ③，
                     R4 修复：继承模块此处曾硬编码全量，未接 on_demand_import）。

    Returns:
        {key: VerifyResult}
    """
    results: Dict = {}
    if not entries:
        return results

    # 按 chunk 分批（每批一个文件，一次 import）
    for s in range(0, len(entries), chunk):
        batch = entries[s:s + chunk]
        results.update(_compile_batch(batch, verifier, temp_dir, import_line))
    return results


def _compile_batch(batch: List[Dict], verifier: LeanVerifier,
                   temp_dir: Optional[str],
                   import_line: str = 'import Mathlib') -> Dict:
    """编译一份文件并逐条判对错。"""
    parts = [import_line, "", "open scoped Nat", "open scoped Real", ""]
    for i, e in enumerate(batch):
        body = _strip_theorem_name(e['theorem_statement'])
        proof = e.get('proof_code', '')
        parts.append(f"theorem x{i}{body}")
        # 空证明/含 sorry 用会报错的占位，避免假通过
        if not proof.strip() or verifier._contains_sorry(proof):
            parts.append("  this_is_not_a_valid_tactic_xyz")
        else:
            parts.append(proof)
        parts.append("")
    full_code = "\n".join(parts)

    if temp_dir:
        os.makedirs(temp_dir, exist_ok=True)
        import tempfile as _tempfile
        fd, filepath = _tempfile.mkstemp(suffix='.lean', dir=temp_dir)
    else:
        import tempfile as _tempfile
        fd, filepath = _tempfile.mkstemp(suffix='.lean')

    out = {}
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(full_code)

        start = time.time()
        try:
            res = subprocess_run(filepath, verifier)
            elapsed = time.time() - start
        except subprocess_timeout():
            elapsed = time.time() - start
            for i, e in enumerate(batch):
                out[e['key']] = VerifyResult(False, 'batch compile timeout', round(elapsed, 2), True)
            return out

        lines = full_code.split('\n')
        theorem_lines = {}
        for ln, ltxt in enumerate(lines):
            m = re.match(r'^theorem\s+x(\d+)', ltxt)
            if m:
                theorem_lines[int(m.group(1))] = ln
        ordered = sorted(theorem_lines.items())

        combined = (res.stderr or '') + '\n' + (res.stdout or '')
        # 只认真正的 `error:`（warning 不是失败，不判 fail、不触发 fail-closed）。
        # Lean 诊断格式：<file>:<line>:<col>: error: <msg> / warning: <msg>。
        error_lines = set()      # 真实 error 行号（1-based）
        parsed_errors = []       # (line, text)，仅 error
        for m in re.finditer(r'([^\n]*?):(\d+):\d+:\s*(error|warning):', combined):
            kind = m.group(3)
            if kind != 'error':
                continue
            error_lines.add(int(m.group(2)))
            ln = int(m.group(2))
            seg_start = m.end()
            nxt = re.search(r'(?=[^\n]*?:\d+:\d+:\s*(?:error|warning):)', combined[seg_start:])
            text = combined[seg_start: seg_start + nxt.start()] if nxt else combined[seg_start:]
            parsed_errors.append((ln, text))

        # 关键（fail-closed）：绝不"无候选级错误 → 全体成功"。
        # 情形1：`import Mathlib` 失败（error 落在第1行 = import 行）→ 整批不可信。
        # 情形2：Lean 返回非零，但存在"无法归属到任何候选"的错误行（如头块里 open scoped
        #        失败、或错误行落在首个定理之前/之后的全局区），说明编译上下文被破坏，
        #        此时个别候选的成功不可信（会把坏候选误判为真通过 = 假阳性）。
        # 情形3：Lean 返回非零，却一行 error 都没解析到（错误格式未匹配 / 输出被截断 /
        #        import 相关异常），同样无法信任"成功" → 整批判 verify_error。
        #        正确做法：整体判 verify_error，交由金标准单验逐个复试（批量只当预筛）。
        first_th = ordered[0][1] if ordered else None
        global_err = (res.returncode != 0 and
                      any((ln - 1) < first_th if first_th is not None else True
                          for ln in error_lines))
        no_parseable_err = (res.returncode != 0 and not error_lines)
        if 1 in error_lines or (res.returncode != 0 and not theorem_lines) \
                or global_err or no_parseable_err:
            msg = ('global/header error (batch invalid, fail-closed)'
                   if (global_err or no_parseable_err) else 'import Mathlib failed (batch invalid)')
            for _e in batch:
                out[_e['key']] = VerifyResult(False, msg, round(elapsed, 2), False)
            return out

        failed = set()
        for err_line in error_lines:
            el = err_line - 1  # lean 1-based -> 0-based
            # 归属：错误行属于"起始行 ≤ el 的最近一个定理"。
            # 修复边界 bug：旧逻辑以 `el < end`（下一定理起始行，排他）判归属，
            # 当错误行恰好落在下一定理起始行时会被漏掉 → 该候选被误判为成功（假通过）。
            owner = None
            for idx, l0 in ordered:  # ordered = [(index, start_line)] 按行号升序
                if l0 <= el:
                    owner = idx
                else:
                    break
            if owner is not None:
                failed.add(owner)

        for i, e in enumerate(batch):
            key = e['key']
            proof = e.get('proof_code', '')
            if not proof.strip():
                out[key] = VerifyResult(False, 'empty proof', round(elapsed, 2), False)
            elif verifier._contains_sorry(proof):
                out[key] = VerifyResult(False, 'Proof contains sorry', round(elapsed, 2), False)
            elif i in failed:
                # 按候选行范围提取该候选的错误片段（供未来 beam/分析）
                try:
                    from goal_parser import extract_goals
                    cl0 = ordered[i][1] if i < len(ordered) else 0
                    cl1 = ordered[i + 1][1] if i + 1 < len(ordered) else len(lines)
                    seg = '\n'.join(t for (ln, t) in parsed_errors if cl0 <= ln < cl1)
                    g = extract_goals(seg) if seg else []
                except Exception:
                    g = []
                out[key] = VerifyResult(False, combined[:800], round(elapsed, 2), False, goals=g)
            else:
                out[key] = VerifyResult(True, '', round(elapsed, 2), False)
    finally:
        try:
            os.unlink(filepath)
        except OSError:
            pass
    return out


def subprocess_run(filepath, verifier):
    """执行 `lake env lean <file>`。独立函数便于单测打桩。"""
    import subprocess
    return subprocess.run(
        ['lake', 'env', 'lean', filepath],
        capture_output=True, text=True,
        timeout=max(verifier.timeout, 300),
        cwd=verifier.mathlib4_dir, encoding='utf-8', errors='replace',
    )


def subprocess_timeout():
    import subprocess
    return subprocess.TimeoutExpired


if __name__ == '__main__':
    v = LeanVerifier()
    demo = [
        {'key': 'p1/norm_num', 'theorem_statement': 'theorem p1 : 1 + 1 = 2 := by', 'proof_code': '  norm_num'},
        {'key': 'p1/bad', 'theorem_statement': 'theorem p1 : 1 + 1 = 3 := by', 'proof_code': '  norm_num'},
        {'key': 'p2/linarith', 'theorem_statement': 'theorem p2 (a b : ℝ) (h : a = 3) (h2 : b = 4) : a + b = 7 := by', 'proof_code': '  linarith'},
    ]
    print("将批量验证 3 条（含 1 条应为 False）...")
    r = batch_verify_many(demo, v)
    for k, vr in r.items():
        print(f"  {k}: success={vr.success}  ({vr.error_message[:60]})")
