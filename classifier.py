"""
Tự động classify lĩnh vực file xlsx/csv.

2 chế độ:
  1. Keyword heuristic  — nhanh, không cần API, dùng mặc định
  2. LLM-assisted       — dùng khi heuristic confidence thấp (cần ANTHROPIC_API_KEY)
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ─── Keyword map cho từng lĩnh vực ───────────────────────────────────────────
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "finance": [
        "gdp", "inflation", "revenue", "expenditure", "budget", "tax", "fiscal",
        "debt", "deficit", "interest rate", "exchange rate", "stock", "profit",
        "loss", "balance sheet", "investment", "fdi", "cpi", "trade balance",
        "tổng sản phẩm", "tăng trưởng kinh tế", "thu chi ngân sách",
        "lạm phát", "xuất nhập khẩu", "lãi suất", "tỷ giá", "nợ công",
        "thu ngân sách", "chỉ số giá tiêu dùng", "doanh thu", "lợi nhuận",
        "vốn đầu tư", "kim ngạch", "cán cân thương mại", "trái phiếu",
        "chứng khoán", "vnindex", "hnx", "bội chi", "oda",
        "dự trữ ngoại hối", "giải ngân", "cung tiền", "tín dụng",
        "nợ xấu", "giá vàng", "giá xăng", "thuế",
    ],
    "health": [
        "mortality", "morbidity", "disease", "hospital", "patient",
        "vaccination", "cancer", "diabetes", "hiv", "epidemic",
        "tử vong", "bệnh viện", "bệnh nhân", "tiêm chủng", "vacxin",
        "ung thư", "suy dinh dưỡng", "y tế", "dịch bệnh",
        "tỷ lệ mắc", "giường bệnh", "bác sĩ", "điều dưỡng",
        "bảo hiểm y tế", "sức khỏe", "tử vong mẹ", "sốt xuất huyết",
        "lao phổi", "hiv aids", "viêm gan", "tay chân miệng",
        "covid", "dinh dưỡng", "béo phì", "tiểu đường", "tăng huyết áp",
        "thương tích", "trạm y tế", "nhân lực y tế", "khám chữa bệnh",
    ],
    "education": [
        "student", "enrollment", "school", "university", "literacy",
        "dropout", "teacher", "exam", "scholarship",
        "học sinh", "sinh viên", "nhập học", "trường học",
        "đại học", "cao đẳng", "tỷ lệ bỏ học", "giáo viên",
        "điểm thi", "tốt nghiệp", "học bổng", "phổ cập giáo dục",
        "chi ngân sách giáo dục", "biết chữ", "thpt", "tiểu học",
        "mầm non", "lưu ban", "dạy nghề", "đào tạo nghề",
        "tuyển sinh", "điểm chuẩn", "lớp học", "phòng học",
    ],
    "environment": [
        "emission", "co2", "carbon", "climate", "pollution",
        "deforestation", "biodiversity", "renewable", "waste",
        "khí thải", "ô nhiễm", "môi trường", "biến đổi khí hậu",
        "diện tích rừng", "chất lượng không khí", "aqi", "pm2.5",
        "nước thải", "rác thải", "năng lượng tái tạo",
        "đa dạng sinh học", "lũ lụt", "hạn hán", "sạt lở",
        "xâm nhập mặn", "tài nguyên nước", "nhiệt độ", "lượng mưa",
        "san hô", "khu bảo tồn", "thiên tai", "bão",
    ],
    "demographics": [
        "population", "census", "migration", "urbanization",
        "household", "poverty", "employment", "unemployment",
        "dân số", "điều tra dân số", "di cư", "đô thị hóa",
        "hộ gia đình", "tỷ lệ nghèo", "việc làm", "thất nghiệp",
        "lực lượng lao động", "già hóa dân số", "mật độ dân số",
        "tỷ lệ sinh", "tuổi thọ", "tỷ số giới tính", "hộ khẩu",
        "xuất khẩu lao động", "kiều hối", "thu nhập bình quân",
        "hộ nghèo", "chuẩn nghèo", "lao động phi chính thức",
    ],
    "agriculture": [
        "crop", "harvest", "yield", "livestock", "fishery",
        "fertilizer", "irrigation", "agricultural",
        "lúa gạo", "sản lượng", "nông sản", "thủy sản",
        "chăn nuôi", "gia súc", "phân bón", "tưới tiêu",
        "cà phê", "cao su", "tôm", "cá tra", "rau quả",
        "diện tích canh tác", "an ninh lương thực", "gieo trồng",
        "năng suất", "hợp tác xã", "lâm sản", "gỗ khai thác",
        "thủy lợi", "gia cầm", "nông nghiệp",
    ],
    "transport": [
        "traffic", "accident", "vehicle", "aviation", "shipping",
        "freight", "railway", "port", "logistics",
        "tai nạn giao thông", "phương tiện", "hàng không",
        "cảng biển", "đường sắt", "vận tải", "hàng hóa",
        "hành khách", "hạ tầng giao thông", "xe máy", "ô tô",
        "container", "đường cao tốc", "quốc lộ",
        "đăng kiểm", "xe buýt", "tàu hỏa", "sân bay",
    ],
    "energy": [
        "electricity", "power", "oil", "gas", "coal",
        "renewable energy", "kwh", "megawatt",
        "điện năng", "tiêu thụ điện", "sản lượng điện",
        "dầu khí", "than đá", "năng lượng mặt trời",
        "điện gió", "evn", "giá điện", "công suất lắp đặt",
        "thủy điện", "nhiệt điện", "điện áp mái",
        "petrovietnam", "vinacomin", "lọc dầu",
        "phát điện", "truyền tải điện",
    ],
    "technology": [
        "internet", "broadband", "digital", "ict", "patent",
        "innovation", "e-commerce", "startup",
        "người dùng internet", "thuê bao di động", "thương mại điện tử",
        "chuyển đổi số", "công nghệ thông tin", "khởi nghiệp",
        "băng thông rộng", "an toàn thông tin", "chỉ số ict",
        "fintech", "ví điện tử", "thanh toán số",
        "shopee", "lazada", "tiki", "momo", "zalopay",
        "4g", "5g", "phần mềm", "outsourcing", "fpt", "viettel",
    ],
    "social": [
        "crime", "inequality", "gini", "welfare",
        "social security", "corruption",
        "tội phạm", "bất bình đẳng", "an sinh xã hội",
        "bảo trợ xã hội", "hộ nghèo", "cận nghèo",
        "bình đẳng giới", "dân tộc thiểu số", "hdi",
        "phúc lợi", "trẻ em", "người cao tuổi",
        "bảo hiểm xã hội", "lương hưu", "ma túy",
        "bạo lực gia đình", "người khuyết tật",
        "văn hóa thể thao", "di sản",
    ],
    "business": [
        "enterprise", "business registration", "industrial output",
        "retail sales", "trade volume",
        "doanh nghiệp", "thành lập", "giải thể", "phá sản",
        "kim ngạch", "xuất khẩu", "nhập khẩu",
        "chỉ số iip", "sản xuất công nghiệp",
        "bán lẻ", "đăng ký kinh doanh", "sme",
        "khu công nghiệp", "khu chế xuất",
        "dệt may", "da giày", "linh kiện điện tử",
        "du lịch khách sạn", "doanh thu dịch vụ",
        "cổ phần hóa", "doanh nghiệp nhà nước",
    ],
    "land_urban": [
        "land use", "real estate", "housing market", "urban planning",
        "đất đai", "sử dụng đất", "quy hoạch đất",
        "bất động sản", "nhà ở", "chung cư", "căn hộ",
        "giá đất", "thu hồi đất", "giải phóng mặt bằng",
        "sổ đỏ", "sổ hồng", "cấp giấy chứng nhận",
        "đô thị", "quy hoạch đô thị", "hạ tầng kỹ thuật",
        "thoát nước", "cây xanh đô thị",
        "nhà ở xã hội", "nhà ở công nhân",
    ],
    "public_admin": [
        "public administration", "governance", "competitiveness",
        "cải cách hành chính", "dịch vụ công",
        "pci", "năng lực cạnh tranh tỉnh", "papi",
        "biên chế công chức", "thủ tục hành chính",
        "ngân sách tỉnh", "thu chi địa phương",
        "tòa án", "xét xử", "thi hành án",
        "đảng viên", "hội đồng nhân dân",
        "bầu cử", "kiểm tra thanh tra",
    ],
}


@dataclass
class ClassificationResult:
    topic: str
    confidence: float          # 0.0 – 1.0
    all_scores: dict[str, float] = field(default_factory=dict)
    method: str = "keyword"    # "keyword" | "llm"
    rationale: str = ""


def classify_heuristic(
    columns: list[str],
    sample_values: dict[str, list],
    filename: str = "",
    existing_topic: str = "",
) -> ClassificationResult:
    """
    Classify dựa trên tên cột, giá trị mẫu, và tên file.
    Trả về ClassificationResult với topic và confidence.
    """
    # Gộp tất cả text để match keyword
    text_parts = [filename.lower()]
    for col in columns:
        text_parts.append(col.lower())
    for vals in sample_values.values():
        text_parts.extend([str(v).lower() for v in vals])
    combined = " ".join(text_parts)

    scores: dict[str, float] = {}
    for topic, keywords in TOPIC_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in combined)
        scores[topic] = hits / len(keywords)  # normalize

    # Boost nếu existing_topic từ query đã khớp
    if existing_topic and existing_topic in scores:
        scores[existing_topic] *= 1.4

    best_topic = max(scores, key=scores.get)
    best_score = scores[best_topic]

    # Normalize confidence to 0-1 với cap hợp lý
    confidence = min(best_score * 8, 1.0)  # ~12.5% keywords hit = confidence 1.0

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
    Dùng Claude API để classify khi heuristic confidence thấp.
    Cần ANTHROPIC_API_KEY trong env.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY không có, fallback về heuristic")
        return classify_heuristic(columns, sample_values, filename)

    try:
        import httpx

        sample_preview = {
            col: vals[:2] for col, vals in list(sample_values.items())[:8]
        }
        prompt = f"""Phân tích file dữ liệu sau và xác định lĩnh vực chính:

