"""
Lean 4 证明验证器
调用 lake env lean 编译验证一个证明是否通过。
"""
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from typing import Optional, List

# P2修复：mathlib4路径从环境变量读取，默认值仅作兜底
MATHLIB4_DIR = os.environ.get('MATHLIB4_DIR', r"D:\mathlib4")
DEFAULT_TIMEOUT = 120  # 秒


def _clean_lean_output(text: str) -> str:
    """清洗 Lean 输出：去掉 info 噪声行（如 'info: MathExplorerVerify...'、'plausible: cloning...'），
    保留真正的 error:/warning:/目标（'⊢'）行。否则噪声淹没真错误/goals，导致喂回给模型的反馈失真
    （教训 #17：plausible: cloning 是 info 噪声；教训 #27：反馈环需真实 error/goals）。
    """
    if not text:
        return text
    lines = text.split('\n')
    kept = []
    for ln in lines:
        s = ln.strip()
        if not s:
            # 保留空行用于分隔目标/错误块（但对纯空行不保留太多）
            kept.append('')
            continue
        low = s.lower()
        # 过滤 info 噪声：'info:' 开头，或含 'cloning'/'no previous manifest'/'toolchain not updated'
        if low.startswith('info:') or 'cloning' in low or 'no previous manifest' in low or 'toolchain not updated' in low:
            continue
        kept.append(ln)
    # 折叠多余空行
    out = []
    prev_blank = False
    for ln in kept:
        if ln.strip() == '' and prev_blank:
            continue
        out.append(ln)
        prev_blank = (ln.strip() == '')
    return '\n'.join(out).strip()



@dataclass
class VerifyResult:
    success: bool
    error_message: str
    compile_time_seconds: float
    timeout: bool = False
    goals: List[str] = field(default_factory=list)  # 未闭合目标（from error, 供 goal 逐步搜索）


