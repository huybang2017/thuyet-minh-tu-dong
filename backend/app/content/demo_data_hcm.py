"""Dữ liệu minh hoạ trải rộng nhiều khu vực TP.HCM: 15 khu vực x 4 quán (60 quán) + thực đơn.

Lưu ý: tên quán là tên chung, mô tả/giá là minh hoạ, toạ độ chỉ xấp xỉ quanh tâm mỗi khu vực — không phải thông tin
xác thực của quán ngoài đời. Nạp bằng: python -m app.content.seed_demo
"""
from math import cos, radians

# Tâm xấp xỉ của từng khu vực (lat, lng)
AREAS = {
    "Bến Thành": (10.7725, 106.6980),
    "Phạm Ngũ Lão – Bùi Viện": (10.7675, 106.6935),
    "Nhà thờ Đức Bà": (10.7798, 106.6990),
    "Võ Văn Tần": (10.7770, 106.6870),
    "Chợ Lớn": (10.7540, 106.6630),
    "Bình Tây": (10.7503, 106.6513),
    "Sư Vạn Hạnh": (10.7727, 106.6693),
    "Phú Nhuận": (10.7995, 106.6865),
    "Bà Chiểu": (10.8030, 106.6970),
    "Hoàng Văn Thụ": (10.7985, 106.6590),
    "Gò Vấp": (10.8360, 106.6640),
    "Thảo Điền": (10.8030, 106.7340),
    "Landmark 81": (10.7950, 106.7218),
    "Phú Mỹ Hưng": (10.7290, 106.7195),
    "Thủ Đức": (10.8500, 106.7590),
}

# 4 vị trí cách tâm (mét): đông/tây, bắc/nam — các điểm cách nhau > 100 m, không chồng vùng kích hoạt 30 m
OFFSETS = [(0, 0), (110, 70), (-120, 60), (30, -130)]

