"""Tài khoản và quán demo để khám phá cổng chủ quán trong môi trường dev."""
from ..db import get_db
from ..security import encrypt_pii, hash_password
from .service import now

DEMO_OWNER_PASSWORD = "Demo@12345"

# username, display name, shop, district, address, lat, lng, description
DEMO_OWNERS = [
    ("owner_q1", "Nguyễn Minh Anh", "Bếp Nhà Bên Hông", "Quận 1", "12 Nguyễn Thái Bình", 10.7682, 106.6981, "Cơm nhà và món Việt giữa trung tâm thành phố."),
    ("owner_q3", "Trần Quốc Bảo", "Hủ Tiếu Mỹ Tho Sáu Lộc", "Quận 3", "84 Nguyễn Thượng Hiền", 10.7767, 106.6864, "Hủ tiếu Mỹ Tho với nước lèo nấu từ xương và tôm khô."),
    ("owner_q4", "Lê Thanh Hương", "Bánh Xèo Cô Ba", "Quận 4", "33 Vĩnh Khánh", 10.7591, 106.7042, "Bánh xèo giòn, rau sống tươi và nước mắm pha tại quán."),
    ("owner_q5", "Phạm Hoàng Long", "Dim Sum Phố Người Hoa", "Quận 5", "102 Hải Thượng Lãn Ông", 10.7548, 106.6602, "Há cảo, xíu mại và dim sum làm mới mỗi ngày."),
    ("owner_q6", "Võ Ngọc Mai", "Bún Bò Huế Ngự Bình", "Quận 6", "18 Bình Tây", 10.7492, 106.6528, "Bún bò Huế đậm vị sả, phục vụ từ sáng đến trưa."),
    ("owner_q7", "Đặng Tuấn Kiệt", "Cơm Tấm Bờ Kè", "Quận 7", "55 Lâm Văn Bền", 10.7418, 106.7172, "Cơm tấm sườn nướng, bì, chả và nước mắm nhà làm."),
    ("owner_q8", "Bùi Thảo Vy", "Mì Quảng Bà Mười", "Quận 8", "27 Phạm Thế Hiển", 10.7353, 106.6788, "Mì Quảng với gà ta, tôm và bánh tráng mè."),
    ("owner_q10", "Ngô Đức Thành", "Ốc Đêm Thành Phát", "Quận 10", "61 Nguyễn Tri Phương", 10.7651, 106.6787, "Các món ốc và hải sản chế biến theo yêu cầu."),
    ("owner_q11", "Đỗ Mỹ Linh", "Chè Nhà Làm Út Nhỏ", "Quận 11", "20 Lãnh Binh Thăng", 10.7638, 106.6507, "Chè truyền thống nấu mới mỗi ngày, vị ngọt thanh."),
    ("owner_binhthanh", "Huỳnh Gia Hân", "Bánh Cuốn Gia Truyền Thanh Đa", "Bình Thạnh", "102 Xô Viết Nghệ Tĩnh", 10.8062, 106.7103, "Bánh cuốn nóng với chả lụa và hành phi."),
    ("owner_govap", "Phan Anh Tuấn", "Gỏi Cuốn Cây Trâm", "Gò Vấp", "48 Quang Trung", 10.8335, 106.6652, "Gỏi cuốn tôm thịt và nước chấm đậu phộng."),
    ("owner_tanbinh", "Lý Bảo Ngọc", "Phở Gà Tân Sơn Nhất", "Tân Bình", "77 Bạch Đằng", 10.8134, 106.6658, "Phở gà ta nước dùng trong, mở cửa từ sáng sớm."),
    ("owner_phunhuan", "Trương Minh Khang", "Bún Riêu Cua Phú Nhuận", "Phú Nhuận", "31 Phan Xích Long", 10.8004, 106.6848, "Bún riêu cua đồng với đậu hũ và rau sống."),
    ("owner_thuduc", "Đinh Khánh An", "Bò Né Làng Đại Học", "Thủ Đức", "15 Võ Văn Ngân", 10.8508, 106.7625, "Bò né chảo nóng ăn cùng bánh mì giòn."),
    ("owner_nhabe", "Mai Thanh Tâm", "Hải Sản Tươi Nhà Bè", "Nhà Bè", "8 Huỳnh Tấn Phát", 10.6954, 106.7355, "Hải sản tươi chế biến đơn giản, giữ vị tự nhiên."),
]

# Mapping "demo-poi-<username>" -> poi_id (được điền khi seed_demo_owners chạy)
_DEMO_POI_IDS: dict[str, int] = {}


async def seed_demo_owners() -> None:
    """Tạo idempotent 15 tài khoản và quán đã duyệt, chỉ được gọi trong dev."""
    db = get_db()
    timestamp = now()
    for username, display_name, shop, district, address, lat, lng, description in DEMO_OWNERS:
        # Tạo user nếu chưa có (dựa trên username duy nhất)
        user = await db.fetchone("SELECT id FROM admin_users WHERE username=%s", [username])
        if user:
            uid = user["id"]
        else:
            uid = await db.insert("admin_users", {
                "username": username, "email": f"{username}@example.test",
                "password_hash": hash_password(DEMO_OWNER_PASSWORD), "role": "poi_owner",
                "display_name": display_name, "is_active": True, "is_verified": True,
                "is_poi_owner_verified": True, "created_at": timestamp,
            })

        # Tạo POI nếu chưa có (dựa trên tên shop)
        poi = await db.fetchone("SELECT id FROM poi WHERE name=%s", [shop])
        if poi:
            poi_id = poi["id"]
            # cập nhật lại owner_id nếu cần
            if poi.get("owner_id") != uid:
                await db.update("poi", poi_id, {"owner_id": uid})
        else:
            poi_id = await db.insert("poi", {
                "owner_id": uid, "name": shop,
                "description": description, "address": f"{address}, {district}, TP. Hồ Chí Minh",
                "lat": lat, "lng": lng, "images": [],
                "trigger_radius": 40, "audio_priority": 3,
                "is_active": True, "audio_status": "none", "updated_at": timestamp,
            })
        _DEMO_POI_IDS[f"demo-poi-{username}"] = poi_id

        # Tạo registration nếu chưa có (dựa trên user_id)
        reg = await db.fetchone("SELECT id FROM poi_owner_registrations WHERE user_id=%s", [uid])
        if not reg:
            await db.insert("poi_owner_registrations", {
                "user_id": uid, "shop_name": shop,
                "phone": "0900000000",
                "status": "approved", "admin_note": "Tài khoản mẫu môi trường dev.",
                "created_at": timestamp, "reviewed_at": timestamp,
            })