Tên file: {filename}
Các cột: {', '.join(columns[:20])}
Dữ liệu mẫu: {json.dumps(sample_preview, ensure_ascii=False)[:800]}

Trả về JSON (chỉ JSON, không thêm gì):
{{
  "topic": "<một trong: finance|health|education|environment|demographics|agriculture|transport|energy|technology|social|misc>",
  "confidence": <0.0-1.0>,
  "rationale": "<1 câu giải thích>"
}}"""

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 200,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            resp.raise_for_status()
            content = resp.json()["content"][0]["text"]
            parsed = json.loads(content)

        return ClassificationResult(
            topic=parsed.get("topic", "misc"),
            confidence=float(parsed.get("confidence", 0.5)),
            method="llm",
            rationale=parsed.get("rationale", ""),
        )

    except Exception as e:
        logger.warning(f"LLM classify failed: {e}, fallback heuristic")
        return classify_heuristic(columns, sample_values, filename)


async def classify_file(
    meta,  # FileMetadata
    use_llm_threshold: float = 0.2,
) -> ClassificationResult:
    """
    Classify 1 file. Nếu heuristic confidence < threshold thì dùng LLM.

    Args:
        meta: FileMetadata từ validator
        use_llm_threshold: confidence tối thiểu để dùng heuristic;
                           thấp hơn → gọi LLM
    """
    result = classify_heuristic(
        columns=meta.columns,
        sample_values=meta.sample_values,
        filename=meta.filepath.name,
    )

    if result.confidence < use_llm_threshold and os.getenv("ANTHROPIC_API_KEY"):
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