# area -> 4 quán: (tên, mô tả, ưu tiên audio, [(món, giá VND)])
_RAW = {
    "Bến Thành": [
        ("Bún thịt nướng chợ Bến Thành", "Bún thịt nướng thơm mùi sả, thịt heo nướng than hồng, chả giò giòn và rau sống, chan nước mắm chua ngọt.", 2,
         [("Bún thịt nướng", 45000), ("Bún thịt nướng chả giò", 55000), ("Chả giò thêm", 15000)]),
        ("Bò kho bánh mì Bến Thành", "Bò kho hầm mềm thơm quế hồi và sả, ăn kèm bánh mì nóng hoặc hủ tiếu, thêm chút rau om ngò gai.", 3,
         [("Bò kho bánh mì", 50000), ("Hủ tiếu bò kho", 55000), ("Bánh mì thêm", 8000)]),
        ("Chè thập cẩm Bến Thành", "Chè nhiều lớp đậu, thạch, nhãn, củ năn và nước cốt dừa béo ngậy, ăn lạnh rất giải nhiệt.", 4,
         [("Chè thập cẩm", 25000), ("Chè khúc bạch", 28000), ("Sương sa hạt lựu", 22000)]),
        ("Nước mía sầu riêng", "Nước mía ép tươi mát lạnh, có thể thêm sầu riêng béo thơm hoặc chút tắc chua nhẹ.", 4,
         [("Nước mía", 15000), ("Nước mía sầu riêng", 30000), ("Nước mía tắc", 18000)]),
    ],
    "Phạm Ngũ Lão – Bùi Viện": [
        ("Bánh mì chảo Bùi Viện", "Bánh mì chảo nóng hổi với trứng ốp la, pate, xúc xích và thịt bò, rất hợp cho bữa sáng của du khách.", 2,
         [("Bánh mì chảo", 60000), ("Bánh mì chảo đặc biệt", 85000), ("Cà phê sữa đá", 20000)]),
        ("Phở cuốn phố Tây", "Phở cuốn mềm mại cuốn thịt bò xào, rau thơm và chấm nước mắm chua ngọt, nhẹ bụng mà đậm vị.", 3,
         [("Phở cuốn bò", 55000), ("Gỏi cuốn tôm thịt", 40000), ("Chả giò", 40000)]),
        ("Cơm chiên Dương Châu", "Cơm chiên hạt tơi với tôm, lạp xưởng, trứng và đậu hà lan, xào nhanh trên lửa lớn nên rất thơm.", 3,
         [("Cơm chiên Dương Châu", 55000), ("Cơm chiên hải sản", 70000), ("Canh chua", 30000)]),
        ("Sinh tố trái cây phố Tây", "Sinh tố xay từ trái cây nhiệt đới tươi như xoài, bơ, thanh long; có nước dừa tươi để giải khát.", 4,
         [("Sinh tố xoài", 35000), ("Sinh tố bơ", 40000), ("Nước dừa tươi", 30000)]),
    ],
    "Nhà thờ Đức Bà": [
        ("Cà phê trứng", "Cà phê phin đậm đà phủ lớp kem trứng đánh bông béo mịn, vị ngọt dịu, một thức uống rất đặc trưng.", 2,
         [("Cà phê trứng", 40000), ("Cà phê muối", 35000), ("Bạc xỉu", 28000)]),
        ("Bánh flan caramel", "Bánh flan mềm mịn tan trong miệng, rưới caramel đắng nhẹ, ăn cùng đá bào và cà phê rất hợp.", 3,
         [("Bánh flan", 20000), ("Flan cà phê", 25000), ("Flan trà xanh", 28000)]),
        ("Bánh mì que pate", "Bánh mì que nhỏ giòn rụm phết pate, thêm chút ớt cay, tiện ăn nhanh khi đi dạo quanh khu trung tâm.", 4,
         [("Bánh mì que", 12000), ("Bánh mì que cay", 15000), ("Sữa đậu nành", 12000)]),
        ("Xôi xéo buổi sáng", "Xôi dẻo vàng ươm rắc đậu xanh nghiền và hành phi, ăn cùng thịt gà xé hoặc chả lụa.", 4,
         [("Xôi xéo", 25000), ("Xôi gà", 30000), ("Xôi đậu xanh", 20000)]),
    ],
    "Võ Văn Tần": [
        ("Bún mắm miền Tây", "Bún mắm nước dùng đậm đà vị mắm, ăn với tôm, mực, thịt heo quay và rau sống, hương vị đặc trưng miền Tây.", 2,
         [("Bún mắm", 55000), ("Bún mắm đặc biệt", 75000), ("Chả cá thêm", 15000)]),
        ("Hủ tiếu mực nướng", "Hủ tiếu nước trong ngọt thanh, ăn kèm mực nướng sa tế thơm lừng, dai giòn và hơi cay.", 3,
         [("Hủ tiếu mực", 60000), ("Mực nướng sa tế", 90000), ("Hủ tiếu khô", 45000)]),
        ("Bánh canh ghẹ", "Bánh canh sợi to dai, nước lèo sánh ngọt vị ghẹ, có thịt ghẹ và chả cá, rắc thêm tiêu xay.", 3,
         [("Bánh canh ghẹ", 70000), ("Bánh canh giò heo", 55000), ("Nem nướng", 45000)]),
        ("Bánh tráng nướng giòn", "Bánh tráng nướng trên than, phủ trứng, hành lá và khô bò, giòn tan và thơm, ăn lúc còn nóng.", 4,
         [("Bánh tráng nướng trứng", 20000), ("Bánh tráng nướng bò khô", 28000), ("Trà tắc", 15000)]),
    ],
    "Chợ Lớn": [
        ("Cơm gà Hải Nam", "Cơm nấu bằng nước luộc gà thơm béo, ăn với gà luộc mềm da giòn, chấm nước tương gừng.", 2,
         [("Cơm gà luộc", 55000), ("Cơm gà xối mỡ", 60000), ("Canh rong biển", 25000)]),
        ("Sủi cảo tôm thịt", "Sủi cảo vỏ mỏng nhân tôm thịt, nấu nước trong hoặc chiên vàng, thơm mùi hành phi và tiêu.", 3,
         [("Sủi cảo nước", 50000), ("Sủi cảo chiên", 55000), ("Hoành thánh", 45000)]),
        ("Dim sum Chợ Lớn", "Các loại dimsum hấp nóng trong xửng tre như há cảo, xíu mại, bánh bao xá xíu, ăn kèm trà nóng.", 2,
         [("Há cảo", 45000), ("Xíu mại", 40000), ("Bánh bao xá xíu", 35000)]),
        ("Mì vịt quay", "Vịt quay da vàng giòn, thịt mềm thơm ngũ vị hương, ăn với mì trứng dai và nước dùng ngọt.", 3,
         [("Mì vịt quay", 70000), ("Vịt quay nửa con", 220000), ("Mì hoành thánh", 55000)]),
    ],
    "Bình Tây": [
        ("Hủ tiếu gõ đêm", "Hủ tiếu gõ bán rong về đêm, nước lèo ngọt thanh, sợi dai, ăn kèm trứng cút và hành phi thơm.", 3,
         [("Hủ tiếu gõ", 25000), ("Hủ tiếu gõ đặc biệt", 35000), ("Trứng cút luộc", 10000)]),
        ("Chè hạt sen long nhãn", "Chè hạt sen bùi, long nhãn ngọt thanh, nấu vừa đường, ăn nóng hay lạnh đều ngon.", 4,
         [("Chè hạt sen", 28000), ("Chè bạch quả", 30000), ("Sâm bổ lượng", 25000)]),
        ("Bánh bao chiên", "Bánh bao chiên vàng giòn đáy, nhân thịt và trứng cút mềm thơm, nóng hổi ăn buổi sáng.", 3,
         [("Bánh bao chiên", 20000), ("Bánh bao nhân thịt", 25000), ("Sữa đậu nành", 12000)]),
        ("Cháo lòng buổi sáng", "Cháo nấu nhừ với lòng heo, tiết và gan, rắc hành ngò và tiêu, ăn kèm quẩy giòn.", 3,
         [("Cháo lòng", 35000), ("Cháo lòng đặc biệt", 45000), ("Quẩy", 8000)]),
    ],
    "Sư Vạn Hạnh": [
        ("Bún đậu mắm tôm", "Mẹt bún đậu gồm đậu hũ chiên, chả cốm, nem chua rán và rau thơm, chấm mắm tôm đánh bọt.", 2,
         [("Mẹt bún đậu", 90000), ("Bún đậu chả cốm", 70000), ("Nem chua rán", 40000)]),
        ("Gà nướng muối ớt", "Gà ta nướng than ướp muối ớt cay thơm, da giòn thịt ngọt, ăn với xôi chiên và rau sống.", 3,
         [("Gà nướng nửa con", 130000), ("Cánh gà nướng", 60000), ("Xôi chiên", 25000)]),
        ("Lẩu nấm thanh đạm", "Lẩu nấm nước dùng ngọt từ rau củ, nhiều loại nấm tươi, hợp cho nhóm bạn thích món nhẹ bụng.", 3,
         [("Lẩu nấm (2-3 người)", 220000), ("Nấm xào tỏi", 60000), ("Rau thêm", 25000)]),
        ("Trà đào cam sả", "Trà đào cam sả thơm mát với miếng đào giòn ngọt, thêm sả đập dập, giải khát cho ngày nóng.", 4,
         [("Trà đào cam sả", 35000), ("Trà vải", 32000), ("Trà tắc", 20000)]),
    ],
    "Phú Nhuận": [
        ("Bún bò Huế buổi sáng", "Bún bò Huế nước dùng đậm sả và ruốc, giò heo mềm, huyết và chả cua, thêm rau sống và ớt sa tế.", 2,
         [("Bún bò Huế", 50000), ("Bún bò giò heo", 60000), ("Chả cua thêm", 15000)]),
        ("Bánh mì xíu mại chén", "Xíu mại viên mềm sốt cà chua ăn với bánh mì giòn, múc bằng chén nhỏ, vị ngọt đậm dễ ăn.", 3,
         [("Bánh mì xíu mại", 30000), ("Xíu mại chén", 35000), ("Cà phê sữa", 20000)]),
        ("Gỏi cuốn tôm thịt", "Gỏi cuốn tươi mát với tôm, thịt luộc, bún và rau thơm, chấm tương đậu phộng béo bùi.", 3,
         [("Gỏi cuốn tôm thịt", 30000), ("Gỏi cuốn chay", 25000), ("Bì cuốn", 28000)]),
        ("Cơm tấm đêm Phan Xích Long", "Cơm tấm mở khuya với sườn nướng thơm, chả trứng và đồ chua, phù hợp cho người ăn tối muộn.", 3,
         [("Cơm tấm sườn nướng", 50000), ("Cơm tấm bì chả đêm", 45000), ("Canh khổ qua", 15000)]),
    ],
    "Bà Chiểu": [
        ("Bánh bột lọc Huế", "Bánh bột lọc dai trong, nhân tôm thịt, ăn cùng bánh bèo chén và nước mắm ớt cay ngọt.", 3,
         [("Bánh bột lọc", 35000), ("Bánh bèo chén", 35000), ("Bánh nậm", 30000)]),
        ("Mì Quảng gà", "Mì Quảng sợi vàng với ít nước dùng đậm, gà xé, đậu phộng rang và bánh tráng mè giòn.", 2,
         [("Mì Quảng gà", 50000), ("Mì Quảng tôm thịt", 55000), ("Bánh tráng mè", 5000)]),
        ("Cháo vịt gừng", "Cháo vịt nấu nhừ thơm gừng, thịt vịt mềm ngọt, ăn kèm gỏi vịt và rau răm.", 3,
         [("Cháo vịt", 40000), ("Gỏi vịt", 90000), ("Cháo vịt đặc biệt", 55000)]),
        ("Chè Huế cung đình", "Các món chè kiểu Huế như chè bắp, chè đậu ván, vị ngọt thanh và dẻo mịn, ăn lạnh hay nóng đều hợp.", 4,
         [("Chè bắp", 20000), ("Chè đậu ván", 22000), ("Chè hạt lựu", 20000)]),
    ],
    "Hoàng Văn Thụ": [
        ("Phá lấu bò", "Phá lấu bò hầm mềm trong nước cốt dừa và ngũ vị hương, ăn với bánh mì hoặc mì gói, chấm mắm gừng.", 2,
         [("Phá lấu bò", 40000), ("Phá lấu bánh mì", 45000), ("Bò viên chiên", 30000)]),
        ("Bún chả Hà Nội", "Bún chả thịt nướng thơm than hồng, chan nước mắm chua ngọt, ăn cùng rau sống và nem cua bể.", 2,
         [("Bún chả", 60000), ("Bún chả nem cua bể", 75000), ("Nem cua bể", 30000)]),
        ("Bánh tằm bì nước cốt dừa", "Bánh tằm sợi mềm trộn bì, giá và rau thơm, chan nước cốt dừa béo ngọt đặc trưng.", 4,
         [("Bánh tằm bì", 35000), ("Bánh tằm xíu mại", 40000), ("Nước cốt dừa thêm", 8000)]),
        ("Quán trứng vịt lộn", "Trứng vịt lộn xào me hoặc nướng muối ớt, ăn kèm rau răm và chút tiêu chanh, món nhậu quen thuộc.", 4,
         [("Trứng vịt lộn xào me", 55000), ("Trứng vịt lộn nướng", 40000), ("Rau muống xào tỏi", 45000)]),
    ],
    "Gò Vấp": [
        ("Bò né sáng", "Bò né chảo nóng với trứng, pate và thịt bò mềm, chấm bánh mì giòn, ăn lúc còn xèo xèo.", 2,
         [("Bò né", 60000), ("Bò né đặc biệt", 80000), ("Bánh mì chấm", 10000)]),
        ("Bánh ướt lòng gà", "Bánh ướt tráng mỏng mềm ăn cùng lòng gà xào, chả lụa và hành phi, chấm nước mắm chua ngọt.", 3,
         [("Bánh ướt lòng gà", 35000), ("Bánh ướt chả lụa", 30000), ("Trà đá", 5000)]),
        ("Lẩu bò đêm", "Lẩu bò nước dùng ngọt thanh nhúng cùng rau và bún, thịt bò mềm, hợp cho nhóm bạn ăn tối.", 3,
         [("Lẩu bò nhỏ", 200000), ("Lẩu bò lớn", 320000), ("Bò thêm", 90000)]),
        ("Cà ri gà bánh mì", "Cà ri gà nước dừa béo thơm, ăn với bánh mì hoặc bún, thêm khoai lang và hành tím.", 3,
         [("Cà ri gà bánh mì", 55000), ("Cà ri gà bún", 55000), ("Gà nướng thêm", 35000)]),
    ],
    "Thảo Điền": [
        ("Bánh mì Việt kiểu mới", "Bánh mì nhân bò nướng, gà lá chanh và rau củ tươi, vỏ giòn nhẹ, phù hợp bữa sáng hiện đại.", 3,
         [("Bánh mì bò nướng", 55000), ("Bánh mì gà lá chanh", 50000), ("Nước ép cam", 40000)]),
        ("Phở gà ta", "Phở gà ta nước dùng trong thanh ngọt, thịt gà dai thơm, rắc hành lá và chanh ớt.", 2,
         [("Phở gà", 60000), ("Phở gà đùi", 70000), ("Gỏi gà", 65000)]),
        ("Cà phê rang xay Thảo Điền", "Cà phê rang xay thơm đậm, pha phin truyền thống hoặc cold brew mát lạnh, không gian yên tĩnh.", 4,
         [("Cà phê phin", 35000), ("Cold brew", 45000), ("Cà phê cam", 45000)]),
        ("Cơm niêu cá kho", "Cơm niêu cháy giòn đáy ăn cùng cá kho tộ, thịt kho trứng và canh chua, đậm vị gia đình.", 3,
         [("Cơm niêu cá kho", 90000), ("Cơm niêu thịt kho", 85000), ("Canh chua cá", 70000)]),
    ],
    "Landmark 81": [
        ("Bún chả cá Nha Trang", "Bún chả cá nước dùng ngọt thanh từ xương và cá, chả cá chiên vàng dai ngon, thêm rau sống.", 2,
         [("Bún chả cá", 50000), ("Bánh canh chả cá", 50000), ("Chả cá chiên", 40000)]),
        ("Gỏi đu đủ khô bò", "Gỏi đu đủ bào sợi trộn khô bò, rau răm và đậu phộng, vị chua cay ngọt hài hòa, rất đưa miệng.", 4,
         [("Gỏi đu đủ khô bò", 45000), ("Gỏi ngó sen", 60000), ("Trà tắc", 18000)]),
        ("Kem dừa", "Kem dừa mát lạnh dùng trong trái dừa, thêm dừa nạo và đậu phộng rang, ăn buổi chiều ven sông.", 4,
         [("Kem dừa", 45000), ("Kem xôi dừa", 50000), ("Nước dừa tươi", 30000)]),
        ("Bánh hỏi heo quay", "Heo quay da giòn thái mỏng cuốn bánh hỏi mềm và rau thơm, chấm mắm nêm đậm đà.", 3,
         [("Bánh hỏi heo quay", 85000), ("Heo quay thêm", 70000), ("Gỏi cuốn", 40000)]),
    ],
    "Phú Mỹ Hưng": [
        ("Cơm chiên cá mặn", "Cơm chiên hạt tơi trộn cá mặn thơm, thêm trứng và hành lá, vị đậm đà, ăn kèm canh rau củ.", 3,
         [("Cơm chiên cá mặn", 65000), ("Cơm chiên gà", 60000), ("Canh rau củ", 25000)]),
        ("Mì cay bảy cấp độ", "Mì cay nước dùng đỏ ớt, chọn nhiều cấp độ cay, thêm hải sản, bò viên và rau cải.", 3,
         [("Mì cay cấp 3", 55000), ("Mì cay hải sản", 70000), ("Trà sữa", 35000)]),
        ("Bánh xèo tôm nhảy", "Bánh xèo vàng giòn nhân tôm nhảy tươi và giá đỗ, cuốn rau sống chấm nước mắm chua ngọt.", 3,
         [("Bánh xèo tôm nhảy", 70000), ("Bánh xèo rau củ", 50000), ("Nem lụi", 55000)]),
        ("Bún măng vịt", "Bún măng vịt nước dùng thanh ngọt, thịt vịt mềm và măng giòn, chấm mắm gừng cay nhẹ.", 3,
         [("Bún măng vịt", 55000), ("Miến vịt", 55000), ("Gỏi măng vịt", 85000)]),
    ],
    "Thủ Đức": [
        ("Bánh mì thịt nướng sinh viên", "Bánh mì thịt nướng nóng giòn giá bình dân, nhiều rau và nước sốt đậm, quen thuộc với sinh viên.", 3,
         [("Bánh mì thịt nướng", 25000), ("Bánh mì trứng", 15000), ("Sữa đậu nành", 10000)]),
        ("Cơm bình dân sinh viên", "Cơm phần đầy đặn với sườn, gà hoặc cá chiên cùng canh và rau, giá mềm phù hợp học sinh sinh viên.", 3,
         [("Cơm sườn", 35000), ("Cơm gà", 35000), ("Canh chua", 15000)]),
        ("Trà sữa và ăn vặt", "Trà sữa trân châu và các món ăn vặt vỉa hè như bánh tráng trộn, xiên que nướng, đông khách vào buổi chiều.", 4,
         [("Trà sữa trân châu", 30000), ("Bánh tráng trộn", 20000), ("Xiên que nướng", 15000)]),
        ("Bún bò gánh", "Bún bò nấu theo kiểu gánh rong, nước dùng ngọt thơm sả, giò heo mềm, đậm đà khó quên.", 2,
         [("Bún bò", 40000), ("Bún bò đặc biệt", 50000), ("Giò heo thêm", 20000)]),
    ],
}


def _offset_to_latlng(clat: float, clng: float, dx_m: float, dy_m: float) -> tuple[float, float]:
    lat = clat + dy_m / 111_320
    lng = clng + dx_m / (111_320 * cos(radians(lat)))
    return round(lat, 6), round(lng, 6)


def _build():
    pois, menus = [], {}
    for area, shops in _RAW.items():
        clat, clng = AREAS[area]
        assert len(shops) == len(OFFSETS)
        for (name, desc, prio, items), (dx, dy) in zip(shops, OFFSETS):
            lat, lng = _offset_to_latlng(clat, clng, dx, dy)
            pois.append({"name": name, "description": desc, "lat": lat, "lng": lng, "audio_priority": prio, "area": area})
            menus[name] = items
    return pois, menus


DEMO_POIS_HCM, DEMO_MENUS_HCM = _build()