class LeanVerifier:
    """Lean 4 证明验证器"""

    def __init__(self, mathlib4_dir: str = MATHLIB4_DIR, timeout: int = DEFAULT_TIMEOUT):
        # 教训（peek_goals/verify 秒回空、import Mathlib 在 1 行报错）：调用方显式传 None 会覆盖默认值，
        # 导致 cwd=None → lake env lean 在非 lake 项目目录秒败。None 一律回退到默认 MATHLIB4_DIR。
        self.mathlib4_dir = mathlib4_dir if mathlib4_dir else MATHLIB4_DIR
        self.timeout = timeout

    def verify(self, theorem_statement: str, proof_code: str,
               temp_dir: Optional[str] = None, import_line: str = 'import Mathlib') -> VerifyResult:
        """
        验证一个证明是否通过。

        Args:
            theorem_statement: 定理声明（从theorem到 := by），如 "theorem foo : 1 + 1 = 2 := by"
            proof_code: LLM生成的证明代码（tactic序列），如 "  norm_num"
            temp_dir: 临时文件目录，None则用系统临时目录
            import_line: import 行（默认 'import Mathlib' = 全量，安全）；可按需传
                         'import Mathlib.Tactic' 等较小 import 加速（B 类降本 ③）。
                         默认行为不变。

        Returns:
            VerifyResult: 验证结果
        """
        # 组合完整的Lean文件
        full_code = f"""{import_line}

open scoped Nat
open scoped Real

{theorem_statement}
{proof_code}
"""

        # 写入临时文件
        if temp_dir:
            os.makedirs(temp_dir, exist_ok=True)
            fd, filepath = tempfile.mkstemp(suffix='.lean', dir=temp_dir)
        else:
            fd, filepath = tempfile.mkstemp(suffix='.lean')

        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(full_code)

            # 调用lean编译
            start_time = time.time()
            try:
                result = subprocess.run(
                    ['lake', 'env', 'lean', filepath],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    cwd=self.mathlib4_dir,
                    encoding='utf-8',
                    errors='replace'
                )
                elapsed = time.time() - start_time

                if result.returncode == 0:
                    # P0修复：检测证明中是否包含sorry（占位符，不算有效证明）
                    has_sorry = self._contains_sorry(proof_code) or self._contains_sorry(theorem_statement)
                    # 声锚加固：空/纯空白证明不算有效（若无 Lean 代码，返回码可能仍为 0）
                    if not proof_code.strip():
                        return VerifyResult(
                            success=False,
                            error_message='Empty proof (no Lean code)',
                            compile_time_seconds=round(elapsed, 2),
                            timeout=False
                        )
                    if has_sorry:
                        return VerifyResult(
                            success=False,
                            error_message='Proof contains sorry (placeholder, not a valid proof)',
                            compile_time_seconds=round(elapsed, 2),
                            timeout=False
                        )
                    return VerifyResult(
                        success=True,
                        error_message='',
                        compile_time_seconds=round(elapsed, 2),
                        timeout=False
                    )
                else:
                    # 提取错误信息
                    error_msg = (result.stderr or result.stdout or '').strip()
                    # 清洗：去掉 info 噪声行（如 'info: MathExplorerVerify...'/'plausible: cloning'），
                    # 保留真正的 error:/warning:/'⊢' 目标；再截断。否则噪声淹没真错误/goals（教训#17/#27）。
                    error_msg = _clean_lean_output(error_msg)
                    error_msg = error_msg[:3000]
                    # 解析未闭合目标（供 goal 逐步搜索）
                    try:
                        from goal_parser import extract_goals
                        goals = extract_goals(error_msg)
                    except Exception:
                        goals = []
                    return VerifyResult(
                        success=False,
                        error_message=error_msg,
                        compile_time_seconds=round(elapsed, 2),
                        timeout=False,
                        goals=goals,
                    )

            except subprocess.TimeoutExpired:
                elapsed = time.time() - start_time
                return VerifyResult(
                    success=False,
                    error_message=f'Compilation timed out after {self.timeout}s',
                    compile_time_seconds=round(elapsed, 2),
                    timeout=True
                )

        finally:
            # 清理临时文件
            try:
                os.unlink(filepath)
            except OSError:
                pass

    def warm_mathlib(self) -> bool:
        """预 warm Mathlib：编译一个 trivial 证明，把 `import Mathlib` 加载进 .lake 缓存，
        使后续 peek_goals / verify / batch_verify 的 import 更稳定（避免冷启动偶发失败）。"""
        try:
            r = self.verify('theorem _warm_probe : True := by', '  trivial')
            return r.success
        except Exception:
            return False

    def peek_goals(self, theorem_statement: str, temp_dir: Optional[str] = None) -> List[str]:
        """用 done 占位编译一次（done 对未闭合目标会报 unsolved goals），解析目标栈（仅诊断）。"""
        full_code = f"""import Mathlib

open scoped Nat
open scoped Real

{theorem_statement}
  done
"""
        if temp_dir:
            os.makedirs(temp_dir, exist_ok=True)
            fd, filepath = tempfile.mkstemp(suffix='.lean', dir=temp_dir)
        else:
            fd, filepath = tempfile.mkstemp(suffix='.lean')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(full_code)
            try:
                result = subprocess.run(
                    ['lake', 'env', 'lean', filepath],
                    capture_output=True, text=True, timeout=max(self.timeout, 600),
                    cwd=self.mathlib4_dir, encoding='utf-8', errors='replace'
                )
            except subprocess.TimeoutExpired:
                return []
            out = (result.stderr or result.stdout or '')
            try:
                from goal_parser import extract_goals
                return extract_goals(out)
            except Exception:
                return []
        finally:
            try:
                os.unlink(filepath)
            except OSError:
                pass

    def batch_verify(self, theorem_statement: str, candidates: List[dict],
                     temp_dir: Optional[str] = None,
                     import_line: str = 'import Mathlib') -> dict:
        """
        批量验证同一定理的多个候选证明（一次 `import Mathlib`，逐个判对错，摊薄成本）。

        Args:
            theorem_statement: 定理声明（含名字与 := by）
            candidates: [{'candidate_id': int, 'proof_code': str}, ...]
            temp_dir: 临时目录
            import_line: import 行（默认 'import Mathlib' 全量，安全）；可按需传
                         'import Mathlib.Tactic' 等较小 import 加速（B 类降本 ③）。

        Returns:
            {candidate_id: VerifyResult}
        """
        results = {}
        if not candidates:
            return results

        # 提取定理名之后的陈述体（binders + 结论 + := by），供每个候选复用（名字唯一 c0..cN）
        body = re.sub(r'^theorem\s+\w+', '', theorem_statement)

        parts = [import_line, "", "open scoped Nat", "open scoped Real", ""]
        for i, cand in enumerate(candidates):
            proof = cand.get('proof_code', '')
            parts.append(f"theorem c{i}{body}")
            parts.append(proof if proof.strip() else "  this_is_not_a_valid_tactic_xyz")  # 空证明用会报错的占位，避免 sorry 假通过
            parts.append("")
        full_code = "\n".join(parts)

        if temp_dir:
            os.makedirs(temp_dir, exist_ok=True)
            fd, filepath = tempfile.mkstemp(suffix='.lean', dir=temp_dir)
        else:
            fd, filepath = tempfile.mkstemp(suffix='.lean')

        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(full_code)

            start_time = time.time()
            try:
                result = subprocess.run(
                    ['lake', 'env', 'lean', filepath],
                    capture_output=True, text=True,
                    timeout=max(self.timeout, 300),
                    cwd=self.mathlib4_dir, encoding='utf-8', errors='replace'
                )
                elapsed = time.time() - start_time
            except subprocess.TimeoutExpired:
                elapsed = time.time() - start_time
                for cand in candidates:
                    results[cand.get('candidate_id', 0)] = VerifyResult(
                        False, 'batch compile timeout', round(elapsed, 2), timeout=True)
                return results

            lines = full_code.split('\n')
            # 每个 theorem c<i> 的起始行（0-based）
            theorem_lines = {}
            for ln, ltxt in enumerate(lines):
                m = re.match(r'^theorem\s+c(\d+)', ltxt)
                if m:
                    theorem_lines[int(m.group(1))] = ln
            ordered = sorted(theorem_lines.items())

            # 错误行号 → 所属候选（Lean 诊断可能走 stdout 或 stderr，都解析）
            combined = (result.stderr or '') + '\n' + (result.stdout or '')
            error_lines = set()
            parsed_errors = []  # (start_line, error_text)，供按候选解析 goals
            for m in re.finditer(r'([^\n]*?):(\d+):\d+:\s*(?:error|warning):', combined):
                error_lines.add(int(m.group(2)))
                ln = int(m.group(2))
                seg_start = m.end()
                nxt = re.search(r'(?=[^\n]*?:\d+:\d+:\s*(?:error|warning):)', combined[seg_start:])
                text = combined[seg_start: seg_start + nxt.start()] if nxt else combined[seg_start:]
                parsed_errors.append((ln, text))
            failed = set()
            for err_line in error_lines:
                el = err_line - 1  # lean 1-based -> 0-based
                for k, (idx, l0) in enumerate(ordered):
                    end = ordered[k + 1][1] if k + 1 < len(ordered) else len(lines)
                    if l0 <= el < end:
                        failed.add(idx)
                        break

            for i, cand in enumerate(candidates):
                cid = cand.get('candidate_id', i)
                proof = cand.get('proof_code', '')
                if not proof.strip():
                    results[cid] = VerifyResult(False, 'empty proof', round(elapsed, 2), False)
                elif self._contains_sorry(proof):
                    results[cid] = VerifyResult(False, 'Proof contains sorry', round(elapsed, 2), False)
                elif i in failed:
                    # 按候选行范围从错误段提取各自 goals（供 beam 剪枝）
                    try:
                        from goal_parser import extract_goals
                        cl0 = ordered[i][1] if i < len(ordered) else 0
                        cl1 = ordered[i + 1][1] if i + 1 < len(ordered) else len(lines)
                        seg = '\n'.join(t for (ln, t) in parsed_errors if cl0 <= ln < cl1)
                        g = extract_goals(seg) if seg else []
                    except Exception:
                        g = []
                    results[cid] = VerifyResult(False, combined[:1000], round(elapsed, 2), False, goals=g)
                else:
                    results[cid] = VerifyResult(True, '', round(elapsed, 2), False)
            return results
        finally:
            try:
                os.unlink(filepath)
            except OSError:
                pass

    def _contains_sorry(self, code: str) -> bool:
        """
        检测代码中是否包含独立的sorry关键字（占位符）

        注意：需要匹配独立的sorry单词，避免误匹配sorry_lemma等标识符
        """
        if not code:
            return False
        # 匹配独立的sorry单词（前后不是字母数字下划线）
        pattern = r'(?<![a-zA-Z0-9_])sorry(?![a-zA-Z0-9_])'
        return bool(re.search(pattern, code))


