"""
Tự động classify file xlsx/csv vào 8 finance sub-categories.

2 chế độ:
  1. Keyword heuristic  — nhanh, không cần API, dùng mặc định
  2. LLM-assisted       — dùng khi heuristic confidence thấp (cần DEEPSEEK_API_KEY)
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ─── Trusted finance domains (boost 1.4x) ────────────────────────────────────
TRUSTED_DOMAINS: set[str] = {
    "data.worldbank.org", "imf.org", "afi.org", "ssi.com.vn",
    "vndirect.com.vn", "cafef.vn", "finance.vietstock.vn",
    "sbv.gov.vn", "mof.gov.vn", "gso.gov.vn",
    "cophieu68.vn", "investing.com", "fiingroup.vn",
}

# ─── Keyword map cho 8 finance sub-categories ─────────────────────────────────
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "macro_economy": [
        "gdp", "tăng trưởng kinh tế", "lạm phát", "cpi",
        "tổng sản phẩm quốc nội", "cán cân vãng lai",
        "cán cân thương mại", "xuất nhập khẩu",
        "tài khoản vốn", "chỉ số kinh tế vĩ mô",
        "gross domestic product", "inflation", "trade balance",
        "current account", "economic growth",
    ],
    "banking_credit": [
        "tín dụng", "lãi suất", "ngân hàng", "nhnn",
        "ngân hàng nhà nước", "nợ xấu", "room tín dụng",
        "huy động vốn", "cho vay", "tỷ lệ nợ",
        "bảo hiểm tiền gửi", "thanh khoản ngân hàng",
        "credit", "interest rate", "bank", "non-performing loan",
        "deposit", "lending",
    ],
    "stock_market": [
        "vnindex", "hnx", "upcom", "cổ phiếu", "chứng khoán",
        "khối lượng giao dịch", "vốn hóa thị trường",
        "p/e ratio", "ipo", "niêm yết",
        "nhà đầu tư nước ngoài", "room ngoại",
        "stock", "equity", "market cap", "share price",
        "trading volume", "listed", "foreign investor",
    ],
    "corporate_finance": [
        "doanh thu", "lợi nhuận", "ebitda", "báo cáo tài chính",
        "bảng cân đối kế toán", "dòng tiền", "vốn chủ sở hữu",
        "roe", "roa", "tỷ suất lợi nhuận", "kết quả kinh doanh",
        "revenue", "profit", "balance sheet", "cash flow",
        "equity", "financial statement", "earnings",
    ],
    "fiscal_budget": [
        "ngân sách nhà nước", "thu ngân sách", "chi ngân sách",
        "bội chi", "thuế gtgt", "thuế tndn",
        "thuế thu nhập", "nợ công",
        "trái phiếu chính phủ", "bộ tài chính",
        "budget", "tax", "fiscal deficit", "public debt",
        "government revenue", "government expenditure",
    ],
    "forex_rates": [
        "tỷ giá", "usd vnd", "eur vnd", "dự trữ ngoại hối",
        "can thiệp tỷ giá", "ngoại tệ", "swift",
        "thanh toán quốc tế", "nhnn tỷ giá",
        "exchange rate", "foreign reserves", "forex",
        "currency", "usd", "vnd",
    ],
    "investment_fund": [
        "quỹ đầu tư", "etf", "fdi", "vốn đầu tư nước ngoài",
        "vốn oda", "quỹ mở", "chứng chỉ quỹ",
        "danh mục đầu tư", "tài sản ròng", "nav",
        "fund", "investment", "foreign direct investment",
        "portfolio", "net asset value",
    ],
    "debt_bond": [
        "trái phiếu doanh nghiệp", "trái phiếu chính phủ",
        "lợi suất trái phiếu", "phát hành trái phiếu",
        "thị trường nợ", "kỳ hạn", "coupon", "yield curve",
        "bond", "corporate bond", "government bond",
        "yield", "maturity", "debt market",
    ],
}

VALID_TOPICS = list(TOPIC_KEYWORDS.keys())


@dataclass
class ClassificationResult:
    topic: str
    confidence: float          # 0.0 – 1.0
    all_scores: dict[str, float] = field(default_factory=dict)
    method: str = "keyword"    # "keyword" | "llm"
    rationale: str = ""


def _is_trusted_domain(source_domain: str) -> bool:
    """Return True if source_domain matches any entry in TRUSTED_DOMAINS."""
    return any(td in source_domain for td in TRUSTED_DOMAINS)


def classify_heuristic(
    columns: list[str],
    sample_values: dict[str, list],
    filename: str = "",
    existing_topic: str = "",
    source_domain: str = "",
) -> ClassificationResult:
    """
    Classify dựa trên tên cột, giá trị mẫu, và tên file.

    Args:
        columns:        tên các cột trong file
        sample_values:  dict col → [val1, val2, ...]
        filename:       tên file
        existing_topic: topic hint từ query (tăng điểm nếu khớp)
        source_domain:  domain nguồn file (nếu là trusted domain → boost 1.4x)

    Returns:
        ClassificationResult với topic và confidence.
    """
    text_parts = [filename.lower()]
    for col in columns:
        text_parts.append(col.lower())
    for vals in sample_values.values():
        text_parts.extend([str(v).lower() for v in vals])
    combined = " ".join(text_parts)

    scores: dict[str, float] = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in combined)
        scores[topic] = hits / len(keywords)

    if existing_topic and existing_topic in scores:
        scores[existing_topic] *= 1.4

    best_topic = max(scores, key=scores.get)
    best_score = scores[best_topic]

    confidence = min(best_score * 8, 1.0)

    if _is_trusted_domain(source_domain):
        confidence = min(confidence * 1.4, 1.0)

    return ClassificationResult(
        topic=best_topic if confidence > 0.05 else "misc",
        confidence=confidence,
        all_scores=scores,
        method="keyword",
    )


async def classify_with_llm(
    columns: list[str],
    sample_values: dict[str, list],
    filename: str = "",
) -> ClassificationResult:
    """
    Dùng DeepSeek API để classify khi heuristic confidence thấp.
    Cần DEEPSEEK_API_KEY trong env.

    Returns:
        ClassificationResult với topic là một trong 8 sub-category names.
    """
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        logger.warning("DEEPSEEK_API_KEY không có, fallback về heuristic")
        return classify_heuristic(columns, sample_values, filename)

    try:
        import httpx

        sample_preview = {
            col: vals[:2] for col, vals in list(sample_values.items())[:8]
        }
        valid_topics_str = "|".join(VALID_TOPICS)
        prompt = f"""Phân tích file dữ liệu tài chính Việt Nam sau và xác định sub-category chính:

