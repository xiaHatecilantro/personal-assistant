"""离线评测命令入口；仅使用 Fake Model，不读取或调用真实模型 API Key。"""

import argparse
import asyncio
from dataclasses import asdict, is_dataclass
import hashlib
import json
from pathlib import Path
import sys

from evals import runner
from evals.metrics import build_report


def main(argv=None):
    parser = argparse.ArgumentParser(description="运行 M9 固定场景及独立安全门禁")
    parser.add_argument("--cases", type=Path, default=Path(__file__).with_name("cases.json"))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        cases = runner.load_cases(args.cases)
        results = asyncio.run(runner.run_suite(cases, seed=args.seed))
        report = build_report(results)
        report.update(
            seed=args.seed,
            cases_sha256=hashlib.sha256(args.cases.read_bytes()).hexdigest(),
            results=[asdict(item) if is_dataclass(item) else dict(item) for item in results],
        )
        rendered = json.dumps(report, ensure_ascii=False, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
        return 0 if report["passed"] else 1
    except (OSError, ValueError, TypeError) as exc:
        print(f"评测无法执行：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
