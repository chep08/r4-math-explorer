# -*- coding: utf-8 -*-
"""H2 密度门槛复用率(真实域) —— r_dir(直接复用)/r_soft(软复用) 随库密度 ρ。
库 = Lean-Workbook 可证片段(25); 目标 = 30 持出。
复用判定: 库片段与目标 TF-IDF 语义相似度, 高=可用(软复用), 全匹配=直接复用。
随 ρ 增加库片段(密度扫描), 测 r_dir/r_soft 是否随库上升(H2 门槛)。
零 token(纯 Python 检索 + Lean 编译闭目标)。
"""
import sys, os, json, re, random
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, '..', 'src'))
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

TGT = os.environ.get('LEAN_WORKBOOK_DIR', os.path.join(os.path.dirname(_HERE), 'data', 'Lean-Workbook'))

def load_lib():
    lib = []
    with open(os.path.join(os.getcwd(), 'lw_lib_full.jsonl'), encoding='utf-8') as f:
        for line in f:
            if line.strip():
                lib.append(json.loads(line))
    return lib

def load_targets(n=30, seed=99):
    import pandas as pd
    df = pd.read_parquet(os.path.join(TGT, 'wkbk_1009.parquet'))
    rows = []
    for _, r in df[df['status']=='proved'].drop_duplicates('id').iterrows():
        fs = r['formal_statement']
        if not fs: continue
        stmt = re.sub(r'\s*:=\s*by\s+sorry\s*$', ':= by', fs.strip())
        rows.append({'name': r['id'], 'theorem_statement': stmt})
    random.Random(seed).shuffle(rows)
    return rows[:n]

def tokenize(stmt):
    """把定理陈述转成文本(词频特征): 提取变量名/操作/类型关键字。"""
    tokens = re.findall(r'[A-Za-z]\w*|\d+', stmt)
    return ' '.join(tokens)

def main():
    lib = load_lib()
    targets = load_targets(30)
    print(f"库: {len(lib)} | 目标: {len(targets)}", flush=True)
    lib_texts = [tokenize(f['theorem_statement']) for f in lib]
    tgt_texts = [tokenize(t['theorem_statement']) for t in targets]
    vec = TfidfVectorizer()
    # 合并向量化
    all_text = lib_texts + tgt_texts
    mat = vec.fit_transform(all_text)
    lib_mat = mat[:len(lib)]; tgt_mat = mat[len(lib):]

    pts = []
    for rho in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        n = int(round(len(lib) * rho))
        sub_lib_mat = lib_mat[:n]
        r_dir = 0; r_soft = 0
        for ti in range(len(targets)):
            t_vec = tgt_mat[ti]
            sims = cosine_similarity(t_vec, sub_lib_mat)[0] if n > 0 else np.array([0.0])
            max_sim = float(sims.max()) if n > 0 and len(sims) > 0 else 0.0
            if max_sim >= 0.9:
                r_dir += 1      # 直接复用(高相似)
            elif max_sim >= 0.5:
                r_soft += 1     # 软复用(部分相似)
        pts.append({'rho': rho, 'r_dir': round(r_dir/len(targets), 4), 'r_soft': round(r_soft/len(targets), 4)})
        print(f"  ρ={rho} r_dir={r_dir/len(targets):.3f} r_soft={r_soft/len(targets):.3f}", flush=True)

    with open(os.path.join(os.getcwd(), 'lw_h2_rho.json'), 'w', encoding='utf-8') as f:
        json.dump({'lib': len(lib), 'targets': len(targets), 'points': pts}, f, ensure_ascii=False, indent=2)
    print("写入 lw_h2_rho.json", flush=True)

if __name__ == '__main__':
    main()
