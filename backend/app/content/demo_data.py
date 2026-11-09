"""Dữ liệu minh hoạ để demo: quán ăn đường phố + thực đơn.

Lưu ý: đây là dữ liệu minh hoạ (mô tả, giá, toạ độ xấp xỉ), không phải thông tin xác thực của từng quán ngoài đời.
Nạp bằng: python -m app.content.seed_demo
"""

# 12 quán bổ sung (8 quán gốc nằm trong seed.py). Toạ độ cách nhau xa hơn 2 lần bán kính kích hoạt (30 m).
DEMO_POIS = [
    {"name": "Phở bò tái lăn", "lat": 10.7630, "lng": 106.7040, "audio_priority": 2,
     "description": "Tô phở bò nước dùng hầm xương trong và ngọt, thịt bò tái lăn xào nhanh trên chảo nóng nên thơm mùi tỏi. Ăn kèm quẩy giòn, hành tây ngâm giấm và rau thơm."},
    {"name": "Cơm tấm sườn bì chả", "lat": 10.7587, "lng": 106.7034, "audio_priority": 2,
     "description": "Cơm tấm nấu từ gạo tấm dẻo thơm, sườn nướng than hoa ướp sả mật ong, ăn cùng bì, chả trứng hấp và đồ chua. Nước mắm pha hơi ngọt rất vừa miệng, bán từ sáng sớm đến trưa."},
    {"name": "Bánh xèo miền Tây", "lat": 10.7614, "lng": 106.7064, "audio_priority": 3,
     "description": "Bánh xèo vàng giòn, nhân tôm thịt giá đỗ, cuốn với rau sống và lá cải rồi chấm nước mắm chua ngọt. Bánh được đổ trên chảo gang lớn ngay khi khách gọi."},
    {"name": "Bún riêu cua", "lat": 10.7585, "lng": 106.7058, "audio_priority": 3,
     "description": "Bún riêu nước dùng chua thanh từ cà chua, gạch cua béo bùi, thêm đậu hũ chiên, huyết và chả. Ăn kèm rau muống chẻ, bắp chuối và chút mắm tôm theo sở thích."},
    {"name": "Bánh tráng trộn cô Mai", "lat": 10.7632, "lng": 106.7060, "audio_priority": 4,
     "description": "Món ăn vặt quen thuộc của giới trẻ: bánh tráng cắt sợi trộn khô bò, trứng cút, xoài xanh, rau răm và sa tế cay cay. Mỗi phần được trộn ngay tại chỗ."},
    {"name": "Cà phê vợt bốn mùa", "lat": 10.7600, "lng": 106.7068, "audio_priority": 4,
     "description": "Cà phê pha bằng vợt vải truyền thống, đậm vị và thơm. Có thể chọn cà phê đen đá, cà phê sữa hoặc bạc xỉu, ngồi ghế nhựa thấp bên vỉa hè nhìn phố xá về chiều."},
    {"name": "Bò nướng lá lốt", "lat": 10.7578, "lng": 106.7047, "audio_priority": 3,
     "description": "Thịt bò băm ướp sả tỏi cuốn lá lốt rồi nướng trên than hồng, dậy mùi thơm đặc trưng. Ăn cuốn bánh tráng với bún, rau sống và chấm mắm nêm."},
    {"name": "Bánh canh cua", "lat": 10.7627, "lng": 106.7022, "audio_priority": 3,
     "description": "Bánh canh sợi to dai, nước lèo sệt sánh nấu từ cua đồng, có thịt cua, chả cua và trứng cút. Thêm chút hành ngò và tiêu xay cho dậy mùi."},
    {"name": "Sinh tố và nước ép tươi", "lat": 10.7607, "lng": 106.7016, "audio_priority": 4,
     "description": "Quầy sinh tố làm từ trái cây tươi theo mùa như bơ, xoài, mãng cầu, dâu tây. Nước ép cam, ổi, dưa hấu vắt tại chỗ, ít đường, hợp giải nhiệt giữa trưa nắng."},
    {"name": "Bánh cuốn nóng", "lat": 10.7640, "lng": 106.7050, "audio_priority": 3,
     "description": "Bánh cuốn tráng mỏng hấp nóng, nhân thịt băm và mộc nhĩ, ăn cùng chả lụa, hành phi và nước mắm pha loãng. Bữa sáng nhẹ nhàng, đặc biệt vào những buổi sáng se lạnh."},
    {"name": "Mì vịt tiềm", "lat": 10.7594, "lng": 106.7020, "audio_priority": 3,
     "description": "Đùi vịt tiềm thuốc bắc mềm thơm, nước dùng đậm vị, ăn với mì trứng hoặc hủ tiếu. Món ăn bổ dưỡng, hợp cho bữa tối ấm bụng."},
    {"name": "Xôi gà chiên", "lat": 10.7620, "lng": 106.7075, "audio_priority": 4,
     "description": "Xôi dẻo thơm ăn cùng đùi gà chiên da giòn, chà bông, hành phi và chút nước sốt mặn ngọt. Món ăn sáng nhanh gọn, bán mang đi rất tiện."},
]

