"""
Query templates để tìm file xlsx/csv đa lĩnh vực.
Hỗ trợ song ngữ Tiếng Việt + English — SearXNG xử lý Unicode tốt.

Chiến lược ngôn ngữ:
  - Tiếng Việt → target nguồn VN (gov.vn, edu.vn, các bộ ngành)
  - Tiếng Anh  → target nguồn quốc tế (worldbank, UN, gov, edu)
  - Kết hợp    → tìm file VN có header song ngữ (rất phổ biến)
"""

# ─── Operators hỗ trợ ────────────────────────────────────────────────────────
# filetype:xlsx / filetype:csv  → tìm file trực tiếp
# site:gov.vn / site:edu.vn     → nguồn chính phủ & giáo dục VN
# intitle: → tiêu đề trang chứa keyword
# ─────────────────────────────────────────────────────────────────────────────

DOMAINS = {
    # ── Việt Nam ──────────────────────────────────────────────────────────────
    "vn_government": [
        "site:gso.gov.vn",          # Tổng cục Thống kê
        "site:mof.gov.vn",          # Bộ Tài chính
        "site:moh.gov.vn",          # Bộ Y tế
        "site:moet.gov.vn",         # Bộ Giáo dục
        "site:mard.gov.vn",         # Bộ Nông nghiệp
        "site:monre.gov.vn",        # Bộ TN&MT
        "site:mot.gov.vn",          # Bộ Giao thông
        "site:mpi.gov.vn",          # Bộ Kế hoạch & Đầu tư
        "site:gov.vn",              # Cổng TTĐT Chính phủ
    ],
    "vn_academic": [
        "site:neu.edu.vn",          # ĐH Kinh tế Quốc dân
        "site:ueh.edu.vn",          # ĐH Kinh tế HCM
        "site:hust.edu.vn",         # Bách khoa HN
        "site:vnu.edu.vn",          # ĐHQG HN
        "site:vnuhcm.edu.vn",       # ĐHQG HCM
        "site:edu.vn",
    ],
    "vn_open_data": [
        "site:data.gov.vn",         # Cổng dữ liệu mở VN
        "site:opendata.vn",
        "site:thongke.vn",
        "site:customs.gov.vn",      # Tổng cục Hải quan
        "site:sbv.gov.vn",          # Ngân hàng Nhà nước
        "site:hnx.vn",              # HNX
        "site:hsx.vn",              # HOSE
    ],
    # ── Quốc tế ───────────────────────────────────────────────────────────────
    "international": [
        "site:worldbank.org",
        "site:imf.org",
        "site:who.int",
        "site:fao.org",
        "site:oecd.org",
        "site:un.org",
        "site:adb.org",             # Asian Development Bank
        "site:asean.org",
    ],
    "global_open_data": [
        "site:data.gov",
        "site:kaggle.com",
        "site:zenodo.org",
        "site:figshare.com",
        "site:data.europa.eu",
    ],
}

FILETYPES = ["filetype:xlsx", "filetype:csv", "filetype:xls"]

# ─── Keywords song ngữ theo lĩnh vực ─────────────────────────────────────────
# Cấu trúc mỗi topic: {"vi": [...], "en": [...]}
# "vi" → dùng với domain VN
# "en" → dùng với domain quốc tế
# ─────────────────────────────────────────────────────────────────────────────