def quick_test():
    """快速测试验证器"""
    verifier = LeanVerifier()

    # 测试1：正确的证明
    print("测试1：正确证明 (1+1=2, norm_num)")
    result = verifier.verify(
        theorem_statement="theorem test1 : 1 + 1 = 2 := by",
        proof_code="  norm_num"
    )
    print(f"  结果: success={result.success}, 耗时={result.compile_time_seconds}s")
    if not result.success:
        print(f"  错误: {result.error_message[:200]}")

    # 测试2：错误的证明
    print("\n测试2：错误证明 (1+1=3)")
    result = verifier.verify(
        theorem_statement="theorem test2 : 1 + 1 = 3 := by",
        proof_code="  norm_num"
    )
    print(f"  结果: success={result.success}, 耗时={result.compile_time_seconds}s")
    if not result.success:
        print(f"  错误: {result.error_message[:200]}")

    # 测试3：含实数的证明
    print("\n测试3：实数证明 (linarith)")
    result = verifier.verify(
        theorem_statement="theorem test3 (a b : ℝ) (h : a = 3) (h2 : b = 4) : a + b = 7 := by",
        proof_code="  linarith"
    )
    print(f"  结果: success={result.success}, 耗时={result.compile_time_seconds}s")
    if not result.success:
        print(f"  错误: {result.error_message[:200]}")


if __name__ == '__main__':
    quick_test()