Tên file: {filename}
Các cột: {', '.join(columns[:20])}
Dữ liệu mẫu: {json.dumps(sample_preview, ensure_ascii=False)[:800]}

Trả về JSON (chỉ JSON, không thêm gì):
{{
  "topic": "<một trong: {valid_topics_str}>",
  "confidence": <0.0-1.0>,
  "rationale": "<1 câu giải thích>"
}}"""

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek-chat",
                    "max_tokens": 200,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)

        topic = parsed.get("topic", "misc")
        if topic not in VALID_TOPICS:
            topic = "misc"

        return ClassificationResult(
            topic=topic,
            confidence=float(parsed.get("confidence", 0.5)),
            method="llm",
            rationale=parsed.get("rationale", ""),
        )

    except Exception as e:
        logger.warning(f"LLM classify failed: {e}, fallback heuristic")
        return classify_heuristic(columns, sample_values, filename)


async def classify_file(
    meta,                          # FileMetadata
    use_llm_threshold: float = 0.2,
    source_domain: str = "",
) -> ClassificationResult:
    """
    Classify 1 file. Nếu heuristic confidence < threshold thì dùng LLM.

    Args:
        meta:               FileMetadata từ validator
        use_llm_threshold:  confidence tối thiểu để dùng heuristic;
                            thấp hơn → gọi LLM
        source_domain:      domain URL nguồn (trusted domain → boost confidence)
    """
    result = classify_heuristic(
        columns=meta.columns,
        sample_values=meta.sample_values,
        filename=meta.filepath.name,
        source_domain=source_domain,
    )

    if result.confidence < use_llm_threshold and os.getenv("DEEPSEEK_API_KEY"):
        logger.info(
            f"Heuristic confidence thấp ({result.confidence:.2f}), "
            f"dùng LLM cho {meta.filepath.name}"
        )
        result = await classify_with_llm(
            columns=meta.columns,
            sample_values=meta.sample_values,
            filename=meta.filepath.name,
        )

    return result
