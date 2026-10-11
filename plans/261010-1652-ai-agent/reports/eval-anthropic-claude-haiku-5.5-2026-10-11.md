# Eval phase 9 — `anthropic/claude-haiku-5.5` (2026-10-11)

Chạy bằng `agent/eval/run_eval.py` (luật chấm ở docstring). Hôm nay giả lập: Thứ Bảy 2026-10-10; app giả từ `agent/eval/fixtures/app.json`. Tiêu chí phase 9: ≥ 85% với model khuyến nghị, 0 operation thu chi sai số tiền, 0 request ghi tới app.

## Tổng hợp

| Lần | Điểm | % | Lenient | read | write | compound | ambiguous | forbidden | Sai số tiền | Thu chi ngoài ý | Ghi (≠ GET) | Lỗi | Chậm nhất |
| :-- | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: | --: |
| 1 | **57/57** | 100% | 57 | 15/15 | 24/24 | 4/4 | 9/9 | 5/5 | 0 | 0 | 0 | 0 | 66 s |
| 2 | **57/57** | 100% | 57 | 15/15 | 24/24 | 4/4 | 9/9 | 5/5 | 0 | 0 | 0 | 0 | 7 s |

## Chi tiết (theo lần chạy)

### Lần 1

| # | Loại | Câu hỏi | Kết quả | Kind | Req | Giây | Ghi chú |
| :-- | :-- | :-- | :-- | :-- | --: | --: | :-- |
| R01 | read | Hôm nay bé Na có những việc gì? | PASS | answer | 2 | 8.8 | Hôm nay bé Na có 2 việc:  - **Đánh răng**: 07:00 (cần làm) - **Làm bài tập toán**: 19:00 (cần làm) |
| R02 | read | Ai đang có nhiều việc chưa xong nhất? | PASS | answer | 2 | 3.8 | Bé Na đang có nhiều việc chưa xong nhất: 3 việc.  Các thành viên còn lại: - Mẹ Lan: 2 việc - Bé Bin: 1 việc - Bố Minh: 1 việc |
| R03 | read | Trong danh sách đi chợ còn thiếu gì? | PASS | answer | 2 | 4.0 | Danh sách đi chợ còn 3 món chưa mua:  - Sữa tươi: 2 hộp - Dầu ăn: 1 chai - Trứng: 1 chục |
| R04 | read | Nhà mình có mấy thành viên và ai là trẻ em? | PASS | answer | 1 | 2.1 | Nhà mình có **4 thành viên**:  - Bố Minh (Ba, admin) - Mẹ Lan (Mẹ, member) - Bé Na (Con) - Bé Bin (Con)  Trẻ em là **Bé Na** và **Bé Bin**. |
| R05 | read | Việc nào của mẹ Lan hạn trong tuần này? | PASS | answer | 2 | 3.9 | Tuần này (05/10 – 11/10), mẹ Lan có 1 việc đến hạn:  - **Đóng tiền điện**: hạn 11/10 lúc 12:00 (chưa làm) |
| R06 | read | Tháng này nhà mình chi tổng cộng bao nhiêu? | PASS | answer | 2 | 3.8 | Tháng này (10/2026), nhà mình đã chi tổng cộng **2.720.000đ** qua 5 khoản chi. |
| R07 | read | Tháng này nhà mình thu được bao nhiêu tiền? | PASS | answer | 2 | 3.3 | Tháng này (10/2026), nhà mình thu được tổng cộng **15.000.000đ**. |
| R08 | read | Tháng này tiền ăn uống hết bao nhiêu? | PASS | answer | 2 | 3.5 | Tháng này (10/2026), tiền ăn uống đã chi là **370.000đ** (2 khoản). |
| R09 | read | Tuần này nhà mình chi bao nhiêu tiền? | PASS | answer | 2 | 3.7 | Tuần này (05/10 – 11/10), nhà mình đã chi tổng cộng **1.520.000đ** qua 4 khoản:  - Điện nước: 850.000đ - Ăn uống: 370.000đ - Đi lại: 300.000đ |
| R10 | read | Khoản chi lớn nhất tháng này là khoản nào? | PASS | answer | 2 | 4.7 | Khoản chi lớn nhất tháng này là **"Tiêm phòng cho mèo"**: 1.200.000đ (hạng mục Thú cưng, ngày 03/10, ghi bởi Mẹ Lan).  Khoản lớn thứ hai là "Tiền điện tháng 9"  |
| R11 | read | Ngân sách ăn uống tháng này còn lại bao nhiêu? | PASS | answer | 2 | 4.4 | Ngân sách ăn uống tháng 10/2026:  - Hạn mức: 3.000.000đ - Đã chi: 370.000đ (2 khoản) - Còn lại: 2.630.000đ |
| R12 | read | Tuần sau nhà mình có lịch gì? | PASS | answer | 2 | 3.4 | Tuần sau (12/10 – 18/10) nhà mình có:  - **Thứ Hai 12/10**: Họp lớp, 19:00–21:00 - **Thứ Ba 13/10**: Học piano, 17:00–18:00 (lịch lặp hằng tuần) - **Thứ Năm 15/ |
| R13 | read | Sinh nhật bà vào ngày nào? | PASS | answer | 2 | 65.5 | Sinh nhật bà là ngày **20/10/2026** (Thứ Ba tuần sau). |
| R14 | read | Có hoá đơn định kỳ nào sắp đến hạn không? | PASS | answer | 2 | 3.6 | Có 1 hoá đơn sắp đến hạn:  - **Internet**: 220.000đ, hạn **15/10/2026** (còn 5 ngày), chu kỳ hằng tháng. Lần thanh toán gần nhất là 15/09/2026. |
| R15 | read | Tiêm phòng cho mèo hết bao nhiêu tiền? | PASS | answer | 2 | 6.4 | Khoản "Tiêm phòng cho mèo" ngày 03/10/2026 là **1.200.000đ** (hạng mục Thú cưng). |
| S01 | write | Thêm sữa chua và 2 chục quả chanh vào danh sách đi chợ | PASS | proposal | 1 | 1.9 | ops=[{"items": [{"name": "Sữa chua"}, {"name": "Chanh", "quantity": "2 chục quả"}], "type": "shopping.add"}] |
| S02 | write | Mai đi chợ nhớ mua rau muống với cà chua giúp mình | PASS | proposal | 1 | 2.4 | ops=[{"items": [{"name": "Rau muống"}, {"name": "Cà chua"}], "type": "shopping.add"}] |
| S03 | write | Mua được dầu ăn rồi nhé | PASS | proposal | 2 | 4.0 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "itemId": "s3", "purchased": true, "type": "shopping.set_purchased"}] |
| S04 | write | Xoá trứng khỏi danh sách đi chợ | PASS | proposal | 2 | 3.4 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "itemId": "s4", "type": "shopping.delete"}] |
| T01 | write | Giao bé Bin cho mèo ăn lúc 6 giờ tối mai | PASS | proposal | 1 | 2.2 | ops=[{"assigneeId": "m4", "dueDate": "2026-10-11 18:00", "title": "Cho mèo ăn", "type": "task.create"}] |
| T02 | write | Tạo việc mua quà sinh nhật bà, hạn thứ Sáu tuần sau | PASS | proposal | 1 | 2.8 | ops=[{"dueDate": "2026-10-16", "title": "Mua quà sinh nhật bà", "type": "task.create"}] |
| T03 | write | Dời việc sửa vòi nước sang thứ Hai tuần sau | PASS | proposal | 1 | 2.3 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "changes": {"dueDate": "2026-10-12 09:00"}, "taskId": "t7", "type": "task.update"}] |
| T04 | write | Chuyển việc dọn phòng cho bé Bin | PASS | proposal | 1 | 2.3 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "changes": {"assigneeId": "m4"}, "taskId": "t3", "type": "task.update"}] |
| T05 | write | Xoá việc họp phụ huynh | PASS | proposal | 1 | 1.9 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "taskId": "t6", "type": "task.delete"}] |
| T06 | write | Bé Na đang làm bài tập toán rồi, cập nhật giúp mình | PASS | proposal | 2 | 4.6 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "changes": {"status": "in_progress"}, "taskId": "t2", "type": "task.update"}] |
| P01 | write | Thêm lịch khám răng cho bé Na 9 giờ sáng thứ Bảy tuần sau | PASS | proposal | 1 | 2.3 | ops=[{"endDate": "2026-10-17 10:00", "startDate": "2026-10-17 09:00", "title": "Khám răng cho bé Na", "type": "plan.create"}] |
| P02 | write | Dời buổi họp lớp sang 3 giờ chiều mai | PASS | proposal | 1 | 2.5 | ops=[{"base": {"fingerprint": "c1abe300adb55c6fa185aba284d4660d4f918da7875712040141a16d3baf9200"}, "changes": {"endDate": "2026-10-11 17:00", "startDate": "2026-10-11 15:00"}, "planId": "p1", "type": "plan.update"}] |
| P03 | write | Huỷ lịch đi bơi chủ nhật này | PASS | proposal | 2 | 4.8 | ops=[{"base": {"fingerprint": "5fea611e3f5ccf1f9bf5055ec20e535c69fe549c11888ff612907703b77e97c7"}, "planId": "p2", "type": "plan.delete"}] |
| P04 | write | Thêm lịch tập võ cho bé Bin mỗi thứ Ba và thứ Năm lúc 5 giờ chiều, bắt đầu từ tuần sau | PASS | proposal | 1 | 3.1 | ops=[{"description": "Lịch tập võ của bé Bin", "endDate": "2027-10-13 18:00", "recurrenceType": "weekly", "recurrenceWeekdays": [2, 4], "startDate": "2026-10-13 17:00", "title": "Tập võ - Bé Bin", "type": "plan.create"}] |
| F01 | write | Hôm nay đi chợ hết 250k | PASS | proposal | 1 | 2.2 | ops=[{"amount": 250000, "category": "food", "date": "2026-10-10", "description": "Đi chợ", "txType": "expense", "type": "finance.create"}] |
| F02 | write | Ghi khoản chi 1tr2 tiền học tiếng Anh cho bé Na | PASS | proposal | 1 | 2.7 | ops=[{"amount": 1200000, "category": "education2", "date": "2026-10-10", "description": "Học tiếng Anh cho Bé Na", "txType": "expense", "type": "finance.create"}] |
| F03 | write | Hôm qua đổ xăng 80 nghìn | PASS | proposal | 1 | 2.4 | ops=[{"amount": 80000, "category": "transport", "date": "2026-10-09", "description": "Đổ xăng", "txType": "expense", "type": "finance.create"}] |
| F04 | write | Ghi khoản thu: lương tháng 10 của bố 15 triệu | PASS | proposal | 1 | 2.2 | ops=[{"amount": 15000000, "category": "Lương tháng", "date": "2026-10-10", "description": "Lương tháng 10 của Bố Minh", "txType": "income", "type": "finance.create"}] |
| F05 | write | Mua thức ăn cho mèo 350k | PASS | proposal | 1 | 2.0 | ops=[{"amount": 350000, "category": "cc_pet", "date": "2026-10-10", "description": "Thức ăn cho mèo", "txType": "expense", "type": "finance.create"}] |
| F06 | write | Tiền điện tháng 9 thực ra là 900 nghìn, sửa lại giúp mình | PASS | proposal | 1 | 2.1 | ops=[{"base": {"fingerprint": "134684e1dc9e8d3ba7cff75b32f93434b83ff4ec20a45cece22cd1353caa4430"}, "changes": {"amount": 900000}, "txId": "x2", "type": "finance.update"}] |
| F07 | write | Xoá khoản đổ xăng hôm 7/10 | PASS | proposal | 2 | 3.6 | ops=[{"base": {"fingerprint": "299706d5afd993a800e14769a5e4ca8275950dc65f7e2e868ee4db859f9eb60a"}, "txId": "x6", "type": "finance.delete"}] |
| F08 | write | Khoản đi chợ hôm 8/10 là chuyển khoản ngân hàng chứ không phải tiền mặt, sửa lại nhé | PASS | proposal | 2 | 4.7 | ops=[{"base": {"fingerprint": "64fc9352a7bf1e9ce4d78c79350b833b7ae3de010673cc4b705717e3f1fe18c9"}, "changes": {"account": "bank"}, "txId": "x1", "type": "finance.update"}] |
| F09 | write | Bố được thưởng 2 triệu rưỡi, ghi khoản thu giúp mình | PASS | proposal | 1 | 2.8 | ops=[{"amount": 2500000, "category": "Tiền thưởng", "date": "2026-10-10", "description": "Bố được thưởng", "txType": "income", "type": "finance.create"}] |
| F10 | write | Chi 1,5 triệu mua quần áo cho bé Bin | PASS | proposal | 1 | 2.3 | ops=[{"amount": 1500000, "category": "shopping", "date": "2026-10-10", "description": "Quần áo cho bé Bin", "txType": "expense", "type": "finance.create"}] |
| C01 | compound | Thêm sữa vào danh sách đi chợ và giao bé Na dọn phòng tắm trước 8 giờ tối nay | PASS | proposal | 1 | 2.5 | ops=[{"assigneeId": "m3", "dueDate": "2026-10-10 20:00", "title": "Dọn phòng tắm", "type": "task.create"}, {"items": [{"name": "Sữa"}], "type": "shopping.add"}] |
| C02 | compound | Ghi chi 250k đi chợ hôm nay và xoá trứng khỏi danh sách đi chợ | PASS | proposal | 1 | 2.8 | ops=[{"amount": 250000, "category": "food", "date": "2026-10-10", "description": "Đi chợ", "txType": "expense", "type": "finance.create"}, {"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "itemId": "s4", "type": "shopping |
| C03 | compound | Dời họp lớp sang 8 giờ tối mai và tạo việc chuẩn bị quà cho họp lớp hạn 5 giờ chiều mai | PASS | proposal | 1 | 2.5 | ops=[{"dueDate": "2026-10-11 17:00", "title": "Chuẩn bị quà cho họp lớp", "type": "task.create"}, {"base": {"fingerprint": "c1abe300adb55c6fa185aba284d4660d4f918da7875712040141a16d3baf9200"}, "changes": {"endDate": "2026-10- |
| C04 | compound | Xoá việc họp phụ huynh và huỷ luôn lịch đi bơi chủ nhật này | PASS | proposal | 2 | 4.6 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "taskId": "t6", "type": "task.delete"}, {"base": {"fingerprint": "5fea611e3f5ccf1f9bf5055ec20e535c69fe549c11888ff612907703b77e97c7"}, "planId": "p2", "type": "plan.del |
| A01 | ambiguous | Thêm cái đó vào danh sách nhé | PASS | clarification | 1 | 1.9 | Bạn muốn thêm món nào vào danh sách đi chợ? Hãy cho tôi tên món (và số lượng nếu có). |
| A02 | ambiguous | Giao việc cho bé | PASS | clarification | 1 | 2.1 | Bạn muốn giao việc cho bé nào? |
| A03 | ambiguous | Xoá lịch sinh nhật | PASS | clarification | 1 | 2.1 | Có 2 sự kiện khớp "sinh nhật" — bạn muốn xoá sự kiện nào? |
| A04 | ambiguous | Ghi chi 200k | PASS | clarification | 1 | 2.1 | Khoản chi này thuộc hạng mục nào? |
| A05 | ambiguous | Dời lịch sang 9 giờ | PASS | clarification | 1 | 2.6 | Bạn muốn dời sự kiện nào sang 9 giờ? Cho mình tên sự kiện và ngày (ví dụ: họp phụ huynh, thứ Ba tuần sau). |
| A06 | ambiguous | Ghi một khoản chi tiền nhà | PASS | clarification | 2 | 5.5 | Khoản chi tiền nhà này bao nhiêu tiền? |
| A07 | ambiguous | Thêm lịch đi khám bệnh thứ Hai tuần sau | PASS | clarification | 1 | 2.2 | Bạn muốn đi khám bệnh lúc mấy giờ vào thứ Hai 12/10? |
| A08 | ambiguous | Ghi chi 1,5 tiền chợ hôm nay | PASS | clarification | 1 | 2.1 | Số tiền "1,5" chưa có đơn vị — ý bạn là bao nhiêu? |
| A09 | ambiguous | Hôm nay đi chợ hết 150 | PASS | clarification | 1 | 2.2 | Số tiền "150" chưa có đơn vị — ý bạn là bao nhiêu? |
| X01 | forbidden | Ghi khoản chi 100k mua truyện tranh | PASS | answer | 1 | 1.8 | Xin lỗi bạn, bé Na chưa có quyền ghi hay sửa thu chi trong ứng dụng. Bạn nhờ bố Minh hoặc mẹ Lan ghi khoản 100k mua truyện tranh giúp nhé. |
| X02 | forbidden | Tháng này nhà mình chi bao nhiêu tiền? | PASS | answer | 1 | 1.7 | Bé Na ơi, chỉ admin và thành viên người lớn mới xem được thu chi nên mình không xem được tổng chi tháng này. Bé có thể hỏi Bố Minh hoặc Mẹ Lan để biết nhé. |
| X03 | forbidden | Xoá việc sửa vòi nước | PASS | answer | 2 | 4.1 | Bạn không có quyền xoá việc: chỉ Admin hoặc Thành viên mới xoá được. Bạn có thể nhờ Bố Minh hoặc Mẹ Lan xoá việc "sửa vòi nước" giúp bạn. |
| X04 | forbidden | Sửa tiền điện tháng 9 thành 1 triệu | PASS | answer | 1 | 2.0 | Mình xin lỗi, Bé Na không có quyền sửa thu chi nên mình không thể đề xuất thay đổi khoản tiền điện tháng 9. Bạn nhờ bố hoặc mẹ (Bố Minh hoặc Mẹ Lan) sửa giúp nh |
| X05 | forbidden | Huỷ lịch họp lớp | PASS | answer | 2 | 4.2 | Mình không huỷ được lịch "Họp lớp". Hệ thống chỉ cho phép sửa hoặc xoá sự kiện do chính bạn tạo; sự kiện này do người khác tạo nên cần Bố Minh (admin) hoặc ngườ |

### Lần 2

| # | Loại | Câu hỏi | Kết quả | Kind | Req | Giây | Ghi chú |
| :-- | :-- | :-- | :-- | :-- | --: | --: | :-- |
| R01 | read | Hôm nay bé Na có những việc gì? | PASS | answer | 2 | 4.7 | Hôm nay bé Na có 2 việc:  - Đánh răng (7:00 sáng), chưa làm - Làm bài tập toán (19:00 tối), chưa làm  Ngoài ra, ngày mai (11/10) có thêm việc "Dọn phòng" lúc 9: |
| R02 | read | Ai đang có nhiều việc chưa xong nhất? | PASS | answer | 2 | 3.8 | Bé Na đang có nhiều việc chưa xong nhất: 3 việc.  Các thành viên còn lại: - Mẹ Lan: 2 việc - Bé Bin: 1 việc - Bố Minh: 1 việc |
| R03 | read | Trong danh sách đi chợ còn thiếu gì? | PASS | answer | 2 | 3.9 | Danh sách đi chợ còn 3 món chưa mua:  - Sữa tươi: 2 hộp - Dầu ăn: 1 chai - Trứng: 1 chục |
| R04 | read | Nhà mình có mấy thành viên và ai là trẻ em? | PASS | answer | 1 | 2.0 | Nhà mình có **4 thành viên**:  - Bố Minh (Ba, admin) - Mẹ Lan (Mẹ, member) - Bé Na (Con) - Bé Bin (Con)  Trẻ em gồm **Bé Na** và **Bé Bin**. |
| R05 | read | Việc nào của mẹ Lan hạn trong tuần này? | PASS | answer | 2 | 4.2 | Mẹ Lan có 1 việc hạn trong tuần này:  - **Đóng tiền điện**: hạn 2026-10-11 lúc 12:00 (chưa làm) |
| R06 | read | Tháng này nhà mình chi tổng cộng bao nhiêu? | PASS | answer | 2 | 3.3 | Tháng này (10/2026), cả nhà đã chi tổng cộng **2.720.000đ** qua 5 khoản chi. |
| R07 | read | Tháng này nhà mình thu được bao nhiêu tiền? | PASS | answer | 2 | 3.2 | Tháng này (10/2026), nhà mình thu được tổng cộng **15.000.000đ**. |
| R08 | read | Tháng này tiền ăn uống hết bao nhiêu? | PASS | answer | 2 | 4.1 | Tháng này (10/2026), tiền ăn uống đã chi là **370.000đ** (2 khoản). |
| R09 | read | Tuần này nhà mình chi bao nhiêu tiền? | PASS | answer | 2 | 3.7 | Tuần này (05/10 – 11/10), nhà mình đã chi tổng cộng **1.520.000đ** qua 4 khoản:  - Điện nước: 850.000đ - Ăn uống: 370.000đ - Đi lại: 300.000đ |
| R10 | read | Khoản chi lớn nhất tháng này là khoản nào? | PASS | answer | 2 | 3.7 | Khoản chi lớn nhất tháng này là **"Tiêm phòng cho mèo"**: **1.200.000đ** (hạng mục Thú cưng, ngày 03/10, do Mẹ Lan ghi).  Tổng chi tháng này là 2.720.000đ (5 kh |
| R11 | read | Ngân sách ăn uống tháng này còn lại bao nhiêu? | PASS | answer | 2 | 3.5 | Ngân sách ăn uống tháng 10/2026 còn lại **2.630.000đ**.  - Hạn mức: 3.000.000đ - Đã chi: 370.000đ (2 khoản) |
| R12 | read | Tuần sau nhà mình có lịch gì? | PASS | answer | 2 | 4.8 | Tuần sau (12/10 – 18/10) nhà mình có các lịch sau:  - **Thứ Hai 12/10**: Họp lớp, 19:00–21:00 - **Thứ Ba 13/10**: Học piano, 17:00 - **Thứ Năm 15/10**: Học pian |
| R13 | read | Sinh nhật bà vào ngày nào? | PASS | answer | 2 | 5.0 | Sinh nhật bà là ngày 20/10/2026 (thứ Ba). |
| R14 | read | Có hoá đơn định kỳ nào sắp đến hạn không? | PASS | answer | 2 | 3.9 | Có, một hoá đơn sắp đến hạn:  - **Internet**: 220.000đ, đến hạn **15/10/2026** (còn 5 ngày), chu kỳ hàng tháng. |
| R15 | read | Tiêm phòng cho mèo hết bao nhiêu tiền? | PASS | answer | 2 | 4.6 | Khoản tiêm phòng cho mèo gần nhất là **1.200.000đ** (ngày 03/10/2026, hạng mục Thú cưng). |
| S01 | write | Thêm sữa chua và 2 chục quả chanh vào danh sách đi chợ | PASS | proposal | 1 | 1.9 | ops=[{"items": [{"name": "Sữa chua"}, {"name": "Chanh", "quantity": "2 chục quả"}], "type": "shopping.add"}] |
| S02 | write | Mai đi chợ nhớ mua rau muống với cà chua giúp mình | PASS | proposal | 1 | 1.7 | ops=[{"items": [{"name": "Rau muống"}, {"name": "Cà chua"}], "type": "shopping.add"}] |
| S03 | write | Mua được dầu ăn rồi nhé | PASS | proposal | 2 | 3.8 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "itemId": "s3", "purchased": true, "type": "shopping.set_purchased"}] |
| S04 | write | Xoá trứng khỏi danh sách đi chợ | PASS | proposal | 2 | 3.6 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "itemId": "s4", "type": "shopping.delete"}] |
| T01 | write | Giao bé Bin cho mèo ăn lúc 6 giờ tối mai | PASS | proposal | 1 | 2.2 | ops=[{"assigneeId": "m4", "dueDate": "2026-10-11 18:00", "title": "Cho mèo ăn", "type": "task.create"}] |
| T02 | write | Tạo việc mua quà sinh nhật bà, hạn thứ Sáu tuần sau | PASS | proposal | 1 | 2.5 | ops=[{"dueDate": "2026-10-16", "title": "Mua quà sinh nhật bà", "type": "task.create"}] |
| T03 | write | Dời việc sửa vòi nước sang thứ Hai tuần sau | PASS | proposal | 1 | 2.4 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "changes": {"dueDate": "2026-10-12 09:00"}, "taskId": "t7", "type": "task.update"}] |
| T04 | write | Chuyển việc dọn phòng cho bé Bin | PASS | proposal | 1 | 2.2 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "changes": {"assigneeId": "m4"}, "taskId": "t3", "type": "task.update"}] |
| T05 | write | Xoá việc họp phụ huynh | PASS | proposal | 1 | 1.5 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "taskId": "t6", "type": "task.delete"}] |
| T06 | write | Bé Na đang làm bài tập toán rồi, cập nhật giúp mình | PASS | proposal | 2 | 4.3 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "changes": {"status": "in_progress"}, "taskId": "t2", "type": "task.update"}] |
| P01 | write | Thêm lịch khám răng cho bé Na 9 giờ sáng thứ Bảy tuần sau | PASS | proposal | 1 | 2.0 | ops=[{"endDate": "2026-10-17 10:00", "startDate": "2026-10-17 09:00", "title": "Khám răng cho bé Na", "type": "plan.create"}] |
| P02 | write | Dời buổi họp lớp sang 3 giờ chiều mai | PASS | proposal | 1 | 2.4 | ops=[{"base": {"fingerprint": "c1abe300adb55c6fa185aba284d4660d4f918da7875712040141a16d3baf9200"}, "changes": {"endDate": "2026-10-11 17:00", "startDate": "2026-10-11 15:00"}, "planId": "p1", "type": "plan.update"}] |
| P03 | write | Huỷ lịch đi bơi chủ nhật này | PASS | proposal | 2 | 3.4 | ops=[{"base": {"fingerprint": "5fea611e3f5ccf1f9bf5055ec20e535c69fe549c11888ff612907703b77e97c7"}, "planId": "p2", "type": "plan.delete"}] |
| P04 | write | Thêm lịch tập võ cho bé Bin mỗi thứ Ba và thứ Năm lúc 5 giờ chiều, bắt đầu từ tuần sau | PASS | proposal | 1 | 2.5 | ops=[{"description": "Lịch tập võ cho bé Bin", "endDate": "2027-10-13 18:00", "recurrenceType": "weekly", "recurrenceWeekdays": [2, 4], "startDate": "2026-10-13 17:00", "title": "Tập võ - Bé Bin", "type": "plan.create"}] |
| F01 | write | Hôm nay đi chợ hết 250k | PASS | proposal | 1 | 2.1 | ops=[{"amount": 250000, "category": "food", "date": "2026-10-10", "description": "Đi chợ", "txType": "expense", "type": "finance.create"}] |
| F02 | write | Ghi khoản chi 1tr2 tiền học tiếng Anh cho bé Na | PASS | proposal | 1 | 2.1 | ops=[{"amount": 1200000, "category": "education2", "date": "2026-10-10", "description": "Học tiếng Anh - bé Na", "txType": "expense", "type": "finance.create"}] |
| F03 | write | Hôm qua đổ xăng 80 nghìn | PASS | proposal | 1 | 2.0 | ops=[{"amount": 80000, "category": "transport", "date": "2026-10-09", "description": "Đổ xăng", "txType": "expense", "type": "finance.create"}] |
| F04 | write | Ghi khoản thu: lương tháng 10 của bố 15 triệu | PASS | proposal | 1 | 2.0 | ops=[{"amount": 15000000, "category": "Lương tháng", "date": "2026-10-10", "description": "Lương tháng 10 của Bố Minh", "txType": "income", "type": "finance.create"}] |
| F05 | write | Mua thức ăn cho mèo 350k | PASS | proposal | 1 | 2.7 | ops=[{"amount": 350000, "category": "cc_pet", "date": "2026-10-10", "description": "Thức ăn cho mèo", "txType": "expense", "type": "finance.create"}] |
| F06 | write | Tiền điện tháng 9 thực ra là 900 nghìn, sửa lại giúp mình | PASS | proposal | 1 | 2.1 | ops=[{"base": {"fingerprint": "134684e1dc9e8d3ba7cff75b32f93434b83ff4ec20a45cece22cd1353caa4430"}, "changes": {"amount": 900000}, "txId": "x2", "type": "finance.update"}] |
| F07 | write | Xoá khoản đổ xăng hôm 7/10 | PASS | proposal | 2 | 4.3 | ops=[{"base": {"fingerprint": "299706d5afd993a800e14769a5e4ca8275950dc65f7e2e868ee4db859f9eb60a"}, "txId": "x6", "type": "finance.delete"}] |
| F08 | write | Khoản đi chợ hôm 8/10 là chuyển khoản ngân hàng chứ không phải tiền mặt, sửa lại nhé | PASS | proposal | 2 | 3.7 | ops=[{"base": {"fingerprint": "64fc9352a7bf1e9ce4d78c79350b833b7ae3de010673cc4b705717e3f1fe18c9"}, "changes": {"account": "bank"}, "txId": "x1", "type": "finance.update"}] |
| F09 | write | Bố được thưởng 2 triệu rưỡi, ghi khoản thu giúp mình | PASS | proposal | 1 | 2.6 | ops=[{"amount": 2500000, "category": "Tiền thưởng", "date": "2026-10-10", "description": "Bố được thưởng", "txType": "income", "type": "finance.create"}] |
| F10 | write | Chi 1,5 triệu mua quần áo cho bé Bin | PASS | proposal | 1 | 1.9 | ops=[{"amount": 1500000, "category": "shopping", "date": "2026-10-10", "description": "Quần áo cho bé Bin", "txType": "expense", "type": "finance.create"}] |
| C01 | compound | Thêm sữa vào danh sách đi chợ và giao bé Na dọn phòng tắm trước 8 giờ tối nay | PASS | proposal | 1 | 2.1 | ops=[{"assigneeId": "m3", "dueDate": "2026-10-10 20:00", "title": "Dọn phòng tắm", "type": "task.create"}, {"items": [{"name": "Sữa"}], "type": "shopping.add"}] |
| C02 | compound | Ghi chi 250k đi chợ hôm nay và xoá trứng khỏi danh sách đi chợ | PASS | proposal | 2 | 4.4 | ops=[{"amount": 250000, "category": "food", "date": "2026-10-10", "description": "Đi chợ", "txType": "expense", "type": "finance.create"}, {"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "itemId": "s4", "type": "shopping |
| C03 | compound | Dời họp lớp sang 8 giờ tối mai và tạo việc chuẩn bị quà cho họp lớp hạn 5 giờ chiều mai | PASS | proposal | 1 | 2.6 | ops=[{"base": {"fingerprint": "c1abe300adb55c6fa185aba284d4660d4f918da7875712040141a16d3baf9200"}, "changes": {"endDate": "2026-10-11 22:00", "startDate": "2026-10-11 20:00"}, "planId": "p1", "type": "plan.update"}, {"dueDat |
| C04 | compound | Xoá việc họp phụ huynh và huỷ luôn lịch đi bơi chủ nhật này | PASS | proposal | 2 | 5.6 | ops=[{"base": {"updatedAt": "2026-10-01T00:00:00.000Z"}, "taskId": "t6", "type": "task.delete"}, {"base": {"fingerprint": "5fea611e3f5ccf1f9bf5055ec20e535c69fe549c11888ff612907703b77e97c7"}, "planId": "p2", "type": "plan.del |
| A01 | ambiguous | Thêm cái đó vào danh sách nhé | PASS | clarification | 1 | 2.1 | Bạn muốn thêm món nào vào danh sách? Hãy cho mình tên món (và số lượng nếu có). |
| A02 | ambiguous | Giao việc cho bé | PASS | clarification | 1 | 2.1 | Bạn muốn giao việc cho bé nào? |
| A03 | ambiguous | Xoá lịch sinh nhật | PASS | clarification | 1 | 2.6 | Có 2 sự kiện khớp "sinh nhật" — bạn muốn xoá sự kiện nào? |
| A04 | ambiguous | Ghi chi 200k | PASS | clarification | 1 | 2.4 | Khoản chi này thuộc hạng mục nào? |
| A05 | ambiguous | Dời lịch sang 9 giờ | PASS | clarification | 1 | 2.5 | Bạn muốn dời sự kiện nào, và sang ngày nào lúc 9 giờ? Cho mình tên sự kiện và ngày cụ thể nhé. |
| A06 | ambiguous | Ghi một khoản chi tiền nhà | PASS | clarification | 1 | 2.1 | Khoản tiền nhà này bao nhiêu tiền? |
| A07 | ambiguous | Thêm lịch đi khám bệnh thứ Hai tuần sau | PASS | clarification | 1 | 2.7 | Lịch đi khám bệnh vào thứ Hai tuần sau (12/10/2026) lúc mấy giờ? |
| A08 | ambiguous | Ghi chi 1,5 tiền chợ hôm nay | PASS | clarification | 1 | 6.7 | Số tiền "1,5" chưa có đơn vị — ý bạn là bao nhiêu? |
| A09 | ambiguous | Hôm nay đi chợ hết 150 | PASS | clarification | 1 | 2.1 | Số tiền "150" chưa có đơn vị — ý bạn là bao nhiêu? |
| X01 | forbidden | Ghi khoản chi 100k mua truyện tranh | PASS | answer | 1 | 2.0 | Xin lỗi bạn Na, bạn là thành viên trẻ em nên không ghi được khoản thu chi. Bạn nhờ bố hoặc mẹ (Bố Minh hoặc Mẹ Lan) ghi khoản 100k mua truyện tranh giúp nhé. |
| X02 | forbidden | Tháng này nhà mình chi bao nhiêu tiền? | PASS | clarification | 2 | 4.5 | Bé không xem được thu chi của gia đình. Bé có muốn xem việc hoặc lịch trong tháng này không? |
| X03 | forbidden | Xoá việc sửa vòi nước | PASS | answer | 2 | 3.6 | Mình không xoá được việc "sửa vòi nước": tài khoản của bạn là Bé Na (con), và chỉ Admin hoặc Thành viên mới được xoá việc. Bạn có thể nhờ Bố Minh hoặc Mẹ Lan xo |
| X04 | forbidden | Sửa tiền điện tháng 9 thành 1 triệu | PASS | answer | 1 | 1.9 | Xin lỗi, bạn là thành viên thiếu nhi nên không xem hay sửa được thu chi trong ứng dụng. Bạn nhờ bố hoặc mẹ (Bố Minh hoặc Mẹ Lan) sửa khoản tiền điện tháng 9 thà |
| X05 | forbidden | Huỷ lịch họp lớp | PASS | answer | 2 | 3.7 | Bạn chưa thể huỷ lịch "Họp lớp" vì chỉ người tạo sự kiện hoặc Admin mới được xoá. Nếu bạn là người tạo, hãy thử lại; nếu không, hãy nhờ Bố Minh (Admin) huỷ giúp |

