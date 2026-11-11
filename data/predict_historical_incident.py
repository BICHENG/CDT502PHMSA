"""Apply the saved CDT502 historical-incident model; Python standard library only.

Download final_model.json to the same folder, or provide --model.
Example: python predict_historical_incident.py --component MAIN --material IRON 
         --diameter 12 --pressure 10
The output describes whole-incident outcomes in the study's reported-incident
population. It does not assign field protection measures or their intensity.
"""

import argparse
import json
import math
from pathlib import Path


def sigmoid(value):
    if value >= 0:
        return 1 / (1 + math.exp(-value))
    exp_value = math.exp(value)
    return exp_value / (1 + exp_value)


def predict(parameters, diameter, pressure):
    if not math.isfinite(diameter) or diameter <= 0:
        raise ValueError("名义管径须为有限正数，单位为英寸。")
    if not math.isfinite(pressure) or pressure < 0:
        raise ValueError("正常运行表压须为有限非负数，单位为 psig。")
    model = parameters["logistic"]
    logs = [math.log1p(diameter), math.log1p(pressure)]
    scaled = [(v - m) / s for v, m, s in zip(
        logs, model["train_scale_mean"], model["train_scale"])]
    eta = model["intercept"] + sum(
        v * c for v, c in zip(scaled, model["coefficient"][:2]))
    calibration = parameters["calibration"]
    score = sigmoid(calibration["intercept"] + calibration["slope"] * eta)
    return {
        "raw_score": sigmoid(eta),
        "calibrated_score": score,
        "threshold": parameters["threshold"],
        "classified_as_casualty_report": score >= parameters["threshold"],
    }


def main():
    parser = argparse.ArgumentParser(description="历史配气事故的整报告伤亡判别；材料和部件用于确认适用范围。")
    parser.add_argument("--model", type=Path, default=Path(__file__).with_name("final_model.json"))
    parser.add_argument("--component", required=True, choices=["MAIN", "MAIN_VALVE"])
    parser.add_argument("--material", required=True, choices=["IRON", "STEEL", "PLASTIC"])
    parser.add_argument("--diameter", type=float, required=True, help="名义管径，英寸")
    parser.add_argument("--pressure", type=float, required=True, help="正常运行表压，psig")
    args = parser.parse_args()
    parameters = json.loads(args.model.read_text(encoding="utf-8-sig"))
    try:
        result = predict(parameters, args.diameter, args.pressure)
    except ValueError as error:
        parser.error(str(error))
    result.update({
        "component": args.component,
        "material": args.material,
        "diameter_inches": args.diameter,
        "normal_pressure_psig": args.pressure,
        "meaning": "适用于研究范围内已报告事故的整起伤亡判别，供历史事故复核；现场人员保护遵循企业规程。",
    })
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
