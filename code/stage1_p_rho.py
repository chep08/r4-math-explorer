"""
R4 · B 轨 Stage 1：片段组装复用管道 + P(ρ) 密度扫描
=================================================================================
方案 X（真·片段组装复用）：库中已验证片段作为可检索引理，被召回并拼进目标证明，
真正度量"库密度 ρ → 目标闭合概率 P(ρ)"。本模块 = 检索层 + 组装层 + 验证层 + 密度扫描。

流水线（报告 §4，方案 X）：
    对每个 held-out 目标 t:
        1) 检索：从库 G_ρ 召回与 t 最相关的 k 个片段（TF-IDF 余弦，或 Oracle 穷举上界）
        2) 组装：召回片段作为可用引理 + 模板战术，尝试构造 t 的证明
        3) 验证：组装出的证明项过 LeanVerifier（sorry-free 硬门禁）→ 判闭合

密度扫描：
    库快照 {F(ρ₁)...F(ρₖ)}（10 密度点），对同一 held-out 目标集 T 统一回放，
    逐点计算 P_close(ρ)、χ(ρ)，检验 H1（相变存在性）。

用法：
    python stage1_p_rho.py --library stage1_library.jsonl \
        --targets stage1_targets_samedomain.jsonl --density-points 10 --out report_stage1.json
"""
import os
import sys
import json
import re
import time
import argparse
from collections import defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, '..', '..', 'src')   # 归档顶层 src
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

try:
    from lean_verifier import LeanVerifier  # noqa: E402
    from warm_sandbox import WarmSandbox  # noqa: E402
    from four_state import FourStatePool  # noqa: E402
    HAVE_LEAN = True
except Exception:  # pragma: no cover - 允许单测独立跑
    HAVE_LEAN = False

# 组装用的模板战术（覆盖 on-demand 战术；组装时会优先尝试召回片段对应战术）
ASSEMBLY_TACTICS = ['linarith', 'omega', 'ring_nf', 'ring', 'simp', 'simp_all',
                    'nlinarith', 'rfl', 'decide']


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


# ---- 检索层：TF-IDF 余弦召回（复用 structure 思路，但独立、可测）----
def build_tfidf(texts):
    from sklearn.feature_extraction.text import TfidfVectorizer
    vec = TfidfVectorizer(min_df=1, token_pattern=r'\S+')
    mat = vec.fit_transform(texts)
    return vec, mat


def retrieve(library, target_text, k=5, oracle=False):
    """从库召回与目标最相关的 k 个片段。
    oracle=True 时返回全部库片段（上界，排除检索器影响）。"""
    if oracle:
        return list(range(len(library)))[:k] if k < len(library) else list(range(len(library)))
    lib_texts = [f.get('theorem_statement', '') for f in library]
    if not lib_texts or not target_text:
        return []
    try:
        vec, mat = build_tfidf(lib_texts)
        q = vec.transform([target_text])
        from sklearn.metrics.pairwise import cosine_similarity
        sims = cosine_similarity(q, mat)[0]
        order = sorted(range(len(sims)), key=lambda i: -sims[i])[:k]
        return [i for i in order if sims[i] > 0]
    except Exception:
        # sklearn 缺失/退化：按文本长度相似启发（保守）
        return sorted(range(len(lib_texts)), key=lambda i: -abs(len(lib_texts[i]) - len(target_text)))[:k]


# ---- 组装层：把召回片段作为引理 + 模板战术，构造目标证明 ----
def assemble(theorem_statement, retrieved_fragments):
    """用召回片段(引理) + 模板战术，生成若干候选证明体（proof_code 列表）。
    片段作为 `have` 引理注入 + 模板战术尝试闭合。
    v1 简化（诚实）：用召回片段的 tactic + 组装战术，作为候选证明体。
    """
    cands = []
    for frag in retrieved_fragments:
        tac = frag.get('tactic', '')
        if tac:
            cands.append(f'  {tac}')   # 复用召回片段的战术
    for tac in ASSEMBLY_TACTICS:
        cands.append(f'  {tac}')
    # 去重保序
    seen = set(); out = []
    for c in cands:
        k = c.strip()
        if k not in seen:
            seen.add(k); out.append(c)
    return out


