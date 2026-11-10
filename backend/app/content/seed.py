from datetime import datetime, timezone

# (id, tên, mô tả tiếng Việt, lat, lng, ưu tiên audio)
_RAW = [
    ("poi-oc-oanh", "Ốc Oanh", "Quán ốc nổi tiếng, nổi bật với ốc len xào dừa, sò điệp nướng mỡ hành và nước chấm me chua cay đặc trưng.", 10.7612, 106.7046, 1),
    ("poi-oc-thao", "Ốc Thảo", "Quán ốc lâu năm với menu đa dạng: ốc hương rang muối ớt, ốc móng tay xào bơ tỏi, giá bình dân, đông khách vào buổi tối.", 10.7609, 106.7038, 2),
    ("poi-bun-moc", "Bún mọc Thanh Mai", "Tô bún mọc nước dùng ngọt thanh từ xương heo, mọc giò dai giòn, thêm chả và huyết, ăn sáng rất hợp.", 10.7601, 106.7029, 3),
    ("poi-banh-mi", "Bánh mì Sài Gòn", "Ổ bánh mì giòn rụm, pate nhà làm, thịt nguội và đồ chua tự muối, bán từ sáng sớm đến khuya.", 10.7596, 106.7051, 3),
    ("poi-lau-de", "Lẩu dê Hương Quê", "Nồi lẩu dê thơm mùi sả gừng, thịt dê mềm, ăn kèm rau rừng và bún tươi, thích hợp nhóm bạn đông người.", 10.7619, 106.7033, 2),
    ("poi-che", "Chè Bà Ba", "Quán chè truyền thống với chè bưởi, chè thái, chè khúc bạch, vị ngọt dịu giải nhiệt buổi chiều.", 10.7605, 106.7058, 4),
    ("poi-hu-tieu", "Hủ tiếu Nam Vang Cô Ba", "Hủ tiếu nước trong, tôm thịt đầy đặn, hành phi thơm, đậm chất Nam Vang giữa lòng Sài Gòn.", 10.7624, 106.7049, 3),
    ("poi-nuong", "Quán nướng Tứ Hải", "Các món nướng than hoa: bạch tuộc, mực, hàu nướng phô mai, ướp đậm đà, phục vụ tới 2 giờ sáng.", 10.7592, 106.7042, 2),
]


# thực đơn mẫu cho quán demo: poi_id → [(tên món, giá VND)]
_MENU = {
    "poi-oc-oanh": [("Ốc len xào dừa", 70000), ("Sò điệp nướng mỡ hành", 80000), ("Ốc hương rang muối", 90000)],
    "poi-oc-thao": [("Ốc hương rang muối ớt", 85000), ("Ốc móng tay xào bơ tỏi", 75000), ("Sò huyết rang me", 70000)],
    "poi-bun-moc": [("Bún mọc thường", 40000), ("Bún mọc đặc biệt", 55000)],
    "poi-banh-mi": [("Bánh mì thịt nguội", 25000), ("Bánh mì pate trứng", 20000), ("Bánh mì đặc biệt", 35000)],
    "poi-lau-de": [("Lẩu dê nhỏ", 250000), ("Lẩu dê lớn", 400000), ("Dê nướng chao", 150000)],
    "poi-che": [("Chè bưởi", 20000), ("Chè thái", 25000), ("Chè khúc bạch", 30000)],
    "poi-hu-tieu": [("Hủ tiếu Nam Vang", 50000), ("Hủ tiếu khô", 50000)],
    "poi-nuong": [("Bạch tuộc nướng", 120000), ("Mực nướng sa tế", 130000), ("Hàu nướng phô mai", 90000)],
    "demo-poi-owner_q1": [("Cơm sườn nướng", 65000), ("Canh chua cá", 55000), ("Gỏi cuốn tôm thịt", 45000)],
    "demo-poi-owner_q3": [("Hủ tiếu Mỹ Tho đặc biệt", 65000), ("Hủ tiếu khô", 60000), ("Hoành thánh chiên", 35000)],
    "demo-poi-owner_q4": [("Bánh xèo tôm thịt", 70000), ("Bánh khọt", 55000), ("Gỏi cuốn", 40000)],
    "demo-poi-owner_q5": [("Há cảo tôm", 45000), ("Xíu mại hấp", 40000), ("Bánh bao xá xíu", 35000)],
    "demo-poi-owner_q6": [("Bún bò đặc biệt", 65000), ("Bún bò giò heo", 70000), ("Chả Huế", 30000)],
    "demo-poi-owner_q7": [("Cơm tấm sườn bì chả", 60000), ("Cơm tấm sườn trứng", 55000), ("Sườn nướng thêm", 30000)],
    "demo-poi-owner_q8": [("Mì Quảng gà", 60000), ("Mì Quảng tôm thịt", 65000), ("Bánh tráng mè", 10000)],
    "demo-poi-owner_q10": [("Ốc hương rang muối", 95000), ("Nghêu hấp sả", 70000), ("Sò điệp nướng mỡ hành", 85000)],
    "demo-poi-owner_q11": [("Chè đậu xanh", 25000), ("Chè thập cẩm", 30000), ("Sâm bổ lượng", 30000)],
    "demo-poi-owner_binhthanh": [("Bánh cuốn đặc biệt", 55000), ("Bánh cuốn chả lụa", 45000), ("Nem chua", 25000)],
    "demo-poi-owner_govap": [("Gỏi cuốn tôm thịt", 40000), ("Bì cuốn", 35000), ("Gỏi cuốn bò bía", 35000)],
    "demo-poi-owner_tanbinh": [("Phở gà đùi", 65000), ("Phở gà xé", 55000), ("Trứng non thêm", 25000)],
    "demo-poi-owner_phunhuan": [("Bún riêu đầy đủ", 60000), ("Bún riêu giò", 65000), ("Đậu hũ thêm", 10000)],
    "demo-poi-owner_thuduc": [("Bò né trứng", 65000), ("Bò né phô mai", 75000), ("Bánh mì thêm", 10000)],
    "demo-poi-owner_nhabe": [("Tôm nướng muối ớt", 150000), ("Mực hấp gừng", 130000), ("Nghêu hấp sả", 80000)],
}


def build_menu_seed(existing_poi_ids: set[str]) -> list[dict]:
    now = datetime.now(timezone.utc)
    return [{"_id": f"{pid}-m{i}", "poi_id": pid, "name": name, "price": price, "description": None, "created_at": now}
            for pid, items in _MENU.items() if pid in existing_poi_ids
            for i, (name, price) in enumerate(items, 1)]


def build_seed() -> list[dict]:
    now = datetime.now(timezone.utc)
    docs = []
    for pid, name, desc, lat, lng, prio in _RAW:
        docs.append({
            "_id": pid,
            "name": name,
            "description": desc,
            "lat": lat,
            "lng": lng,
            "location": {"type": "Point", "coordinates": [lng, lat]},
            "trigger_radius": 30,
            "audio_priority": prio,
            "images": [],
            "is_active": True,
            "audio_status": "none",
            "owner_id": None,
            "updated_at": now,
        })
    return docs
