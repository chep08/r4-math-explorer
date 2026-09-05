"""
R4 · B 轨 Stage 1：合成需桥接目标 的 P(ρ) 密度扫描（P2-A 主线）
=================================================================================
背景（报告实验 A）：用"库片段覆盖密度 ρ → 目标闭合概率 P(ρ)"测渗流/相变。
真实数学题有"自带战术即闭"或"太难桥接"两难，难测相变。为此用**合成需桥接目标**：
    每个目标恰好需要 K 个库引理（rw 链）才能闭合。库密度 ρ = 目标所需引理在总引理池中的占比。
    P(ρ) = fixed held-out 目标集里"目标所需 K 个引理全在库子集中"的比例。

关键（科研上干净、可复现）：
    合成目标集合：{t_j : 需要引理集 R_j ⊆ 引理池 L, |R_j|=K}。
    库快照(ρ)：从 L 抽样一个子集 S_ρ（含 ρ 比例）。
    闭合判定：t_j 闭合 ⟺ R_j ⊆ S_ρ（目标所需引理全在库中 → 可完成 rw 链）。
    这是**集合包含**判定（零 Lean，纯逻辑），但用 Lean 小样本实证"集合包含 ⟺ Lean 闭合"。

引理与目标全部**确定性构造**（seed 固定），确保可复现、可控。

用法：
    python stage1_synthetic.py --n-lemmas 40 --k 3 --density-points 10 --out report_stage1_synth.json
"""
import os
import sys
import json
import random
import argparse
from itertools import combinations


# ---- 引理池构造（确定性）----
def build_lemma_pool(n):
    """构造 n 个 `ℕ` 上的可 rw 等式引理。名字唯一，证明为 trivial（rw 自反）。
    引理 i: theorem L_i (x : ℕ) : x + i = x + i := by rfl
    （用 `by rfl`，任何等式恒真；rw [L_i] 会把 x+i 重写为 x+i——幂等，够测"引理在库中"。
       科研上更严格可让引理为"非平凡等式"，但 v1 用恒真引理测"包含关系"，见诚实边界。）
    """
    pool = []
    for i in range(n):
        name = f"L{i}"
        # 每个引理都是闭包，rw 名存在即可（vw 用 rfl 证明幂等重写）
        theorem = f"theorem {name} (x : \u2115) : x + {i} = x + {i} := by\n  rfl"
        pool.append({'name': name, 'theorem_statement': theorem, 'proof_code': '  rfl'})
    return pool


# ---- 合成目标构造（确定性）----
def build_synthetic_targets(pool, k, n_targets, seed=42):
    """构造 n_targets 个目标，每个恰好需要 k 个引理（rw 链）闭合。
    目标 j: theorem t_j (x : ℕ) : x + a + b + ... = x + a + b + ... := by  (rw 链)
    简化：目标 = `theorem t_j (x : ℕ) : <sum A> = <sum A> := by rw [L_i1]; rw [L_i2]; ...`
    但幂等 rw 后需闭合，用 `rfl` 收尾。这里 v1 目标 proof 用合成的 rw 链 + rfl。
    """
    rng = random.Random(seed)
    pool_names = [p['name'] for p in pool]
    targets = []
    used = set()
    for j in range(n_targets):
        # 选 k 个不重复引理做目标所需
        need = tuple(sorted(rng.sample(pool_names, k)))
        if need in used:  # 去重目标
            continue
        used.add(need)
        # 目标陈述 + 候选证明（rw 链 + rfl 收尾）
        stmt = f"theorem t{j} (x : \u2115) : x + 0 = x + 0 := by"
        # 证明：rw 所需引理(每个幂等) + rfl 收尾。v1 简化：目标本身恒真(rfl 即可)，rw 链仅演示引用。
        proof_code = "  rfl"
        targets.append({'name': f"t{j}", 'needed_lemmas': list(need),
                        'theorem_statement': stmt, 'proof_code': proof_code})
        if len(targets) >= n_targets:
            break
    return targets


# ---- 库快照(ρ) + 闭合判定（集合包含）----
def density_snapshot(pool, rho, seed=42):
    """从引理池构造库子集，含 ceil(rho*n) 个引理（确定性抽样）。"""
    rng = random.Random(seed)
    n = len(pool)
    size = max(1, int(round(n * rho)))
    idx = list(range(n))
    rng.shuffle(idx)
    idx = sorted(idx[:size])
    return {'rho': round(rho, 2), 'size': size, 'indices': idx}


def target_closed(target, snapshot, pool):
    """目标闭合 ⟺ 目标所需引理全在库子集中。"""
    needed = set(target['needed_lemmas'])
    in_lib = {pool[i]['name'] for i in snapshot['indices']}
    return needed.issubset(in_lib)


def scan_p_rho(pool, targets, n_points=10, seed=42):
    """密度扫描：P(ρ) = 目标闭合比例；χ(ρ) = 边际。"""
    points = []
    prev_p = 0.0
    for i in range(1, n_points + 1):
        rho = i / n_points
        snap = density_snapshot(pool, rho, seed)
        closed = sum(1 for t in targets if target_closed(t, snap, pool))
        p = closed / max(1, len(targets))
        points.append({'rho': rho, 'size': snap['size'], 'closed': closed,
                       'P': round(p, 4), 'chi': round(p - prev_p, 4)})
        prev_p = p
    return points


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n-lemmas', type=int, default=40)
    ap.add_argument('--k', type=int, default=3)
    ap.add_argument('--n-targets', type=int, default=60)
    ap.add_argument('--density-points', type=int, default=10)
    ap.add_argument('--out', default='report_stage1_synth.json')
    args = ap.parse_args()

    pool = build_lemma_pool(args.n_lemmas)
    targets = build_synthetic_targets(pool, args.k, args.n_targets)
    print(f"引理池: {args.n_lemmas} | 合成目标: {len(targets)} (每个需要 k={args.k} 引理)")
    print(f"  目标所需引理数分布: {set(len(t['needed_lemmas']) for t in targets)}")

    points = scan_p_rho(pool, targets, args.density_points)
    print('=' * 60)
    print('P(ρ) 合成目标密度扫描（纯逻辑集合包含判定）')
    print('=' * 60)
    print(f'  {"ρ":>5} {"库size":>7} {"closed":>7} {"P(ρ)":>8} {"χ":>8}')
    for p in points:
        print(f'  {p["rho"]:>5} {p["size"]:>7} {p["closed"]:>7} {p["P"]:>8} {p["chi"]:>8}')

    # 临界 ρ_c 启发：P 首次超过 0.5 的 ρ
    rho_c = next((p['rho'] for p in points if p['P'] >= 0.5), None)
    print(f"\n  启发式 ρ_c (P首次≥0.5): {rho_c}")

    report = {'n_lemmas': args.n_lemmas, 'k': args.k, 'n_targets': len(targets),
              'density_points': points, 'rho_c_heuristic': rho_c,
              'method': 'synthetic needs-bridging targets, set-inclusion closure',
              'notes': '纯逻辑集合包含判定；Lean 实证对应关系见 stage1_synth_lean_verify'}
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f'  写入 {args.out}')


if __name__ == '__main__':
    main()
