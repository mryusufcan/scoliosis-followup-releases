from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.model_acceptance import evaluate_model_candidate


parser = argparse.ArgumentParser(description="Yerel V2 ONNX model paketini çalıştırmadan denetler.")
parser.add_argument("package_dir", help="manifest.json, ONNX dosyası ve validation_report.json içeren klasör")
parser.add_argument("--json", action="store_true", dest="as_json", help="Sonucu JSON olarak yazdır")
parser.add_argument("--output", help="Kabul ön kontrolü sonucunu JSON dosyasına yaz")
args = parser.parse_args()

result = evaluate_model_candidate(args.package_dir)
payload = result.to_dict()
if args.output:
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
if args.as_json:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
else:
    print("SONUÇ: " + ("UZMAN İNCELEMELİ POC İÇİN HAZIR" if result.accepted_for_expert_review else "KABUL EDİLMEDİ"))
    print(result.summary)
    for finding in result.findings:
        print(f"- [{finding.severity}] {finding.code}: {finding.message}")
sys.exit(0 if result.accepted_for_expert_review else 2)
