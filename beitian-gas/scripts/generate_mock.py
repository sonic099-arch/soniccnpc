"""在项目根目录运行：python scripts/generate_mock.py --count 600 --days 14 --output work/mock600 [--load]。"""
import argparse
import json
from pathlib import Path
from app.data_sources.mock import MockDataSource, DISCLAIMER
from app.services.demo import workbook_bytes, template_bytes, dataset_manifest, load_dataset


def main():
    parser = argparse.ArgumentParser(description=DISCLAIMER)
    parser.add_argument("--count",type=int,default=600)
    parser.add_argument("--days",type=int,default=14)
    parser.add_argument("--seed",type=int,default=20261021)
    parser.add_argument("--output",type=Path,default=Path("work/mock600"))
    parser.add_argument("--load",action="store_true",help="显式写入DATABASE_URL或.env指定的开发数据库")
    args=parser.parse_args()
    source=MockDataSource(args.count,args.days,args.seed)
    dataset=source.generate()
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"standard-template.xlsx").write_bytes(template_bytes())
    (args.output/"example.xlsx").write_bytes(template_bytes(True))
    (args.output/"mock-data.xlsx").write_bytes(workbook_bytes(dataset))
    (args.output/"manifest.json").write_text(json.dumps(dataset_manifest(dataset),ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf8")
    result={"wells":len(dataset.wells),"measurements":len(dataset.measurements),"seed":args.seed,"warning":DISCLAIMER,"output":str(args.output)}
    if args.load:
        from sqlalchemy.orm import Session
        from app.core.database import get_engine
        with Session(get_engine()) as session:
            result["database"]=load_dataset(session,dataset)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__": main()
