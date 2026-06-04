"""
Query templates cho dữ liệu tài chính Việt Nam (xlsx/csv).

8 sub-categories:
  macro_economy, banking_credit, stock_market, corporate_finance,
  fiscal_budget, forex_rates, investment_fund, debt_bond

Chiến lược:
  - Keyword thuần Tiếng Việt → target nguồn VN và quốc tế
  - Trusted finance domains → site:-filtered queries cho nguồn tin cậy
"""

# ─── Trusted finance domains ──────────────────────────────────────────────────
TRUSTED_FINANCE_DOMAINS = [
    "data.worldbank.org",
    "imf.org",
    "afi.org",
    "ssi.com.vn",
    "vndirect.com.vn",
    "cafef.vn",
    "finance.vietstock.vn",
    "sbv.gov.vn",
    "mof.gov.vn",
    "gso.gov.vn",
    "cophieu68.vn",
    "investing.com",
    "fiingroup.vn",
]

# ─── Finance sub-categories ───────────────────────────────────────────────────
TOPICS: dict[str, dict[str, list[str]]] = {

    "macro_economy": {
        "vi": [
            "gdp", "tăng trưởng kinh tế", "lạm phát", "cpi",
            "tổng sản phẩm quốc nội", "cán cân vãng lai",
            "cán cân thương mại", "xuất nhập khẩu",
            "tài khoản vốn", "chỉ số kinh tế vĩ mô",
        ],
    },

    "banking_credit": {
        "vi": [
            "tín dụng", "lãi suất", "ngân hàng", "nhnn",
            "ngân hàng nhà nước", "nợ xấu", "room tín dụng",
            "huy động vốn", "cho vay", "tỷ lệ nợ",
            "bảo hiểm tiền gửi", "thanh khoản ngân hàng",
        ],
    },

    "stock_market": {
        "vi": [
            "vnindex", "hnx", "upcom", "cổ phiếu", "chứng khoán",
            "khối lượng giao dịch", "vốn hóa thị trường",
            "p/e ratio", "ipo", "niêm yết",
            "nhà đầu tư nước ngoài", "room ngoại",
        ],
    },

    "corporate_finance": {
        "vi": [
            "doanh thu", "lợi nhuận", "ebitda", "báo cáo tài chính",
            "bảng cân đối kế toán", "dòng tiền", "vốn chủ sở hữu",
            "roe", "roa", "tỷ suất lợi nhuận", "kết quả kinh doanh",
        ],
    },

    "fiscal_budget": {
        "vi": [
            "ngân sách nhà nước", "thu ngân sách", "chi ngân sách",
            "bội chi", "thuế gtgt", "thuế tndn",
            "thuế thu nhập", "nợ công",
            "trái phiếu chính phủ", "bộ tài chính",
        ],
    },

    "forex_rates": {
        "vi": [
            "tỷ giá", "usd vnd", "eur vnd", "dự trữ ngoại hối",
            "can thiệp tỷ giá", "ngoại tệ", "swift",
            "thanh toán quốc tế", "nhnn tỷ giá",
        ],
    },

    "investment_fund": {
        "vi": [
            "quỹ đầu tư", "etf", "fdi", "vốn đầu tư nước ngoài",
            "vốn oda", "quỹ mở", "chứng chỉ quỹ",
            "danh mục đầu tư", "tài sản ròng", "nav",
        ],
    },

    "debt_bond": {
        "vi": [
            "trái phiếu doanh nghiệp", "trái phiếu chính phủ",
            "lợi suất trái phiếu", "phát hành trái phiếu",
            "thị trường nợ", "kỳ hạn", "coupon",
            "yield curve",
        ],
    },
}


def build_queries(
    topics: list[str] | None = None,
    filetypes: list[str] | None = None,
    domains: list[str] | None = None,
    lang: str = "vi",
    max_per_topic: int = 1000,
    trusted_domain_kw_limit: int = 1,
) -> list[dict]:
    """
    Sinh danh sách query dict cho từng finance sub-category.

    Mỗi sub-category tạo ra 2 loại query:
      1. Generic: filetype + keyword (không site filter)
      2. Trusted domain: filetype + keyword + site:<domain>
         (chỉ dùng tối đa `trusted_domain_kw_limit` keyword đầu tiên)

    Args:
        topics:                topic keys (None = tất cả)
        filetypes:             ["filetype:xlsx", ...] (None = xlsx + csv)
        domains:               bỏ qua (kept for API compat)
        lang:                  "vi" | "both" — hiện tại chỉ "vi" có keywords
        max_per_topic:         số keyword tối đa mỗi topic (generic queries)
        trusted_domain_kw_limit: số keyword dùng để generate trusted-domain queries

    Returns:
        list of {
          "query": str, "topic": str, "filetype": str,
          "domain_group": str, "lang": str
        }
    """
    selected_topics = {
        k: v for k, v in TOPICS.items()
        if topics is None or k in topics
    }
    selected_ft = filetypes or ["filetype:xlsx", "filetype:csv"]

    queries: list[dict] = []

    for topic_name, kw_dict in selected_topics.items():
        vi_kws = kw_dict.get("vi", [])

        for ft in selected_ft:
            ft_ext = ft.split(":")[1]

            # ── Generic queries (no site filter) ─────────────────────────────
            for kw in vi_kws[:max_per_topic]:
                queries.append({
                    "query":        f"{ft} {kw}",
                    "topic":        topic_name,
                    "filetype":     ft_ext,
                    "domain_group": "generic_vi",
                    "lang":         "vi",
                })

    return queries


def get_quick_queries(n: int = 50, lang: str = "vi") -> list[dict]:
    """Lấy n query đa dạng để test nhanh. Mặc định ưu tiên tiếng Việt."""
    import random
    all_q = build_queries(
        filetypes=["filetype:xlsx", "filetype:csv"],
        lang=lang,
        max_per_topic=2,
        trusted_domain_kw_limit=1,
    )
    random.shuffle(all_q)
    return all_q[:n]


if __name__ == "__main__":
    import sys
    lang = sys.argv[1] if len(sys.argv) > 1 else "vi"
    qs = build_queries(max_per_topic=1, trusted_domain_kw_limit=1, lang=lang)
    print(f"Total queries [{lang}]: {len(qs)}")
    print()
    seen: set[str] = set()
    for q in qs:
        key = f"{q['topic']}_{q['domain_group']}"
        if key not in seen:
            print(f"  [{q['topic']}][{q['domain_group']}] {q['query']}")
            seen.add(key)