TOPICS = {

    # ══════════════════════════════════════════════════════════════════════════
    "finance": {
        "vi": [
            # Kinh tế vĩ mô
            "số liệu GDP", "tăng trưởng kinh tế", "tổng sản phẩm quốc nội",
            "GNI thu nhập quốc gia", "tổng sản phẩm nội địa theo tỉnh",
            "lạm phát chỉ số giá", "chỉ số giá tiêu dùng CPI",
            "chỉ số giá sản xuất PPI", "chỉ số giá xuất khẩu nhập khẩu",
            # Ngân sách
            "thu chi ngân sách nhà nước", "thu ngân sách nhà nước",
            "chi thường xuyên ngân sách", "bội chi ngân sách",
            "nợ công nợ chính phủ", "trái phiếu chính phủ",
            "vốn ODA viện trợ không hoàn lại",
            # Đầu tư
            "vốn đầu tư toàn xã hội", "đầu tư FDI nước ngoài",
            "vốn đầu tư trực tiếp nước ngoài", "đầu tư công",
            "giải ngân vốn đầu tư", "vốn đăng ký FDI theo tỉnh",
            # Thương mại
            "xuất nhập khẩu hàng hóa", "cán cân thương mại",
            "kim ngạch xuất khẩu", "kim ngạch nhập khẩu",
            "cán cân thanh toán quốc tế", "dự trữ ngoại hối",
            "thặng dư thâm hụt thương mại",
            # Ngân hàng tài chính
            "lãi suất ngân hàng", "tỷ giá hối đoái",
            "tín dụng tăng trưởng", "cung tiền M2",
            "dư nợ tín dụng", "nợ xấu ngân hàng",
            "lợi nhuận ngân hàng thương mại",
            # Chứng khoán
            "VN-Index HNX-Index", "vốn hóa thị trường chứng khoán",
            "giá cổ phiếu niêm yết", "giao dịch chứng khoán",
            "phát hành trái phiếu doanh nghiệp",
            # Giá cả
            "giá vàng trong nước", "giá xăng dầu bán lẻ",
            "chỉ số giá bất động sản", "giá nhà đất",
        ],
        "en": [
            "GDP statistics Vietnam", "budget expenditure Vietnam",
            "trade balance Vietnam", "bank interest rates Vietnam",
            "foreign exchange reserves", "tax revenue Vietnam",
            "public debt Vietnam", "FDI inflow Vietnam", "CPI Vietnam",
            "Vietnam stock market data", "monetary policy Vietnam",
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    "health": {
        "vi": [
            # Tử vong & bệnh tật
            "tỷ lệ tử vong", "tử vong theo nguyên nhân",
            "tử vong mẹ và trẻ sơ sinh", "tử vong trẻ dưới 5 tuổi",
            "tuổi thọ trung bình", "gánh nặng bệnh tật",
            # Bệnh truyền nhiễm
            "số ca mắc bệnh truyền nhiễm", "dịch bệnh sốt xuất huyết",
            "lao phổi HIV AIDS", "sốt rét", "viêm gan",
            "covid-19 số ca nhiễm", "bệnh tay chân miệng",
            # Cơ sở y tế
            "thống kê bệnh viện cơ sở y tế", "số giường bệnh",
            "nhân lực y tế bác sĩ điều dưỡng",
            "số trạm y tế xã phường",
            # Tiêm chủng & dinh dưỡng
            "tiêm chủng vacxin trẻ em", "tỷ lệ tiêm chủng đầy đủ",
            "tỷ lệ suy dinh dưỡng trẻ em", "thừa cân béo phì",
            "tình trạng dinh dưỡng",
            # Tài chính y tế
            "chi tiêu y tế toàn quốc", "bảo hiểm y tế",
            "tỷ lệ bao phủ bảo hiểm y tế", "chi phí khám chữa bệnh",
            # Bệnh không lây
            "ung thư tỷ lệ mắc", "tiểu đường đái tháo đường",
            "tăng huyết áp", "bệnh tim mạch", "sức khỏe tâm thần",
            "tai nạn thương tích",
            # Sức khỏe sinh sản
            "tỷ lệ sinh", "sinh đẻ có hỗ trợ y tế",
            "kế hoạch hóa gia đình",
        ],
        "en": [
            "mortality rate Vietnam", "hospital statistics Vietnam",
            "vaccination coverage Vietnam", "health expenditure Vietnam",
            "disease burden Vietnam", "nutrition survey Vietnam",
            "maternal health Vietnam", "universal health coverage",
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    "education": {
        "vi": [
            # Quy mô hệ thống
            "số trường học mầm non tiểu học", "số trường THCS THPT",
            "số trường đại học cao đẳng", "số học sinh sinh viên",
            "tỷ lệ nhập học đúng tuổi", "tỷ lệ đi học chung",
            # Chất lượng
            "tỷ lệ bỏ học lưu ban", "tỷ lệ tốt nghiệp",
            "kết quả thi tốt nghiệp THPT", "điểm thi vào lớp 10",
            "kết quả thi THPT quốc gia", "điểm chuẩn đại học",
            "học sinh giỏi quốc gia quốc tế", "tỷ lệ biết chữ",
            # Giáo viên
            "số giáo viên giảng viên", "tỷ lệ giáo viên đạt chuẩn",
            "giáo viên trên học sinh", "đào tạo giáo viên",
            # Tài chính giáo dục
            "chi ngân sách cho giáo dục", "học phí các cấp",
            "học bổng sinh viên", "đầu tư giáo dục",
            # Nghề nghiệp & ĐH
            "đào tạo nghề dạy nghề", "lao động qua đào tạo",
            "sinh viên ra trường việc làm", "tuyển sinh đại học",
            "xếp hạng đại học Việt Nam",
            # Cơ sở vật chất
            "phòng học thiếu phòng học", "trường học vùng sâu vùng xa",
            "internet trường học", "thiết bị dạy học",
        ],
        "en": [
            "student enrollment Vietnam", "school performance Vietnam",
            "literacy rate Vietnam", "education expenditure Vietnam",
            "dropout rate Vietnam", "higher education Vietnam",
            "vocational training Vietnam",
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    "environment": {
        "vi": [
            # Khí hậu & khí thải
            "khí thải CO2 phát thải nhà kính", "phát thải khí nhà kính",
            "chỉ số AQI chất lượng không khí",
            "ô nhiễm không khí bụi PM2.5",
            "nhiệt độ trung bình năm", "lượng mưa",
            "biến đổi khí hậu kịch bản",
            # Rừng & đất
            "diện tích rừng che phủ rừng", "phá rừng suy thoái rừng",
            "trồng rừng phủ xanh", "sạt lở đất xói mòn",
            "sử dụng đất đai", "đất nông nghiệp lâm nghiệp",
            # Nước
            "chất lượng nước mặt nước ngầm",
            "ô nhiễm sông hồ biển", "nước sạch vệ sinh",
            "tài nguyên nước", "xâm nhập mặn",
            # Thiên tai
            "lũ lụt hạn hán thiệt hại", "bão lốc xoáy",
            "thiên tai thống kê thiệt hại",
            "ngập lụt đô thị",
            # Chất thải
            "rác thải sinh hoạt", "xử lý rác thải",
            "ô nhiễm đất", "chất thải công nghiệp",
            "chất thải nguy hại", "tái chế rác thải",
            # Đa dạng sinh học & biển
            "đa dạng sinh học", "động thực vật quý hiếm",
            "san hô biển Việt Nam", "khu bảo tồn thiên nhiên",
            # Năng lượng tái tạo
            "năng lượng tái tạo điện mặt trời",
            "điện gió trang trại gió", "năng lượng sinh khối",
        ],
        "en": [
            "CO2 emissions Vietnam", "air quality Vietnam",
            "deforestation Vietnam", "climate change Vietnam",
            "renewable energy Vietnam", "water quality Vietnam",
            "natural disaster statistics Vietnam",
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    "demographics": {
        "vi": [
            # Dân số tổng hợp
            "dân số Việt Nam theo tỉnh", "tổng điều tra dân số nhà ở",
            "mật độ dân số", "dân số đô thị nông thôn",
            "cơ cấu dân số theo tuổi giới tính",
            "tháp dân số", "già hóa dân số",
            # Sinh tử
            "tỷ lệ sinh thô", "tỷ lệ tử vong thô",
            "tỷ suất tử vong trẻ sơ sinh",
            "tổng tỷ suất sinh TFR",
            "tuổi thọ khi sinh", "tỷ số giới tính khi sinh",
            # Di cư lao động
            "di cư nội địa liên tỉnh", "xuất khẩu lao động",
            "lao động đi làm việc nước ngoài",
            "kiều hối chuyển tiền về nước",
            "nhập cư người nước ngoài",
            # Hộ gia đình
            "quy mô hộ gia đình", "số thành viên hộ",
            "hộ gia đình đơn thân", "nhân khẩu học hộ gia đình",
            # Đô thị hóa
            "đô thị hóa tỷ lệ đô thị", "dân số đô thị",
            "dân số thành phố lớn Hà Nội HCM",
            "khu đô thị mới phát triển",
            # Thu nhập & nghèo
            "thu nhập bình quân đầu người",
            "hộ nghèo cận nghèo theo tỉnh",
            "chuẩn nghèo đa chiều", "tỷ lệ nghèo",
            "chênh lệch thu nhập nông thôn đô thị",
            # Lao động
            "lực lượng lao động", "tỷ lệ tham gia lao động",
            "thất nghiệp theo quý năm",
            "lao động phi chính thức",
            "cơ cấu lao động theo ngành",
        ],
        "en": [
            "Vietnam population census", "birth death rate Vietnam",
            "labor migration Vietnam", "urbanization Vietnam",
            "household income Vietnam", "poverty rate Vietnam",
            "remittance Vietnam",
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    "agriculture": {
        "vi": [
            # Trồng trọt
            "sản lượng lúa gạo theo tỉnh", "diện tích gieo trồng lúa",
            "năng suất lúa", "sản lượng ngô khoai sắn",
            "rau củ quả sản lượng", "cây ăn trái",
            "cà phê sản lượng xuất khẩu", "cao su tiêu điều",
            "hồ tiêu chè sản lượng",
            # Chăn nuôi
            "đàn lợn trâu bò", "chăn nuôi gia cầm gà vịt",
            "sản lượng thịt trứng sữa",
            "dịch bệnh gia súc gia cầm",
            # Thủy sản
            "sản lượng thủy sản khai thác nuôi trồng",
            "xuất khẩu tôm cá tra",
            "nuôi trồng thủy sản diện tích",
            "nghề cá đánh bắt biển",
            # Đất đai & tưới tiêu
            "diện tích đất nông nghiệp",
            "đất canh tác đất lúa",
            "hệ thống tưới tiêu thủy lợi",
            # Vật tư
            "phân bón sử dụng tiêu thụ",
            "thuốc bảo vệ thực vật",
            "máy móc nông nghiệp cơ giới hóa",
            # Kinh tế nông nghiệp
            "giá nông sản thị trường",
            "xuất khẩu nông lâm thủy sản",
            "hợp tác xã nông nghiệp",
            "nông nghiệp hữu cơ công nghệ cao",
            "thu nhập nông hộ nông dân",
            # Lâm nghiệp
            "khai thác gỗ lâm sản",
            "trồng rừng sản xuất",
        ],
        "en": [
            "Vietnam rice production statistics", "agricultural export Vietnam",
            "fisheries production Vietnam", "livestock Vietnam",
            "food security Vietnam", "crop yield Vietnam",
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    "transport": {
        "vi": [
            # Tai nạn & an toàn
            "tai nạn giao thông số vụ chết người",
            "tai nạn đường bộ đường sắt",
            "vi phạm giao thông xử phạt",
            "điểm đen tai nạn giao thông",
            # Phương tiện
            "số xe máy ô tô đăng ký",
            "đăng kiểm phương tiện",
            "xe buýt xe khách vận tải hành khách",
            "xe tải xe container vận tải hàng hóa",
            # Đường bộ
            "chiều dài đường bộ quốc lộ tỉnh lộ",
            "đường cao tốc km hoàn thành",
            "cầu đường xây dựng hạ tầng",
            # Đường sắt
            "vận tải đường sắt hành khách hàng hóa",
            "đường sắt tốc độ cao dự án",
            "tàu hỏa thống kê",
            # Hàng không
            "hành khách hàng không sân bay",
            "thống kê sân bay nội địa quốc tế",
            "hàng hóa hàng không",
            "Vietnam Airlines Vietjet Bamboo",
            # Cảng biển & đường thủy
            "thông lượng cảng biển container",
            "vận tải đường thủy nội địa",
            "hàng hóa thông qua cảng biển",
            "đội tàu biển Việt Nam",
            # Logistics
            "chi phí logistics vận chuyển",
            "kho bãi logistics",
            "chỉ số năng lực logistics LPI",
        ],
        "en": [
            "traffic accident statistics Vietnam",
            "vehicle registration Vietnam",
            "air passenger Vietnam", "seaport throughput Vietnam",
            "transport infrastructure investment Vietnam",
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    "energy": {
        "vi": [
            # Điện
            "sản lượng điện phát điện",
            "tiêu thụ điện theo ngành",
            "điện thương phẩm EVN",
            "giá điện bán lẻ biểu giá",
            "công suất lắp đặt hệ thống điện",
            "mất điện thiếu điện",
            "điện khí hóa nông thôn",
            # Năng lượng tái tạo
            "điện mặt trời công suất lắp đặt",
            "điện gió onshore offshore",
            "năng lượng tái tạo tỷ trọng",
            "pin mặt trời áp mái",
            "thủy điện công suất",
            # Dầu khí
            "sản lượng khai thác dầu thô",
            "khí thiên nhiên khai thác",
            "nhập khẩu dầu thô xăng dầu",
            "giá xăng dầu trong nước",
            "petrovietnam pvn",
            "lọc dầu Nghi Sơn Dung Quất",
            # Than
            "sản lượng than khai thác Vinacomin",
            "nhập khẩu than",
            "than cho nhiệt điện",
            # Tiêu thụ & hiệu quả
            "cường độ năng lượng GDP",
            "tiết kiệm năng lượng hiệu quả",
            "tiêu thụ năng lượng cuối cùng",
            "năng lượng bình quân đầu người",
        ],
        "en": [
            "electricity production Vietnam", "power capacity Vietnam",
            "renewable energy Vietnam", "oil gas production Vietnam",
            "energy consumption Vietnam", "EVN statistics",
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    "technology": {
        "vi": [
            # Internet & di động
            "người dùng internet Việt Nam",
            "thuê bao điện thoại di động",
            "tốc độ internet băng thông",
            "4G 5G phủ sóng",
            "thuê bao băng rộng cố định",
            # Thương mại điện tử
            "thương mại điện tử doanh thu",
            "mua sắm trực tuyến",
            "Shopee Lazada Tiki doanh thu",
            "thanh toán không dùng tiền mặt",
            "ví điện tử MoMo ZaloPay",
            # Chuyển đổi số
            "chuyển đổi số doanh nghiệp",
            "chính phủ điện tử dịch vụ công",
            "ứng dụng di động người dùng",
            "fintech tài chính công nghệ",
            # Công nghiệp CNTT
            "doanh thu ngành CNTT phần mềm",
            "xuất khẩu phần mềm dịch vụ CNTT",
            "doanh nghiệp công nghệ số",
            "khu công nghệ cao",
            "FPT Viettel VNPT doanh thu",
            # Đổi mới sáng tạo
            "đầu tư nghiên cứu phát triển R&D",
            "bằng sáng chế đăng ký",
            "startup khởi nghiệp đổi mới",
            "chỉ số đổi mới sáng tạo GII",
            # An toàn thông tin
            "tấn công mạng an ninh mạng",
            "sự cố an toàn thông tin",
        ],
        "en": [
            "internet users Vietnam", "e-commerce Vietnam",
            "mobile subscriptions Vietnam", "digital economy Vietnam",
            "ICT sector revenue Vietnam", "fintech Vietnam",
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    "social": {
        "vi": [
            # An ninh trật tự
            "tội phạm hình sự số vụ",
            "ma túy buôn bán người",
            "tệ nạn xã hội cờ bạc",
            "tội phạm kinh tế tham nhũng",
            # Nhà ở & đô thị
            "nhà ở diện tích bình quân",
            "nhà ở xã hội nhà ở thu nhập thấp",
            "giá nhà đất bất động sản",
            "cải tạo chung cư cũ",
            # An sinh xã hội
            "hộ nghèo cận nghèo theo huyện xã",
            "giảm nghèo bền vững",
            "bảo trợ xã hội trợ cấp",
            "bảo hiểm xã hội bảo hiểm thất nghiệp",
            "quỹ bảo hiểm xã hội",
            "lương hưu người cao tuổi",
            # Bình đẳng & xã hội
            "bất bình đẳng hệ số Gini",
            "chỉ số phát triển con người HDI",
            "bình đẳng giới chỉ số GII",
            "bạo lực gia đình bạo lực giới",
            "trẻ em lao động trẻ em",
            "người khuyết tật",
            # Dân tộc thiểu số
            "dân tộc thiểu số miền núi",
            "vùng đặc biệt khó khăn",
            "xóa đói giảm nghèo vùng dân tộc",
            # Văn hóa thể thao
            "thể thao thành tích huy chương",
            "văn hóa di sản du lịch",
            "báo chí xuất bản phát thanh truyền hình",
        ],
        "en": [
            "crime statistics Vietnam", "social protection Vietnam",
            "income inequality Vietnam", "HDI Vietnam",
            "poverty reduction Vietnam", "social insurance Vietnam",
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    "business": {
        "vi": [
            # Doanh nghiệp
            "doanh nghiệp đăng ký thành lập mới",
            "doanh nghiệp giải thể phá sản",
            "doanh nghiệp đang hoạt động",
            "doanh nghiệp theo ngành nghề",
            "doanh nghiệp nhà nước cổ phần hóa",
            "doanh nghiệp vừa và nhỏ SME",
            "doanh nghiệp tư nhân hộ kinh doanh",
            # Sản xuất
            "chỉ số sản xuất công nghiệp IIP",
            "sản xuất chế biến chế tạo",
            "khu công nghiệp khu chế xuất",
            "tỷ lệ sử dụng công suất",
            "sản lượng công nghiệp theo tỉnh",
            # Thương mại bán lẻ
            "tổng mức bán lẻ hàng hóa dịch vụ",
            "doanh thu bán lẻ tăng trưởng",
            "thị trường bán lẻ siêu thị",
            "chỉ số giá bán lẻ",
            # Xuất nhập khẩu hàng hóa
            "kim ngạch xuất nhập khẩu theo mặt hàng",
            "xuất khẩu hàng dệt may da giày",
            "xuất khẩu điện tử linh kiện",
            "thị trường xuất khẩu đối tác",
            "nhập khẩu nguyên liệu máy móc",
            # Dịch vụ
            "doanh thu dịch vụ",
            "du lịch khách quốc tế nội địa",
            "doanh thu du lịch",
            "dịch vụ tài chính ngân hàng bảo hiểm",
            # Lao động doanh nghiệp
            "lao động trong doanh nghiệp",
            "thu nhập lương bình quân người lao động",
            "năng suất lao động doanh nghiệp",
        ],
        "en": [
            "Vietnam business registration statistics",
            "industrial production Vietnam",
            "retail sales Vietnam", "trade statistics Vietnam",
            "SME Vietnam", "tourism statistics Vietnam",
            "manufacturing Vietnam",
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    "land_urban": {
        "vi": [
            # Đất đai
            "hiện trạng sử dụng đất", "quy hoạch sử dụng đất",
            "đất ở đất thương mại dịch vụ",
            "thu hồi đất đền bù giải phóng mặt bằng",
            "giao đất cho thuê đất",
            "đăng ký cấp giấy chứng nhận quyền sử dụng đất",
            "tranh chấp đất đai",
            # Bất động sản
            "thị trường bất động sản",
            "căn hộ chung cư giá bán",
            "nhà ở xã hội nhà ở công nhân",
            "văn phòng cho thuê công suất",
            "bất động sản công nghiệp khu công nghiệp",
            # Quy hoạch đô thị
            "quy hoạch đô thị xây dựng",
            "đô thị loại I II III",
            "hạ tầng kỹ thuật đô thị",
            "nước sạch thoát nước đô thị",
            "cây xanh công viên đô thị",
        ],
        "en": [
            "land use Vietnam statistics",
            "real estate market Vietnam",
            "urban planning Vietnam",
            "housing market Vietnam",
        ],
    },

    # ══════════════════════════════════════════════════════════════════════════
    "public_admin": {
        "vi": [
            # Hành chính công
            "cải cách hành chính công vụ",
            "chỉ số PAPI cải cách",
            "chỉ số PCI năng lực cạnh tranh cấp tỉnh",
            "thủ tục hành chính dịch vụ công",
            "bộ máy nhà nước biên chế",
            # Ngân sách địa phương
            "ngân sách tỉnh thành phố",
            "thu chi ngân sách địa phương",
            "đầu tư công địa phương",
            # Tư pháp pháp lý
            "vụ án dân sự hình sự",
            "tòa án xét xử",
            "thi hành án dân sự",
            # Đảng đoàn thể
            "đảng viên đoàn viên",
            "bầu cử hội đồng nhân dân",
        ],
        "en": [
            "provincial competitiveness index Vietnam PCI",
            "public administration reform Vietnam",
            "local government budget Vietnam",
        ],
    },

}


def build_queries(
    topics: list[str] | None = None,
    filetypes: list[str] | None = None,
    domains: list[str] | None = None,
    lang: str = "both",
    max_per_topic: int = 3,
) -> list[dict]:
    """
    Sinh danh sách query dict song ngữ Việt + Anh.

    Args:
        topics:        topic keys (None = tất cả)
        filetypes:     ["filetype:xlsx", ...] (None = xlsx + csv)
        domains:       domain group keys (None = tất cả)
        lang:          "vi" | "en" | "both"
                         "vi"   → chỉ keyword tiếng Việt + domain VN
                         "en"   → chỉ keyword tiếng Anh + domain quốc tế
                         "both" → kết hợp cả hai (mặc định)
        max_per_topic: số keyword tối đa mỗi topic × ngôn ngữ

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

    # Phân domain theo ngôn ngữ
    vn_domain_keys   = {"vn_government", "vn_academic", "vn_open_data"}
    intl_domain_keys = {"international", "global_open_data"}

    def _domain_filter(keys):
        return {
            k: v for k, v in DOMAINS.items()
            if (domains is None or k in domains) and k in keys
        }

    vn_domains   = _domain_filter(vn_domain_keys)
    intl_domains = _domain_filter(intl_domain_keys)

    queries = []

    for topic_name, kw_dict in selected_topics.items():
        vi_kws = kw_dict.get("vi", [])[:max_per_topic]
        en_kws = kw_dict.get("en", [])[:max_per_topic]

        for ft in selected_ft:
            ft_ext = ft.split(":")[1]

            # ── Tiếng Việt ───────────────────────────────────────────────────
            if lang in ("vi", "both"):
                for kw in vi_kws:
                    # Generic (không site filter) — Google index file VN rải rác
                    queries.append({
                        "query":        f"{ft} {kw}",
                        "topic":        topic_name,
                        "filetype":     ft_ext,
                        "domain_group": "generic_vi",
                        "lang":         "vi",
                    })
                    # Tạm thời disable filter theo site để tránh bị block.
                    # for dg_name, dg_sites in vn_domains.items():
                    #     for site in dg_sites[:2]:  # 2 site đại diện mỗi group
                    #         queries.append({
                    #             "query":        f"{ft} {kw} {site}",
                    #             "topic":        topic_name,
                    #             "filetype":     ft_ext,
                    #             "domain_group": dg_name,
                    #             "lang":         "vi",
                    #         })

            # ── Tiếng Anh ────────────────────────────────────────────────────
            if lang in ("en", "both"):
                for kw in en_kws:
                    queries.append({
                        "query":        f"{ft} {kw}",
                        "topic":        topic_name,
                        "filetype":     ft_ext,
                        "domain_group": "generic_en",
                        "lang":         "en",
                    })
                    # Tạm thời disable filter theo site để tránh bị block.
                    # for dg_name, dg_sites in intl_domains.items():
                    #     site = dg_sites[0]
                    #     queries.append({
                    #         "query":        f"{ft} {kw} {site}",
                    #         "topic":        topic_name,
                    #         "filetype":     ft_ext,
                    #         "domain_group": dg_name,
                    #         "lang":         "en",
                    #     })

    return queries


def get_quick_queries(n: int = 50, lang: str = "vi") -> list[dict]:
    """Lấy n query đa dạng để test nhanh. Mặc định ưu tiên tiếng Việt."""
    import random
    all_q = build_queries(
        filetypes=["filetype:xlsx", "filetype:csv"],
        lang=lang,
        max_per_topic=2,
    )
    random.shuffle(all_q)
    return all_q[:n]


if __name__ == "__main__":
    import sys
    lang = sys.argv[1] if len(sys.argv) > 1 else "both"
    qs = build_queries(max_per_topic=1, lang=lang)
    print(f"Total queries [{lang}]: {len(qs)}")
    print()
    seen: set[str] = set()
    for q in qs:
        key = f"{q['topic']}_{q['lang']}"
        if key not in seen:
            print(f"  [{q['topic']}][{q['lang']}] {q['query']}")
            seen.add(key)