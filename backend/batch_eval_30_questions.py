"""
批量评测脚本：
1) 使用现有链路生成三模型回答（Qwen / DeepSeek / Kimi）
2) 生成基线回答：仅把用户问题传给 DeepSeek（无个性化系统提示）
3) 使用项目既有 score_ai_response 评分标准统一打分
4) 导出详细记录和汇总

运行示例：
python batch_eval_30_questions.py
python batch_eval_30_questions.py --output-dir eval_results --identity 普通学生 --age-group 20-25岁 --major 计算机科学
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime
from typing import Any, Dict, List

from main import (
    DEEPSEEK_MODEL_ID,
    assess_question_risk,
    deepseek_client,
    dynamic_semantic_completion,
    enhance_user_portrait,
    generate_responses_dual_models,
    nlp_pre_processing,
    rag_review_reply,
    score_ai_response,
)

DEFAULT_QUESTIONS: List[str] = [
    "为什么说青年一代有理想、有本领、有担当，国家就有前途，民族就有希望？",
    "大学生应该如何理解并践行社会主义核心价值观？",
    "在网络信息复杂的时代，如何坚定政治立场而不被带节奏？",
    "学习马克思主义基本原理对我们现实生活有什么具体帮助？",
    "为什么要把个人理想融入国家和民族事业中？",
    "如何看待当代青年中的躺平心态？",
    "思政课为什么不能只讲知识点，还要重视价值引导？",
    "面对就业压力，青年应如何保持积极心态和社会责任感？",
    "怎样理解中国式现代化对青年的新要求？",
    "在人工智能快速发展的背景下，青年如何做到科技向善？",
    "为什么说爱国主义是中华民族精神的核心？",
    "大学生参与志愿服务对人格成长有哪些价值？",
    "面对历史虚无主义言论，青年应如何理性辨析？",
    "如何理解法治思维在大学生日常行为中的意义？",
    "新时代青年怎样在乡村振兴中找到自己的位置？",
    "思政教育如何帮助解决大学生的焦虑与迷茫？",
    "如何把红色文化转化为当代青年的行动动力？",
    "为什么要重视国家安全教育，普通学生能做什么？",
    "在社交媒体上表达观点时，如何做到理性、负责、文明？",
    "大学生如何平衡个人发展与集体利益？",
    "为什么说劳动教育是立德树人的重要环节？",
    "如何理解文化自信，并把它落实到日常学习生活中？",
    "面对同辈比较焦虑，青年应如何建立健康的成长坐标？",
    "为什么要坚持问题导向来学习党的创新理论？",
    "大学生如何在专业学习中体现家国情怀？",
    "如何看待短视频时代下的价值观塑造问题？",
    "新时代青年如何理解并践行责任担当？",
    "为什么要把道德修养与法治素养结合起来？",
    "高校思政教育怎样更好回应学生的真实需求？",
    "如果学习动力不足，怎样用思政视角重建目标感和行动力？",
]

SCORE_DIMENSIONS: List[str] = [
    "理论贯彻度",
    "主流意识形态弘扬",
    "政治立场引导",
    "社会主义核心价值观传播",
    "品德与人格塑造",
    "理想信念培育",
    "社会发展适配",
    "热点融入度",
    "学生需求契合",
    "个性与专业适配",
    "成长增量体现",
]


def ensure_dir(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def empty_dimension_scores() -> Dict[str, int]:
    return {k: 0 for k in SCORE_DIMENSIONS}


def normalize_dimension_scores(data: Any) -> Dict[str, int]:
    if not isinstance(data, dict):
        return empty_dimension_scores()
    output: Dict[str, int] = {}
    for key in SCORE_DIMENSIONS:
        value = data.get(key, 0)
        try:
            score = int(float(value))
        except Exception:
            score = 0
        output[key] = max(0, min(10, score))
    return output


def deepseek_question_only_reply(user_text: str) -> str:
    """基线：只把用户问题传给 DeepSeek，不附带个性化系统提示。"""
    response = deepseek_client.chat.completions.create(
        model=DEEPSEEK_MODEL_ID,
        messages=[
            {"role": "user", "content": user_text},
        ],
        temperature=0.7,
        max_tokens=2048,
        stream=False,
    )
    return (response.choices[0].message.content or "").strip()


def build_portrait_for_question(
    user_text: str,
    identity: str,
    age_group: str,
) -> Dict[str, Any]:
    explicit_data = nlp_pre_processing(user_text)
    rule_based_needs = dynamic_semantic_completion(user_text)
    historical_context = {
        "historical_tags": [],
        "historical_hidden_needs": [],
        "rule_based_needs": rule_based_needs,
    }

    portrait_data = enhance_user_portrait(
        user_text=user_text,
        user_identity=identity,
        user_age_group=age_group,
        historical_context=historical_context,
        explicit_data=explicit_data,
    )
    risk_assessment = assess_question_risk(user_text, explicit_data)
    return {
        "portrait_data": portrait_data,
        "explicit_data": explicit_data,
        "risk_assessment": risk_assessment,
    }


def evaluate_one_question(
    index: int,
    question: str,
    identity: str,
    age_group: str,
    major: str,
) -> Dict[str, Any]:
    print(f"\n[{index:02d}] 开始评测问题: {question}")

    context = build_portrait_for_question(question, identity, age_group)
    portrait_data = context["portrait_data"]
    explicit_data = context["explicit_data"]
    risk_assessment = context["risk_assessment"]

    # 1) 我们的三模型回答
    model_replies = generate_responses_dual_models(
        user_text=question,
        portrait_data=portrait_data,
        user_identity=identity,
        user_age_group=age_group,
        user_major=major,
        explicit_data=explicit_data,
        risk_assessment=risk_assessment,
    )

    # 2) 基线回答：只传用户问题给 DeepSeek
    baseline_reply = ""
    baseline_error = ""
    try:
        baseline_reply = deepseek_question_only_reply(question)
    except Exception as e:
        baseline_error = str(e)

    candidates = {
        "qwen": model_replies.get("qwen", ""),
        "deepseek": model_replies.get("deepseek", ""),
        "kimi": model_replies.get("kimi", ""),
        "deepseek_question_only": baseline_reply,
    }

    scores: Dict[str, Dict[str, Any]] = {}

    for model_name, reply_text in candidates.items():
        if not reply_text:
            reason = baseline_error if model_name == "deepseek_question_only" else "模型未生成回答"
            scores[model_name] = {
                "score": 0,
                "feedback": reason,
                "dimension_scores": empty_dimension_scores(),
            }
            continue

        try:
            rag_info = rag_review_reply(reply_text=reply_text, user_text=question)
        except Exception as e:
            rag_info = {"available": False, "reason": str(e)}

        try:
            result = score_ai_response(
                user_text=question,
                reply_text=reply_text,
                portrait_data=portrait_data,
                rag_info=rag_info,
            )
            scores[model_name] = {
                "score": int(result.get("score", 0)),
                "feedback": str(result.get("feedback", "")),
                "dimension_scores": normalize_dimension_scores(result.get("dimension_scores", {})),
            }
        except Exception as e:
            scores[model_name] = {
                "score": 0,
                "feedback": f"评分失败: {str(e)}",
                "dimension_scores": empty_dimension_scores(),
            }

    print(
        "[{}] 完成 | Qwen={} DeepSeek={} Kimi={} DeepSeek(仅问题)={}".format(
            f"{index:02d}",
            scores["qwen"]["score"],
            scores["deepseek"]["score"],
            scores["kimi"]["score"],
            scores["deepseek_question_only"]["score"],
        )
    )
    for model_name in ["qwen", "deepseek", "kimi", "deepseek_question_only"]:
        print(f"  - {model_name} 子项分: {scores[model_name]['dimension_scores']}")

    return {
        "index": index,
        "question": question,
        "portrait": {
            "sentiment_score": portrait_data.get("sentiment_score"),
            "logic_score": portrait_data.get("logic_score"),
            "practice_ability": portrait_data.get("practice_ability"),
            "psychological_quality": portrait_data.get("psychological_quality"),
            "emotional_state": portrait_data.get("emotional_state"),
            "interest_themes": portrait_data.get("interest_themes", []),
            "hidden_needs": portrait_data.get("hidden_needs", []),
            "analysis_summary": portrait_data.get("analysis_summary", ""),
        },
        "risk_assessment": risk_assessment,
        "replies": candidates,
        "scores": scores,
    }


def summarize_results(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    model_names = ["qwen", "deepseek", "kimi", "deepseek_question_only"]
    summary: Dict[str, Any] = {"count": len(records), "models": {}}

    for model_name in model_names:
        score_list = [int(r["scores"][model_name]["score"]) for r in records]
        avg_score = round(sum(score_list) / len(score_list), 2) if score_list else 0
        summary["models"][model_name] = {
            "avg_score": avg_score,
            "min_score": min(score_list) if score_list else 0,
            "max_score": max(score_list) if score_list else 0,
            "scores": score_list,
        }

    return summary


def dump_outputs(output_dir: str, records: List[Dict[str, Any]], summary: Dict[str, Any]) -> Dict[str, str]:
    ensure_dir(output_dir)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    detail_json_path = os.path.join(output_dir, f"batch_eval_detail_{ts}.json")
    summary_json_path = os.path.join(output_dir, f"batch_eval_summary_{ts}.json")
    summary_csv_path = os.path.join(output_dir, f"batch_eval_summary_{ts}.csv")

    with open(detail_json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    with open(summary_csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        base_headers = ["index", "question", "qwen", "deepseek", "kimi", "deepseek_question_only"]
        detail_headers = []
        for model in ["qwen", "deepseek", "kimi", "deepseek_question_only"]:
            for dim in SCORE_DIMENSIONS:
                detail_headers.append(f"{model}_{dim}")
        writer.writerow(base_headers + detail_headers)
        for r in records:
            row = [
                r["index"],
                r["question"],
                r["scores"]["qwen"]["score"],
                r["scores"]["deepseek"]["score"],
                r["scores"]["kimi"]["score"],
                r["scores"]["deepseek_question_only"]["score"],
            ]
            for model in ["qwen", "deepseek", "kimi", "deepseek_question_only"]:
                dim_scores = normalize_dimension_scores(r["scores"][model].get("dimension_scores", {}))
                for dim in SCORE_DIMENSIONS:
                    row.append(dim_scores[dim])
            writer.writerow(row)

        writer.writerow([])
        writer.writerow(["model", "avg_score", "min_score", "max_score"])
        for model_name in ["qwen", "deepseek", "kimi", "deepseek_question_only"]:
            item = summary["models"][model_name]
            writer.writerow([model_name, item["avg_score"], item["min_score"], item["max_score"]])

    return {
        "detail_json": detail_json_path,
        "summary_json": summary_json_path,
        "summary_csv": summary_csv_path,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量评测30个思政问题并统一打分")
    parser.add_argument("--output-dir", default="eval_results", help="结果输出目录")
    parser.add_argument("--identity", default="普通学生", help="评测时使用的用户身份")
    parser.add_argument("--age-group", default="20-25岁", help="评测时使用的年龄段")
    parser.add_argument("--major", default="计算机科学", help="评测时使用的专业")
    parser.add_argument("--questions-file", default="", help="可选：自定义问题文件(JSON数组)")
    parser.add_argument("--max-questions", type=int, default=30, help="最多评测题数，默认30")
    return parser.parse_args()


def load_questions(args: argparse.Namespace) -> List[str]:
    questions = DEFAULT_QUESTIONS
    if args.questions_file:
        with open(args.questions_file, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        if not isinstance(loaded, list) or not all(isinstance(x, str) for x in loaded):
            raise ValueError("questions-file 必须是字符串数组 JSON")
        questions = loaded

    max_q = max(1, int(args.max_questions))
    return questions[:max_q]


def main() -> None:
    args = parse_args()
    questions = load_questions(args)

    if len(questions) < 30 and not args.questions_file:
        raise ValueError("默认题库应包含30题，请检查 DEFAULT_QUESTIONS")

    print("=" * 72)
    print("批量评测开始")
    print(f"题目数量: {len(questions)}")
    print(f"身份: {args.identity} | 年龄段: {args.age_group} | 专业: {args.major}")
    print("评分标准: 复用 main.py::score_ai_response")
    print("=" * 72)

    records: List[Dict[str, Any]] = []

    for i, question in enumerate(questions, start=1):
        try:
            record = evaluate_one_question(
                index=i,
                question=question,
                identity=args.identity,
                age_group=args.age_group,
                major=args.major,
            )
            records.append(record)
        except Exception as e:
            print(f"[{i:02d}] 评测失败: {str(e)}")
            records.append(
                {
                    "index": i,
                    "question": question,
                    "error": str(e),
                    "replies": {
                        "qwen": "",
                        "deepseek": "",
                        "kimi": "",
                        "deepseek_question_only": "",
                    },
                    "scores": {
                        "qwen": {"score": 0, "feedback": f"任务失败: {str(e)}", "dimension_scores": empty_dimension_scores()},
                        "deepseek": {"score": 0, "feedback": f"任务失败: {str(e)}", "dimension_scores": empty_dimension_scores()},
                        "kimi": {"score": 0, "feedback": f"任务失败: {str(e)}", "dimension_scores": empty_dimension_scores()},
                        "deepseek_question_only": {"score": 0, "feedback": f"任务失败: {str(e)}", "dimension_scores": empty_dimension_scores()},
                    },
                }
            )

    summary = summarize_results(records)
    output_paths = dump_outputs(args.output_dir, records, summary)

    print("\n" + "=" * 72)
    print("批量评测完成")
    print("平均分汇总:")
    for model_name in ["qwen", "deepseek", "kimi", "deepseek_question_only"]:
        m = summary["models"][model_name]
        print(f"- {model_name}: avg={m['avg_score']} min={m['min_score']} max={m['max_score']}")
    print("输出文件:")
    print(f"- 详细记录(JSON): {output_paths['detail_json']}")
    print(f"- 汇总(JSON): {output_paths['summary_json']}")
    print(f"- 汇总(CSV): {output_paths['summary_csv']}")
    print("=" * 72)


if __name__ == "__main__":
    main()
