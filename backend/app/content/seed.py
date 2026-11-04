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