# Thực đơn (tên món, giá VND) cho cả 20 quán, khoá theo tên quán. Giá minh hoạ.
DEMO_MENUS = {
    "Ốc Oanh": [("Ốc len xào dừa", 75000), ("Sò điệp nướng mỡ hành", 65000), ("Ốc hương rang muối ớt", 120000)],
    "Ốc Thảo": [("Ốc hương rang muối ớt", 110000), ("Ốc móng tay xào bơ tỏi", 90000), ("Nghêu hấp sả", 55000)],
    "Bún mọc Thanh Mai": [("Bún mọc đặc biệt", 45000), ("Bún mọc thường", 35000), ("Thêm chả và huyết", 10000)],
    "Bánh mì Sài Gòn": [("Bánh mì thịt nguội", 25000), ("Bánh mì xíu mại", 25000), ("Bánh mì pate trứng", 20000)],
    "Lẩu dê Hương Quê": [("Lẩu dê nhỏ (2-3 người)", 280000), ("Lẩu dê lớn (4-5 người)", 450000), ("Dê nướng tảng", 160000)],
    "Chè Bà Ba": [("Chè bưởi", 20000), ("Chè thái", 25000), ("Chè khúc bạch", 25000)],
    "Hủ tiếu Nam Vang Cô Ba": [("Hủ tiếu Nam Vang đặc biệt", 50000), ("Hủ tiếu khô", 45000), ("Hủ tiếu thường", 40000)],
    "Quán nướng Tứ Hải": [("Bạch tuộc nướng sa tế", 140000), ("Mực nướng muối ớt", 130000), ("Hàu nướng phô mai", 95000)],
    "Phở bò tái lăn": [("Phở tái lăn", 55000), ("Phở tái nạm gầu", 60000), ("Quẩy giòn (phần)", 8000)],
    "Cơm tấm sườn bì chả": [("Cơm sườn bì chả", 50000), ("Cơm sườn trứng ốp la", 55000), ("Canh khổ qua", 15000)],
    "Bánh xèo miền Tây": [("Bánh xèo tôm thịt", 45000), ("Bánh xèo mực", 55000), ("Gỏi cuốn (2 cuốn)", 25000)],
    "Bún riêu cua": [("Bún riêu cua đồng", 45000), ("Bún riêu thêm chả", 55000), ("Đậu hũ chiên (phần)", 10000)],
    "Bánh tráng trộn cô Mai": [("Bánh tráng trộn thường", 20000), ("Bánh tráng trộn đặc biệt", 30000), ("Bánh tráng nướng", 25000)],
    "Cà phê vợt bốn mùa": [("Cà phê đen đá", 15000), ("Cà phê sữa đá", 18000), ("Bạc xỉu", 22000)],
    "Bò nướng lá lốt": [("Bò nướng lá lốt (6 cuốn)", 70000), ("Bún kèm rau sống", 15000), ("Nem nướng", 60000)],
    "Bánh canh cua": [("Bánh canh cua thường", 50000), ("Bánh canh cua đặc biệt", 70000), ("Chả cua thêm", 15000)],
    "Sinh tố và nước ép tươi": [("Sinh tố bơ", 35000), ("Nước ép cam", 30000), ("Sinh tố dâu", 38000)],
    "Bánh cuốn nóng": [("Bánh cuốn nhân thịt", 35000), ("Bánh cuốn chả lụa", 40000), ("Chả lụa thêm", 15000)],
    "Mì vịt tiềm": [("Mì vịt tiềm", 65000), ("Hủ tiếu vịt tiềm", 65000), ("Đùi vịt tiềm thêm", 40000)],
    "Xôi gà chiên": [("Xôi gà chiên", 35000), ("Xôi mặn đầy đủ", 30000), ("Xôi chà bông", 20000)],
}
