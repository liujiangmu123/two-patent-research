import sys,json,time,importlib.util
sys.stdout.reconfigure(encoding="utf-8")
spec=importlib.util.spec_from_file_location("pd",r"H:/Axinjihua/02动画项目/05动画Harness工作台/专利文档资料/专利/刘智远专利/三项发明专利/00_共享/工具/patent_detail.py")
pd=importlib.util.module_from_spec(spec);spec.loader.exec_module(pd)
out={}
for n in ["CN120976438A","CN120976449B","CN117933030B","CN121053109A"]:
    try: out[n]=pd.fetch(n)
    except Exception as e: out[n]={"error":str(e)}
    print(n, str(out[n])[:1600]); time.sleep(6)
json.dump(out,open("detail_round3.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
