"""Run from the project root using .venv/Scripts/python.exe <this file>."""
from pathlib import Path
import argparse
import json
import sys

if __package__ in (None,""):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from trusstwin.pipeline import run_case, demo_case


def main(argv=None):
    parser = argparse.ArgumentParser(description="Finite-thickness angle/truss engineering prototype; not a code-compliance certificate")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--demo",action="store_true")
    source.add_argument("--case",type=Path)
    parser.add_argument("--out",type=Path,default=Path(__file__).parent/"output")
    parser.add_argument("--with-thickness",action="store_true",help="add the known 10 mm synthetic thickness reading to the demo")
    args = parser.parse_args(argv)
    try:
        case = demo_case(args.with_thickness) if args.demo else json.loads(args.case.read_text(encoding="utf-8-sig"))
        result = run_case(case,args.out)
    except (ValueError,KeyError,TypeError,json.JSONDecodeError) as exc:
        print(json.dumps({"error":str(exc)},ensure_ascii=False),file=sys.stderr)
        return 2
    print(json.dumps({"result":str(args.out.resolve()/"result.json"),"solver":result["solver"]["status"],
                      "members":[{"id":m["id"],"status":m["status"],"posterior":m["posterior"]} for m in result["members"]]},ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
