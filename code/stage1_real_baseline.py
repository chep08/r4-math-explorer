"""
R4 · B 轨 Stage 1 P0：真实基线 P(ρ) —— "具体事实库 → 真实深缺口目标"
=================================================================================
背景：合成 P(ρ)（stage1_synthetic.py）测出上升相变，但那是**需桥接引理**的合成目标。
P0 用**真实同域目标**（seed_corpus 的 deep-gap 深缺口）——它们大多是"自带战术闭不了"的
难题（实测 1/8 自闭环）。本实验测：**具体事实库（别题已证结论）能否辅助闭合这些真实深缺口？**

预期（诚实）：库片段是**别题的具体事实**（如某线性方程的结论），作为通用引理**很难**桥接
真实深缺口 → 真实 P(ρ) 可能 **≈0/平坦**（β 分支 / 概念闭包）。这作为**真实基线**，
与 P1（泛化骨架库 → 真实目标）对比，展示"泛化是必须的"（H3）。

方法（真实 Lean 闭合判定）：
    对每个密度 ρ，取库片段子集 → 对每个真实目标生成候选证明（库片段 exact + 模板战术）
    → 用 batch_verify_many 一次 import 验所有 (目标,候选)，目标任一候选闭合即闭合 → P(ρ)。
    ⚠️ v1 简化：当前候选用模板战术（不含库片段引理注入），测"真实深缺口目标 + 战术自闭环率"
    （基线1）。库片段作为引理真正注入在 P1（泛化骨架库）做。因此本基线 P(ρ) 反映的是
    "真实深缺口目标在机械锤下的闭合率"——预期低且不随库密度涨（因为库不真正参与）。

用法：
    python stage1_real_baseline.py --library stage1_library.jsonl \
        --targets stage1_targets_samedomain.jsonl --n-points 10 --max-targets 12 --out report_stage1_real_baseline.json
"""
import os
import sys
import json
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, '..', '..', 'src')
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

try:
    from warm_sandbox import WarmSandbox  # noqa: E402
    from lean_verifier import LeanVerifier  # noqa: E402
    from lean_batch import batch_verify_many  # noqa: E402
    HAVE_LEAN = True
except Exception:  # pragma: no cover
    HAVE_LEAN = False

# 模板战术（闭合用 on-demand 战术）
TACTICS = ['linarith', 'omega', 'ring_nf', 'ring', 'simp', 'simp_all', 'nlinarith', 'rfl', 'decide']


def load_jsonl(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def density_slice(library, rho, seed=42):
    """取库片段按密度 ρ 的子集（确定性抽样）。"""
    import random
    n = len(library)
    if n == 0:
        return []
    size = max(1, int(round(n * rho)))
    rng = random.Random(seed)
    idx = list(range(n)); rng.shuffle(idx); idx = sorted(idx[:size])
    return [library[i] for i in idx]


def build_proof_candidates(frag_names):
    """为单个目标生成候选证明（独立条目，每条一个 proof_code）。
    ⚠️ 修正：去除 `exact <库片段名>` 候选——它无意义（库片段名不是目标所需引理）且
    在 batch_verify_many 上制造假阳性（把错误归属错乱判为 success）。候选只用模板战术。
    """
    cands = []
    for tac in TACTICS:
        cands.append(f'  {tac}')
    return cands


def run_real_baseline(library, targets, n_points=10, verifier=None, seed=42):
    """真实 Lean 密度扫描（金标准单验，唯一裁判）：
    对每个密度 ρ 取库子集，对每个目标用模板战术逐候选**单验**（LeanVerifier.verify，
    非 batch——batch 在上次实测中把 `exact 库片段名` 误判成功，有假阳性）。
    目标任一候选单验闭合即闭合 → P(ρ)。
    ⚠️ 诚实：库片段不作为引理注入（v1 候选=模板战术），因此本基线测的是"真实深缺口 +
    模板战术的自闭合率"，反映库密度**不真正参与**时的 P(ρ) 下界。库片段引理注入在 P1 做。
    """
    pts = []
    for i in range(0, n_points + 1):
        rho = i / n_points
        lib_slice = density_slice(library, rho, seed) if rho > 0 else []
        frag_names = [f['problem'] for f in lib_slice]
        closed = 0
        for t in targets:
            stmt = t['theorem_statement']
            if not stmt:
                continue
            closed_this = False
            for proof in build_proof_candidates(frag_names):
                r = verifier.verify(stmt, proof, import_line='import Mathlib.Tactic')
                if r.success:
                    closed_this = True
                    break
            if closed_this:
                closed += 1
        p = closed / max(1, len(targets))
        pts.append({'rho': round(rho, 2), 'size': len(lib_slice), 'P': round(p, 4),
                    'closed': closed, 'n': len(targets)})
    return pts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--library', default='stage1_library.jsonl')
    ap.add_argument('--targets', default='stage1_targets_samedomain.jsonl')
    ap.add_argument('--n-points', type=int, default=10)
    ap.add_argument('--max-targets', type=int, default=12)
    ap.add_argument('--out', default='report_stage1_real_baseline.json')
    ap.add_argument('--no-lean', action='store_true')
    args = ap.parse_args()

    library = load_jsonl(args.library)
    targets = load_jsonl(args.targets)[:args.max_targets]
    print(f"真实库片段: {len(library)} | 真实目标(深缺口样本): {len(targets)}")

    verifier = LeanVerifier(timeout=420) if (not args.no_lean and HAVE_LEAN) else None
    pts = run_real_baseline(library, targets, args.n_points, verifier)

    # 上界: 若 verifier 无(no-lean), 只输出库密度信息
    print("=" * 66)
    print("P0 真实基线：具体事实库 → 真实深缺口目标（真实 Lean 闭合率）")
    print("=" * 66)
    print(f'  {"ρ":>5} {"库size":>7} {"closed":>7} {"P(ρ)":>8}')
    for p in pts:
        print(f'  {p["rho"]:>5} {p["size"]:>7} {p.get("closed","-"):>7} {p.get("P","-"):>8}')
    print("  注: v1 候选为模板战术(不含库片段引理注入), 反映真实深缺口在机械锤下的闭合率")

    rep = {'library': len(library), 'targets': len(targets), 'points': pts,
           'method': '真实库片段(具体事实)密度子集 + 真实深缺口目标; 模板战术 batch_verify_many 判闭合',
           'note': '诚实基线: 预期P≈低/平坦(Beta 概念闭包); 库片段引理注入在P1(泛化骨架)做'}
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=2)
    print(f"  写入 {args.out}")


if __name__ == '__main__':
    main()
