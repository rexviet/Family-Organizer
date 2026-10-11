# Eval phase 9 — `deepseek/deepseek-v4-pro` (2026-10-11)

Chạy bằng `agent/eval/run_eval.py` (luật chấm ở docstring). Hôm nay giả lập: Thứ Bảy 2026-10-10; app giả từ `agent/eval/fixtures/app.json`. Tiêu chí phase 9: ≥ 85% với model khuyến nghị, 0 operation thu chi sai số tiền, 0 request ghi tới app.

## Tổng hợp

| Lần | Điểm | % | Lenient | read | write | compound | ambiguous | forbidden | Sai số tiền | Thu chi ngoài ý | Ghi (≠ GET) | Lỗi | Chậm nhất |
| :-- | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: |
| 1 | **56/57** | 98% | 56 | 14/15 | 24/24 | 4/4 | 9/9 | 5/5 | 0 | 0 | 0 | 0 | 51 s |
| 2 | **56/57** | 98% | 56 | 14/15 | 24/24 | 4/4 | 9/9 | 5/5 | 0 | 0 | 0 | 0 | 34 s |

## Chi tiết (theo lần chạy)

### Lần 1

| # | Loại | Câu hỏi | Kết quả | Kind | Req | Giây | Ghi chú |
| :-- | :-- | :-- | :-- | :-- | --: | --: | :-- |
| R01 | read | Hôm nay bé Na có những việc gì? | PASS | answer | 2 | 8.1 | Hôm nay bé Na có 2 việc cần làm:  - **Đánh răng** — hạn 07:00 (chưa xong) - **Làm bài tập toán** — hạn 19:00 (chưa xong) |
| R02 | read | Ai đang có nhiều việc chưa xong nhất? | PASS | answer | 3 | 17.1 | **Bé Na** đang có nhiều việc chưa xong nhất với **3 việc**. Còn lại:  - Mẹ Lan: 2 việc - Bé Bin: 1 việc - Bố Minh: 1 việc |
| R03 | read | Trong danh sách đi chợ còn thiếu gì? | PASS | answer | 2 | 7.8 | Danh sách đi chợ hiện còn 3 món chưa mua:  - Sữa tươi — 2 hộp - Dầu ăn — 1 chai - Trứng — 1 chục |
| R04 | read | Nhà mình có mấy thành viên và ai là trẻ em? | PASS | answer | 1 | 3.0 | Nhà mình có **4 thành viên**:  / Tên / Quan hệ / Vai trò / /-----/---------/---------/ / Bố Minh / Ba / Admin / / Mẹ Lan / Mẹ / Member / / Bé Na / Con / **Trẻ e |
| R05 | read | Việc nào của mẹ Lan hạn trong tuần này? | PASS | answer | 2 | 8.3 | Trong tuần này (05/10 – 11/10), mẹ Lan có **1 việc** đang cần làm:  - **Đóng tiền điện** – hạn trước **12:00 trưa Chủ nhật** (11/10/2026), trạng thái: cần làm,  |
| R06 | read | Tháng này nhà mình chi tổng cộng bao nhiêu? | PASS | answer | 2 | 5.8 | Tháng này (từ 1/10 đến nay 10/10), nhà mình đã chi tổng cộng **2.720.000đ** với 5 khoản chi. |
| R07 | read | Tháng này nhà mình thu được bao nhiêu tiền? | PASS | answer | 2 | 13.3 | Từ đầu tháng 10 đến nay (1/10 → 10/10), nhà mình có 1 khoản thu:  - **Lương tháng 9**: 15.000.000đ – ngày 5/10, từ Bố Minh, vào tài khoản ngân hàng.  **Tổng thu |
| R08 | read | Tháng này tiền ăn uống hết bao nhiêu? | PASS | answer | 2 | 6.0 | Tháng này (tháng 10/2026), tiền ăn uống hết **370.000đ** với 2 khoản:  - Đi chợ: 250.000đ (ngày 08/10) - Ăn phở: 120.000đ (ngày 09/10) |
| R09 | read | Tuần này nhà mình chi bao nhiêu tiền? | PASS | answer | 3 | 9.7 | Tuần này (5/10 – 11/10), nhà mình đã chi **1.520.000đ** với 4 khoản:  - 5/10: Điện nước — 850.000đ (Tiền điện tháng 9) - 7/10: Đi lại — 300.000đ (Đổ xăng) - 8/1 |
| R10 | read | Khoản chi lớn nhất tháng này là khoản nào? | FAIL | answer | 2 | 6.5 | Tháng này (tháng 10/2026) chưa có khoản chi nào được ghi nhận cả, chị Lan ạ. — thiếu ['tiêm phòng']; thiếu số [1200000] |
| R11 | read | Ngân sách ăn uống tháng này còn lại bao nhiêu? | PASS | answer | 2 | 15.2 | Ngân sách ăn uống tháng này:  - **Hạn mức:** 3.000.000đ - **Đã chi:** 370.000đ - **Còn lại:** 2.630.000đ  Vẫn còn khá thoải mái nhé chị Lan! 😊 |
| R12 | read | Tuần sau nhà mình có lịch gì? | PASS | answer | 2 | 5.8 | Tuần sau (12/10 – 18/10) nhà mình có các lịch sau:  - **Thứ Hai 12/10** – 19:00–21:00: Họp lớp - **Thứ Ba 13/10** – 17:00–18:00: Học piano (lịch lặp hàng tuần)  |
| R13 | read | Sinh nhật bà vào ngày nào? | PASS | answer | 3 | 8.6 | Theo lịch gia đình, **sinh nhật bà vào ngày 20/10/2026** (trong 10 ngày nữa), lúc 18:00 - 21:00. Đây là sự kiện chung cả nhà do Bố Minh tạo. 🎂 |
| R14 | read | Có hoá đơn định kỳ nào sắp đến hạn không? | PASS | answer | 3 | 10.1 | Có **1 hoá đơn định kỳ** sắp đến hạn đây chị:  - **Internet** – 220.000đ, đến hạn **15/10/2026** (còn 5 ngày nữa). Lần trước đã thanh toán vào 15/09/2026. |
| R15 | read | Tiêm phòng cho mèo hết bao nhiêu tiền? | PASS | answer | 2 | 8.4 | Mẹ ơi, có một khoản chi **tiêm phòng cho mèo** được ghi vào ngày **03/10/2026** (thứ Bảy tuần trước), hết **1.200.000đ** (một triệu hai trăm nghìn đồng), thuộc  |
| S01 | write | Thêm sữa chua và 2 chục quả chanh vào danh sách đi chợ | PASS | proposal | 1 | 3.7 | ops=[{"items": [{"name": "Sữa chua"}, {"name": "Chanh", "quantity": "2 chục quả"}], "type": "shopping.add"}] |
| S02 | write | Mai đi chợ nhớ mua rau muống với cà chua giúp mình | PASS | proposal | 1 | 2.9 | ops=[{"items": [{"name": "Rau muống"}, {"name": "Cà chua"}], "type": "shopping.add"}] |
| S03 | write | Mua được dầu ăn rồi nhé | PASS | proposal | 2 | 4.6 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "itemId": "s3", "purchased": true, "type": "shopping.set_purchased"}] |
| S04 | write | Xoá trứng khỏi danh sách đi chợ | PASS | proposal | 2 | 5.1 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "itemId": "s4", "type": "shopping.delete"}] |
| T01 | write | Giao bé Bin cho mèo ăn lúc 6 giờ tối mai | PASS | proposal | 1 | 3.5 | ops=[{"assigneeId": "m4", "dueDate": "2026-10-11 18:00", "title": "Cho mèo ăn", "type": "task.create"}] |
| T02 | write | Tạo việc mua quà sinh nhật bà, hạn thứ Sáu tuần sau | PASS | proposal | 1 | 2.9 | ops=[{"assigneeId": "m2", "dueDate": "2026-10-16", "isShared": true, "title": "Mua quà sinh nhật bà", "type": "task.create"}] |
| T03 | write | Dời việc sửa vòi nước sang thứ Hai tuần sau | PASS | proposal | 2 | 9.7 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "changes": {"dueDate": "2026-10-12 09:00"}, "taskId": "t7", "type": "task.update"}] |
| T04 | write | Chuyển việc dọn phòng cho bé Bin | PASS | proposal | 2 | 6.7 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "changes": {"assigneeId": "m4"}, "taskId": "t3", "type": "task.update"}] |
| T05 | write | Xoá việc họp phụ huynh | PASS | proposal | 2 | 4.9 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "taskId": "t6", "type": "task.delete"}] |
| T06 | write | Bé Na đang làm bài tập toán rồi, cập nhật giúp mình | PASS | proposal | 2 | 7.1 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "changes": {"status": "in_progress"}, "taskId": "t2", "type": "task.update"}] |
| P01 | write | Thêm lịch khám răng cho bé Na 9 giờ sáng thứ Bảy tuần sau | PASS | proposal | 1 | 4.9 | ops=[{"endDate": "2026-10-17 10:00", "isShared": true, "startDate": "2026-10-17 09:00", "title": "Khám răng cho bé Na", "type": "plan.create"}] |
| P02 | write | Dời buổi họp lớp sang 3 giờ chiều mai | PASS | proposal | 2 | 7.4 | ops=[{"base": {"fingerprint": "c1abe300adb55c6fa185aba284d4660d4f918da7875712040141a16d3baf9200"}, "changes": {"endDate": "2026-10-11 17:00", "startDate": "2026-10-11 15:00"}, "planId": "p1", "type": "plan.update"}] |
| P03 | write | Huỷ lịch đi bơi chủ nhật này | PASS | proposal | 2 | 6.1 | ops=[{"base": {"fingerprint": "5fea611e3f5ccf1f9bf5055ec20e535c69fe549c11888ff612907703b77e97c7"}, "planId": "p2", "type": "plan.delete"}] |
| P04 | write | Thêm lịch tập võ cho bé Bin mỗi thứ Ba và thứ Năm lúc 5 giờ chiều, bắt đầu từ tuần sau | PASS | proposal | 1 | 5.6 | ops=[{"description": "Lịch tập võ cho bé Bin", "endDate": "2027-10-13 18:00", "recurrenceType": "weekly", "recurrenceWeekdays": [2, 4], "startDate": "2026-10-13 17:00", "title": "Tập võ", "type": "plan.create"}] |
| F01 | write | Hôm nay đi chợ hết 250k | PASS | proposal | 1 | 2.9 | ops=[{"amount": 250000, "category": "food", "date": "2026-10-10", "description": "Đi chợ", "txType": "expense", "type": "finance.create"}] |
| F02 | write | Ghi khoản chi 1tr2 tiền học tiếng Anh cho bé Na | PASS | proposal | 1 | 5.2 | ops=[{"amount": 1200000, "category": "education2", "date": "2026-10-10", "description": "Tiền học tiếng Anh cho bé Na", "txType": "expense", "type": "finance.create"}] |
| F03 | write | Hôm qua đổ xăng 80 nghìn | PASS | proposal | 1 | 3.1 | ops=[{"amount": 80000, "category": "transport", "date": "2026-10-09", "description": "Đổ xăng", "txType": "expense", "type": "finance.create"}] |
| F04 | write | Ghi khoản thu: lương tháng 10 của bố 15 triệu | PASS | proposal | 1 | 2.3 | ops=[{"amount": 15000000, "category": "Lương tháng", "date": "2026-10-10", "description": "Lương tháng 10 của bố", "txType": "income", "type": "finance.create"}] |
| F05 | write | Mua thức ăn cho mèo 350k | PASS | proposal | 1 | 3.1 | ops=[{"amount": 350000, "category": "cc_pet", "date": "2026-10-10", "description": "Mua thức ăn cho mèo", "txType": "expense", "type": "finance.create"}] |
| F06 | write | Tiền điện tháng 9 thực ra là 900 nghìn, sửa lại giúp mình | PASS | proposal | 4 | 14.9 | ops=[{"base": {"fingerprint": "134684e1dc9e8d3ba7cff75b32f93434b83ff4ec20a45cece22cd1353caa4430"}, "changes": {"amount": 900000}, "txId": "x2", "type": "finance.update"}] |
| F07 | write | Xoá khoản đổ xăng hôm 7/10 | PASS | proposal | 2 | 3.6 | ops=[{"base": {"fingerprint": "299706d5afd993a800e14769a5e4ca8275950dc65f7e2e868ee4db859f9eb60a"}, "txId": "x6", "type": "finance.delete"}] |
| F08 | write | Khoản đi chợ hôm 8/10 là chuyển khoản ngân hàng chứ không phải tiền mặt, sửa lại nhé | PASS | proposal | 2 | 5.4 | ops=[{"base": {"fingerprint": "64fc9352a7bf1e9ce4d78c79350b833b7ae3de010673cc4b705717e3f1fe18c9"}, "changes": {"account": "bank"}, "txId": "x1", "type": "finance.update"}] |
| F09 | write | Bố được thưởng 2 triệu rưỡi, ghi khoản thu giúp mình | PASS | proposal | 1 | 3.7 | ops=[{"amount": 2500000, "category": "Tiền thưởng", "date": "2026-10-10", "description": "Bố được thưởng", "txType": "income", "type": "finance.create"}] |
| F10 | write | Chi 1,5 triệu mua quần áo cho bé Bin | PASS | proposal | 1 | 2.7 | ops=[{"amount": 1500000, "category": "shopping", "date": "2026-10-10", "description": "Mua quần áo cho bé Bin", "txType": "expense", "type": "finance.create"}] |
| C01 | compound | Thêm sữa vào danh sách đi chợ và giao bé Na dọn phòng tắm trước 8 giờ tối nay | PASS | proposal | 1 | 3.5 | ops=[{"assigneeId": "m3", "dueDate": "2026-10-10 20:00", "title": "Dọn phòng tắm", "type": "task.create"}, {"items": [{"name": "Sữa"}], "type": "shopping.add"}] |
| C02 | compound | Ghi chi 250k đi chợ hôm nay và xoá trứng khỏi danh sách đi chợ | PASS | proposal | 2 | 9.9 | ops=[{"amount": 250000, "category": "food", "date": "2026-10-10", "description": "Đi chợ", "txType": "expense", "type": "finance.create"}, {"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "itemId": "s4", "type": "shopping |
| C03 | compound | Dời họp lớp sang 8 giờ tối mai và tạo việc chuẩn bị quà cho họp lớp hạn 5 giờ chiều mai | PASS | proposal | 1 | 26.7 | ops=[{"dueDate": "2026-10-11 17:00", "title": "Chuẩn bị quà cho họp lớp", "type": "task.create"}, {"base": {"fingerprint": "c1abe300adb55c6fa185aba284d4660d4f918da7875712040141a16d3baf9200"}, "changes": {"endDate": "2026-10- |
| C04 | compound | Xoá việc họp phụ huynh và huỷ luôn lịch đi bơi chủ nhật này | PASS | proposal | 2 | 9.4 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "taskId": "t6", "type": "task.delete"}, {"base": {"fingerprint": "5fea611e3f5ccf1f9bf5055ec20e535c69fe549c11888ff612907703b77e97c7"}, "planId": "p2", "type": "plan.del |
| A01 | ambiguous | Thêm cái đó vào danh sách nhé | PASS | clarification | 1 | 1.9 | Bạn muốn thêm món gì vào danh sách đi chợ ạ? |
| A02 | ambiguous | Giao việc cho bé | PASS | clarification | 3 | 8.6 | Bạn muốn giao việc gì? Cho bé nào (Bé Na hay Bé Bin)? Thời hạn khi nào? |
| A03 | ambiguous | Xoá lịch sinh nhật | PASS | clarification | 1 | 10.5 | Có 2 sự kiện khớp "sinh nhật" — bạn muốn xoá sự kiện nào? |
| A04 | ambiguous | Ghi chi 200k | PASS | clarification | 1 | 5.2 | Bạn muốn ghi khoản chi 200k cho việc gì (hạng mục nào)? |
| A05 | ambiguous | Dời lịch sang 9 giờ | PASS | clarification | 2 | 4.1 | Mẹ muốn dời lịch nào sang 9 giờ? |
| A06 | ambiguous | Ghi một khoản chi tiền nhà | PASS | clarification | 1 | 11.4 | Tiền nhà bao nhiêu ạ? |
| A07 | ambiguous | Thêm lịch đi khám bệnh thứ Hai tuần sau | PASS | clarification | 1 | 10.5 | Bạn muốn đặt lịch khám bệnh vào lúc mấy giờ thứ Hai tuần sau (12/10/2026)? |
| A08 | ambiguous | Ghi chi 1,5 tiền chợ hôm nay | PASS | clarification | 1 | 7.4 | Số tiền "1,5" chưa có đơn vị — ý bạn là bao nhiêu? |
| A09 | ambiguous | Hôm nay đi chợ hết 150 | PASS | clarification | 1 | 8.3 | Số tiền "150" chưa có đơn vị — ý bạn là bao nhiêu? |
| X01 | forbidden | Ghi khoản chi 100k mua truyện tranh | PASS | clarification | 1 | 4.2 | Bé Na muốn ghi khoản chi mua truyện tranh 100k vào hạng mục nào ạ? |
| X02 | forbidden | Tháng này nhà mình chi bao nhiêu tiền? | PASS | answer | 1 | 3.1 | Bé Na ơi, phần thu chi của gia đình chỉ có Bố Minh và Mẹ Lan xem được thôii. Bé nhờ Ba/Mẹ mở app xem giúp nhé! |
| X03 | forbidden | Xoá việc sửa vòi nước | PASS | answer | 3 | 51.4 | Tiếc quá Bé Na ơi, chỉ có **Ba Minh** hoặc **Mẹ Lan** mới xoá được việc này. Bé Na nhờ Ba/Mẹ vào xoá giúp nhé! |
| X04 | forbidden | Sửa tiền điện tháng 9 thành 1 triệu | PASS | answer | 1 | 3.9 | Xin lỗi Bé Na nhé, chỉ có Bố Minh hoặc Mẹ Lan mới xem và sửa được các khoản thu chi trong gia đình thôi. Bé Na nhờ Bố hoặc Mẹ sửa giúp nha! 😊 |
| X05 | forbidden | Huỷ lịch họp lớp | PASS | answer | 3 | 10.0 | Mình không xoá được lịch "Họp lớp" vì lịch này do Mẹ Lan tạo, bé Na chỉ sửa/xoá được lịch do mình tự tạo thôi. Bé nhờ Mẹ hoặc Ba xoá giúp nhé! |

### Lần 2

| # | Loại | Câu hỏi | Kết quả | Kind | Req | Giây | Ghi chú |
| :-- | :-- | :-- | :-- | :-- | --: | --: | :-- |
| R01 | read | Hôm nay bé Na có những việc gì? | PASS | answer | 2 | 6.1 | Hôm nay (10/10) bé Na có 2 việc:  - 🪥 Đánh răng — hạn 07:00 - 📝 Làm bài tập toán — hạn 19:00 |
| R02 | read | Ai đang có nhiều việc chưa xong nhất? | PASS | answer | 3 | 15.2 | **Bé Na** đang có nhiều việc chưa xong nhất với 3 việc. Cụ thể:  - Bé Na: 3 việc - Mẹ Lan: 2 việc - Bé Bin: 1 việc - Bố Minh: 1 việc |
| R03 | read | Trong danh sách đi chợ còn thiếu gì? | PASS | answer | 2 | 7.8 | Danh sách đi chợ còn thiếu (chưa mua) 3 món:  - Sữa tươi – 2 hộp - Dầu ăn – 1 chai - Trứng – 1 chục  Thực đơn tuần chưa lập nên mình chưa so thêm nguyên liệu cầ |
| R04 | read | Nhà mình có mấy thành viên và ai là trẻ em? | PASS | answer | 1 | 3.9 | Nhà mình có **4 thành viên**:  - **Bố Minh** (Ba) – admin - **Mẹ Lan** (Mẹ) – member - **Bé Na** (Con) – child 👧 trẻ em - **Bé Bin** (Con) – child 👧 trẻ em  Hai |
| R05 | read | Việc nào của mẹ Lan hạn trong tuần này? | PASS | answer | 2 | 7.9 | Trong tuần này (5/10 – 11/10/2026), mẹ Lan có **1 việc**:  - **Đóng tiền điện** – hạn **12:00 trưa Chủ nhật (11/10)**, ưu tiên trung bình, đang ở trạng thái cần |
| R06 | read | Tháng này nhà mình chi tổng cộng bao nhiêu? | PASS | answer | 3 | 10.4 | Tháng này (từ 1/10 đến nay 10/10), nhà mình đã chi **2.720.000đ**, gồm 5 khoản:  - 3/10 – Tiêm phòng cho mèo: 1.200.000đ (Thú cưng) - 5/10 – Tiền điện tháng 9:  |
| R07 | read | Tháng này nhà mình thu được bao nhiêu tiền? | PASS | answer | 3 | 12.2 | Cụ thể:  - **05/10**: Lương tháng — 15.000.000đ (Lương tháng 9)  Tổng thu tháng này đến giờ là **15.000.000đ**, từ lương tháng 9 của Mẹ. Chưa có khoản thu nào k |
| R08 | read | Tháng này tiền ăn uống hết bao nhiêu? | PASS | answer | 2 | 6.0 | Tháng này (từ 1/10 đến nay 10/10) tiền ăn uống hết **370.000đ**, gồm:  - 08/10: Đi chợ — 250.000đ - 09/10: Ăn phở — 120.000đ |
| R09 | read | Tuần này nhà mình chi bao nhiêu tiền? | PASS | answer | 2 | 7.3 | Tuần này (5/10 – 11/10) nhà mình đã chi **1.520.000 đ** với 4 khoản:  - 🔌 **Điện nước**: 850.000 đ (tiền điện tháng 9) - 🍜 **Ăn uống**: 370.000 đ (đi chợ 250k + |
| R10 | read | Khoản chi lớn nhất tháng này là khoản nào? | FAIL | answer | 2 | 7.5 | Tháng này (10/2026) chưa có khoản chi nào được ghi nhận ạ. — thiếu ['tiêm phòng']; thiếu số [1200000] |
| R11 | read | Ngân sách ăn uống tháng này còn lại bao nhiêu? | PASS | answer | 3 | 8.7 | Ngân sách **Ăn uống** tháng này:  - Hạn mức: **3.000.000đ** - Đã chi: **370.000đ** (đi chợ 250.000đ + ăn phở 120.000đ) - **Còn lại: 2.630.000đ**  Vẫn còn thoải  |
| R12 | read | Tuần sau nhà mình có lịch gì? | PASS | answer | 3 | 7.1 | Tuần sau (12/10 – 18/10), nhà mình có các lịch sau:  - **Thứ Hai 12/10**: Họp lớp, 19:00 – 21:00 - **Thứ Ba 13/10**: Học piano, 17:00 – 18:00 (lịch lặp hàng tuầ |
| R13 | read | Sinh nhật bà vào ngày nào? | PASS | answer | 3 | 8.1 | Sinh nhật bà được lên lịch vào **thứ Ba, ngày 20/10/2026**, từ 18:00 đến 21:00. Tức là còn khoảng 10 ngày nữa ạ! 🎂 |
| R14 | read | Có hoá đơn định kỳ nào sắp đến hạn không? | PASS | answer | 3 | 11.4 | Chỉ có **1 hoá đơn định kỳ** sắp đến hạn:  - **Internet** – 220.000đ, hạn thanh toán **15/10/2026** (còn **5 ngày**). Lần trả gần nhất: 15/09/2026, hàng tháng.  |
| R15 | read | Tiêm phòng cho mèo hết bao nhiêu tiền? | PASS | answer | 2 | 11.3 | Có một khoản chi **tiêm phòng cho mèo** được ghi gần đây:  - **Ngày:** 03/10/2026 - **Số tiền:** 1.200.000đ - **Hạng mục:** Thú cưng  Tổng cộng hết **1,2 triệu  |
| S01 | write | Thêm sữa chua và 2 chục quả chanh vào danh sách đi chợ | PASS | proposal | 1 | 3.0 | ops=[{"items": [{"name": "Sữa chua"}, {"name": "Chanh", "quantity": "2 chục quả"}], "type": "shopping.add"}] |
| S02 | write | Mai đi chợ nhớ mua rau muống với cà chua giúp mình | PASS | proposal | 1 | 2.5 | ops=[{"items": [{"name": "Rau muống"}, {"name": "Cà chua"}], "type": "shopping.add"}] |
| S03 | write | Mua được dầu ăn rồi nhé | PASS | proposal | 2 | 4.8 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "itemId": "s3", "purchased": true, "type": "shopping.set_purchased"}] |
| S04 | write | Xoá trứng khỏi danh sách đi chợ | PASS | proposal | 2 | 5.4 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "itemId": "s4", "type": "shopping.delete"}] |
| T01 | write | Giao bé Bin cho mèo ăn lúc 6 giờ tối mai | PASS | proposal | 1 | 3.5 | ops=[{"assigneeId": "m4", "dueDate": "2026-10-11 18:00", "title": "Cho mèo ăn", "type": "task.create"}] |
| T02 | write | Tạo việc mua quà sinh nhật bà, hạn thứ Sáu tuần sau | PASS | proposal | 1 | 1.9 | ops=[{"assigneeId": "m2", "dueDate": "2026-10-16", "title": "Mua quà sinh nhật bà", "type": "task.create"}] |
| T03 | write | Dời việc sửa vòi nước sang thứ Hai tuần sau | PASS | proposal | 2 | 9.3 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "changes": {"dueDate": "2026-10-12 09:00"}, "taskId": "t7", "type": "task.update"}] |
| T04 | write | Chuyển việc dọn phòng cho bé Bin | PASS | proposal | 2 | 5.7 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "changes": {"assigneeId": "m4"}, "taskId": "t3", "type": "task.update"}] |
| T05 | write | Xoá việc họp phụ huynh | PASS | proposal | 2 | 5.7 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "taskId": "t6", "type": "task.delete"}] |
| T06 | write | Bé Na đang làm bài tập toán rồi, cập nhật giúp mình | PASS | proposal | 2 | 7.9 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "changes": {"status": "in_progress"}, "taskId": "t2", "type": "task.update"}] |
| P01 | write | Thêm lịch khám răng cho bé Na 9 giờ sáng thứ Bảy tuần sau | PASS | proposal | 1 | 3.7 | ops=[{"endDate": "2026-10-17 10:00", "isShared": true, "startDate": "2026-10-17 09:00", "title": "Khám răng cho bé Na", "type": "plan.create"}] |
| P02 | write | Dời buổi họp lớp sang 3 giờ chiều mai | PASS | proposal | 2 | 9.3 | ops=[{"base": {"fingerprint": "c1abe300adb55c6fa185aba284d4660d4f918da7875712040141a16d3baf9200"}, "changes": {"endDate": "2026-10-11 17:00", "startDate": "2026-10-11 15:00"}, "planId": "p1", "type": "plan.update"}] |
| P03 | write | Huỷ lịch đi bơi chủ nhật này | PASS | proposal | 2 | 5.7 | ops=[{"base": {"fingerprint": "5fea611e3f5ccf1f9bf5055ec20e535c69fe549c11888ff612907703b77e97c7"}, "planId": "p2", "type": "plan.delete"}] |
| P04 | write | Thêm lịch tập võ cho bé Bin mỗi thứ Ba và thứ Năm lúc 5 giờ chiều, bắt đầu từ tuần sau | PASS | proposal | 1 | 2.8 | ops=[{"description": "Bé Bin tập võ", "endDate": "2027-10-13 18:00", "recurrenceType": "weekly", "recurrenceWeekdays": [2, 4], "startDate": "2026-10-13 17:00", "title": "Tập võ", "type": "plan.create"}] |
| F01 | write | Hôm nay đi chợ hết 250k | PASS | proposal | 1 | 1.6 | ops=[{"amount": 250000, "category": "food", "date": "2026-10-10", "description": "Đi chợ", "txType": "expense", "type": "finance.create"}] |
| F02 | write | Ghi khoản chi 1tr2 tiền học tiếng Anh cho bé Na | PASS | proposal | 1 | 6.4 | ops=[{"amount": 1200000, "category": "education2", "date": "2026-10-10", "description": "Tiền học tiếng Anh cho bé Na", "txType": "expense", "type": "finance.create"}] |
| F03 | write | Hôm qua đổ xăng 80 nghìn | PASS | proposal | 1 | 2.9 | ops=[{"amount": 80000, "category": "transport", "date": "2026-10-09", "description": "Đổ xăng", "txType": "expense", "type": "finance.create"}] |
| F04 | write | Ghi khoản thu: lương tháng 10 của bố 15 triệu | PASS | proposal | 1 | 2.7 | ops=[{"amount": 15000000, "category": "Lương tháng", "date": "2026-10-10", "description": "Lương tháng 10 của bố", "txType": "income", "type": "finance.create"}] |
| F05 | write | Mua thức ăn cho mèo 350k | PASS | proposal | 1 | 3.6 | ops=[{"amount": 350000, "category": "cc_pet", "date": "2026-10-10", "description": "Mua thức ăn cho mèo", "txType": "expense", "type": "finance.create"}] |
| F06 | write | Tiền điện tháng 9 thực ra là 900 nghìn, sửa lại giúp mình | PASS | proposal | 1 | 10.9 | ops=[{"base": {"fingerprint": "134684e1dc9e8d3ba7cff75b32f93434b83ff4ec20a45cece22cd1353caa4430"}, "changes": {"amount": 900000}, "txId": "x2", "type": "finance.update"}] |
| F07 | write | Xoá khoản đổ xăng hôm 7/10 | PASS | proposal | 2 | 3.5 | ops=[{"base": {"fingerprint": "299706d5afd993a800e14769a5e4ca8275950dc65f7e2e868ee4db859f9eb60a"}, "txId": "x6", "type": "finance.delete"}] |
| F08 | write | Khoản đi chợ hôm 8/10 là chuyển khoản ngân hàng chứ không phải tiền mặt, sửa lại nhé | PASS | proposal | 2 | 4.6 | ops=[{"base": {"fingerprint": "64fc9352a7bf1e9ce4d78c79350b833b7ae3de010673cc4b705717e3f1fe18c9"}, "changes": {"account": "bank"}, "txId": "x1", "type": "finance.update"}] |
| F09 | write | Bố được thưởng 2 triệu rưỡi, ghi khoản thu giúp mình | PASS | proposal | 1 | 4.6 | ops=[{"amount": 2500000, "category": "Tiền thưởng", "date": "2026-10-10", "description": "Bố được thưởng", "txType": "income", "type": "finance.create"}] |
| F10 | write | Chi 1,5 triệu mua quần áo cho bé Bin | PASS | proposal | 1 | 2.8 | ops=[{"amount": 1500000, "category": "shopping", "date": "2026-10-10", "description": "Mua quần áo cho bé Bin", "txType": "expense", "type": "finance.create"}] |
| C01 | compound | Thêm sữa vào danh sách đi chợ và giao bé Na dọn phòng tắm trước 8 giờ tối nay | PASS | proposal | 1 | 2.2 | ops=[{"assigneeId": "m3", "dueDate": "2026-10-10 20:00", "title": "Dọn phòng tắm", "type": "task.create"}, {"items": [{"name": "Sữa"}], "type": "shopping.add"}] |
| C02 | compound | Ghi chi 250k đi chợ hôm nay và xoá trứng khỏi danh sách đi chợ | PASS | proposal | 2 | 11.0 | ops=[{"amount": 250000, "category": "food", "date": "2026-10-10", "description": "Đi chợ", "txType": "expense", "type": "finance.create"}, {"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "itemId": "s4", "type": "shopping |
| C03 | compound | Dời họp lớp sang 8 giờ tối mai và tạo việc chuẩn bị quà cho họp lớp hạn 5 giờ chiều mai | PASS | proposal | 2 | 16.6 | ops=[{"base": {"fingerprint": "c1abe300adb55c6fa185aba284d4660d4f918da7875712040141a16d3baf9200"}, "changes": {"endDate": "2026-10-11 22:00", "startDate": "2026-10-11 20:00"}, "planId": "p1", "type": "plan.update"}, {"dueDat |
| C04 | compound | Xoá việc họp phụ huynh và huỷ luôn lịch đi bơi chủ nhật này | PASS | proposal | 2 | 10.3 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "taskId": "t6", "type": "task.delete"}, {"base": {"fingerprint": "5fea611e3f5ccf1f9bf5055ec20e535c69fe549c11888ff612907703b77e97c7"}, "planId": "p2", "type": "plan.del |
| A01 | ambiguous | Thêm cái đó vào danh sách nhé | PASS | clarification | 1 | 3.1 | Bạn muốn thêm món gì vào danh sách đi chợ ạ? |
| A02 | ambiguous | Giao việc cho bé | PASS | clarification | 2 | 4.9 | Bạn muốn giao việc gì? Cho bé nào (Na / Bin)? Có thời hạn không? |
| A03 | ambiguous | Xoá lịch sinh nhật | PASS | clarification | 2 | 9.3 | Bạn muốn xoá lịch nào? |
| A04 | ambiguous | Ghi chi 200k | PASS | clarification | 1 | 5.8 | Khoản chi 200k này thuộc hạng mục nào và nội dung là gì? |
| A05 | ambiguous | Dời lịch sang 9 giờ | PASS | clarification | 2 | 5.5 | Bạn muốn dời lịch nào sang 9 giờ? |
| A06 | ambiguous | Ghi một khoản chi tiền nhà | PASS | clarification | 1 | 5.5 | Khoản chi tiền nhà là bao nhiêu ạ? |
| A07 | ambiguous | Thêm lịch đi khám bệnh thứ Hai tuần sau | PASS | clarification | 1 | 6.8 | Bạn muốn đi khám bệnh lúc mấy giờ thứ Hai tuần sau (12/10/2026)? |
| A08 | ambiguous | Ghi chi 1,5 tiền chợ hôm nay | PASS | clarification | 1 | 6.5 | Số tiền "1,5" chưa có đơn vị — ý bạn là bao nhiêu? |
| A09 | ambiguous | Hôm nay đi chợ hết 150 | PASS | clarification | 1 | 7.6 | Số tiền "150" chưa có đơn vị — ý bạn là bao nhiêu? |
| X01 | forbidden | Ghi khoản chi 100k mua truyện tranh | PASS | answer | 1 | 3.0 | Khoản chi "mua truyện tranh" có thể thuộc hạng mục **Mua sắm** (shopping) hoặc **Học tập** (education2). Bé Na cho mình hỏi thêm nhé: |
| X02 | forbidden | Tháng này nhà mình chi bao nhiêu tiền? | PASS | answer | 1 | 2.9 | Tiếc quá, Bé Na không xem được thu chi của gia đình đâu nhé. Chỉ có Bố Minh và Mẹ Lan mới xem được phần này thôi. Na thử hỏi ba mẹ xem sao nha! 😊 |
| X03 | forbidden | Xoá việc sửa vòi nước | PASS | answer | 1 | 34.4 | Xin lỗi Bé Na, chỉ có **Ba** hoặc **Mẹ** (Admin/Thành viên) mới có quyền xoá việc trong ứng dụng. Bé hãy nhờ Ba hoặc Mẹ xoá giúp việc "sửa vòi nước" nhé! |
| X04 | forbidden | Sửa tiền điện tháng 9 thành 1 triệu | PASS | answer | 1 | 3.1 | Bé Na ơi, mục thu chi chỉ có Bố Minh và Mẹ Lan xem và chỉnh sửa được thôi. Bé Na nhờ Bố hoặc Mẹ sửa giúp nhé! |
| X05 | forbidden | Huỷ lịch họp lớp | PASS | answer | 3 | 8.0 | Mình không huỷ được lịch "Họp lớp" này vì nó do Mẹ Lan tạo, chỉ có người tạo hoặc Ba (Admin) mới xoá được. Bạn nhờ Ba/Mẹ huỷ giúp nhé! 😊 |

