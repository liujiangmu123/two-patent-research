import fitz, sys, re
sys.stdout.reconfigure(encoding='utf-8')
p = r'h:\Axinjihua\02动画项目\05动画Harness工作台\专利文档资料\专利\刘智远专利\三项发明专利\专利A_角钢高斯泼溅与激光雷达联合反演\01_调研与查新\文献\T01_DLT409-2023_电力安全工作规程线路部分_报批稿.pdf'
doc = fitz.open(p)
print('pages', doc.page_count)
kw = sys.argv[1:] if len(sys.argv) > 1 else ['安全距离', '无人机', '表1', '表 1']
for i, pg in enumerate(doc):
    t = pg.get_text()
    hits = [k for k in kw if k in t]
    if hits:
        print('=== PDF page', i + 1, 'hits', hits)
