"""Generate only the explicitly named synthetic calibrated-geometry fixture."""
from pathlib import Path
import json
import sys

if __package__ in (None,""):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from trusstwin.pipeline import geometry_demo_case, run_case

if __name__=="__main__":
    directory=Path(__file__).resolve().parents[2]/"data"
    directory.mkdir(parents=True,exist_ok=True)
    case=geometry_demo_case()
    (directory/"calibrated_geometry_case.json").write_text(json.dumps(case,ensure_ascii=False,indent=2),encoding="utf-8")
    result=run_case(case,directory/"calibrated_geometry_result")
    print(json.dumps({"fixture":str(directory/"calibrated_geometry_case.json"),"engineering_decision":result["engineering_decision"],
                      "candidates":[{"thickness_m":c["thickness_m"],"width_m":c["width_m"],"orientation_rad":c["orientation_rad"],
                                     "likelihood_probability":c["likelihood_probability"],"retained":c["retained"],"rank":c["fit"]["local_rank"]}
                                    for c in result["members"][0]["candidates"]]},ensure_ascii=False))