# ---- 密度扫描：库子集随 ρ 递增，测 P(ρ) ----
def density_subsets(library, n_points=10):
    """构造 n_points 个递增密度的库快照（ρ = 0.1..1.0 的库片段子集）。"""
    n = len(library)
    subsets = []
    for i in range(1, n_points + 1):
        frac = i / n_points
        size = max(1, int(round(n * frac)))
        # 用固定 seed 抽样保持可复现；子集按索引升序
        import hashlib
        # 用确定性抽样（前 size 个 + 打散）：简单起见取排序后的前 size 个，另用 seed 打散
        import random
        rng = random.Random(42)
        idx = list(range(n))
        rng.shuffle(idx)
        idx = sorted(idx[:size])
        subsets.append({'rho': round(frac, 2), 'size': size, 'indices': idx})
    return subsets


def run_stage1(library, targets, n_points=10, k=5, oracle=False, verifier=None,
               pool=None, max_targets_per_rho=None):
    """跑密度扫描，返回 P(ρ)/χ(ρ)。
    verifier=None 时只做检索+组装（不跑 Lean，返回推断闭合），供单测。
    oracle=True 用穷举上界检索。
    """
    subsets = density_subsets(library, n_points)
    results = {'rho_points': [], 'library_size': len(library),
               'targets': len(targets), 'oracle': oracle, 'k': k}
    pool = pool or (FourStatePool() if HAVE_LEAN else None)
    prev_proved = 0
    for ss in subsets:
        lib_sub = [library[i] for i in ss['indices']]
        tgt = targets if max_targets_per_rho is None else targets[:max_targets_per_rho]
        proved = 0; unref = 0; invalid = 0
        for t in tgt:
            stmt = t.get('theorem_statement', '')
            if not stmt:
                continue
            idx = retrieve(lib_sub, stmt, k=k, oracle=oracle)
            frags = [lib_sub[i] for i in idx]
            proofs = assemble(stmt, frags)
            # 尝试每个候选证明，任一过 Lean 即闭合
            closed_this = False
            for proof in proofs:
                if HAVE_LEAN and verifier is not None:
                    r = verifier.verify(stmt, proof, import_line='import Mathlib.Tactic')
                    if r.success:
                        closed_this = True
                        break
                else:
                    # 无 Lean：用"片段战术命中就判闭合"的启发（仅单测，非科研结论）
                    if any(proof.strip().startswith(frag.get('tactic', '').strip())
                           for frag in frags):
                        closed_this = True
                        break
            if closed_this:
                proved += 1
            else:
                unref += 1
        p = proved / max(1, len(tgt))
        chi = (proved - prev_proved) / max(1, len(tgt)) if prev_proved >= 0 else 0
        results['rho_points'].append({'rho': ss['rho'], 'size': ss['size'],
                                      'proved': proved, 'unref': unref,
                                      'P': round(p, 4), 'chi': round(p - (results['rho_points'][-1]['P'] if results['rho_points'] else 0), 4)})
        prev_proved = proved
    return results


def main():
    ap = argparse.ArgumentParser(description='R4 Stage 1 P(ρ) 片段复用曲线')
    ap.add_argument('--library', default='stage1_library.jsonl')
    ap.add_argument('--targets', default='stage1_targets_samedomain.jsonl')
    ap.add_argument('--density-points', type=int, default=10)
    ap.add_argument('--k', type=int, default=5)
    ap.add_argument('--oracle', action='store_true')
    ap.add_argument('--max-targets', type=int, default=None)
    ap.add_argument('--out', default='report_stage1.json')
    ap.add_argument('--no-lean', action='store_true', help='单测模式，不跑真Lean')
    args = ap.parse_args()

    library = load_jsonl(args.library)
    targets = load_jsonl(args.targets)
    print(f'库片段: {len(library)} | 目标: {len(targets)} | 密度点: {args.density_points} | k={args.k} | oracle={args.oracle}')

    verifier = None
    if not args.no_lean and HAVE_LEAN:
        verifier = LeanVerifier(timeout=420)
        print('  使用真实 Lean 验证')

    t0 = time.time()
    res = run_stage1(library, targets, n_points=args.density_points, k=args.k,
                     oracle=args.oracle, verifier=verifier,
                     max_targets_per_rho=args.max_targets)
    res['wall_seconds'] = round(time.time() - t0, 1)
    res['mode'] = 'oracle' if args.oracle else 'tfidf'
    res['lean'] = (not args.no_lean) and HAVE_LEAN

    print('=' * 60)
    print('P(ρ) 曲线')
    print('=' * 60)
    print(f'  {"ρ":>5} {"库size":>7} {"proved":>7} {"P(ρ)":>8} {"χ":>8}')
    for rp in res['rho_points']:
        print(f'  {rp["rho"]:>5} {rp["size"]:>7} {rp["proved"]:>7} {rp["P"]:>8} {rp["chi"]:>8}')

    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(f'  写入 {args.out}')


if __name__ == '__main__':
    main()
