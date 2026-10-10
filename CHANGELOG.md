# Thay đổi

Ghi theo phiên bản, mới nhất ở trên. Nội dung mục của từng phiên bản được dùng làm ghi chú
hiển thị trong **Thiết lập → Hệ thống & Sao lưu → Phiên bản & Cập nhật**.

## [1.2.0] - 2026-10-11

### Mới
- **Trợ lý nâng cao** (tùy chọn, Admin bật trong **Thiết lập → Hệ thống & Sao lưu → Trợ lý nâng cao**): hỏi trợ lý về dữ liệu thật của gia đình — Đi chợ, Việc, Lịch, Thu chi — kiểu "tuần này nhà mình tiêu bao nhiêu cho ăn uống?", "mai có lịch gì?".
  - Nhờ trợ lý **thêm/sửa/xoá** món **Đi chợ**, **Việc**, **Lịch** và khoản **Thu chi** — kiểu "thêm 1kg cà chua vào đi chợ", "giao Bin đổ rác trước 6 giờ tối mai", "dời họp phụ huynh sang 2 giờ chiều thứ Ba", "hôm nay đi chợ hết 250k". Một câu nhờ nhiều việc cũng được.
  - Trợ lý chỉ **đề xuất**: thay đổi hiện thành thẻ để bạn xem từng dòng rồi bấm **Duyệt** — không bấm thì không có gì bị đổi. Nếu ai đó vừa sửa dữ liệu trong lúc bạn chưa bấm Duyệt, thẻ báo dữ liệu đã thay đổi và không ghi đè.
  - Chưa rõ ý (vd. hai lịch cùng tên "Sinh nhật", số tiền "150" không rõ nghìn hay triệu) thì trợ lý hỏi lại, kèm nút chọn nhanh.
  - Thẻ Duyệt thu chi luôn ghi **số tiền đầy đủ** (vd. 1.200.000₫); "250k", "1tr2", "1,5 triệu", "2 triệu rưỡi" được đổi chính xác. Sửa qua trợ lý chỉ đổi đúng thứ bạn nói — ảnh hoá đơn và thông tin khác giữ nguyên.
  - Dời giờ một sự kiện thì giờ kết thúc dời theo. Lịch lặp không nói lặp tới khi nào thì mặc định 1 năm — thẻ ghi rõ ngày.
  - Mỗi người chỉ thấy và nhờ trợ lý làm những gì mình vốn được phép trong app. Trợ lý không đánh dấu hoàn thành, không duyệt việc của con; chỉ Admin và Thành viên nhờ ghi thu chi được.
  - Chưa bật, hoặc trợ lý nâng cao tạm lỗi → app tự dùng trợ lý cũ như trước.
- Trang **Cập nhật** báo nếu trợ lý nâng cao chưa chạy được sau khi cập nhật (app vẫn chạy bình thường).

### Sửa lỗi
- Thêm sự kiện chung giờ hiện cả trong mục **Thông báo** của app (trước đây chỉ có thông báo đẩy trên điện thoại).
- Sửa một sự kiện không còn vô tình đổi được người tạo của sự kiện đó.
- Nhật ký hoạt động ghi lại đầy đủ việc thêm và sửa giao dịch thu chi.
- Sửa giao dịch mà lưu bị lỗi không còn làm mất ảnh hoá đơn cũ.

### Cần làm một lần trên Pi (chỉ khi muốn dùng Trợ lý nâng cao)
- Cần một dịch vụ AI tương thích OpenAI (địa chỉ, khóa, tên model). Thêm các biến `AGENT_*` vào `.env` và service `family-organizer-agent` vào `docker-compose.yml` theo README, mục **Trợ lý nâng cao**. Không làm bước này thì mọi thứ vẫn như cũ.

### Ghi chú
- Dịch vụ cập nhật tự nâng cấp sau khi lên bản này. Từ lần cập nhật **kế tiếp**, nó cập nhật luôn cả trợ lý nâng cao cùng phiên bản với app; trợ lý lỗi không làm app bị quay về (trợ lý được giữ ở bản trước).
- Vài giao dịch cũ có số tiền lẻ (không tròn đồng) thì trợ lý không sửa/xoá được — bạn sửa trực tiếp trong mục **Thu chi**.
- Quay về bản 1.1.0 trở về trước vẫn được — trợ lý nâng cao được giữ nguyên, bản cũ chỉ đơn giản không dùng tới.

## [1.1.0] - 2026-10-09

### Mới
- **Cập nhật Immich ngay trong app** (tab **Quản lý Server**, chỉ Admin): thẻ Immich so bản đang chạy với bản mới nhất trên GitHub. Có bản mới thì bấm **Cập nhật lên vX** — app chạy `docker compose pull` + `docker compose up -d` cho `immich-server` và `immich-machine-learning`, chờ Immich chạy ổn rồi báo xong, có tiến trình từng bước và nhật ký.
  - Ghi chú phát hành của Immich có **breaking changes** thì app cảnh báo trước để bạn đọc kỹ.
  - Báo qua Telegram khi Immich có bản mới và khi cập nhật xong / lỗi.
  - Immich **không** tự cập nhật ban đêm — luôn do bạn bấm.

### Sửa lỗi
- Lần kiểm tra bản mới trên GitHub bị lỗi (mất mạng…) không còn làm bỏ qua thông báo và tự cập nhật của lượt đó.

### Ghi chú
- Dịch vụ cập nhật tự nâng cấp ngay sau khi lên bản này — không cần làm gì thêm trên Pi.

## [1.0.0] - 2026-10-09

Bản phát hành đầu tiên có số phiên bản. Từ bản này, app được cập nhật ngay trong
**Thiết lập → Hệ thống & Sao lưu → Phiên bản & Cập nhật** — không cần mở terminal.

### Cập nhật kiểu mới
- **Xem trước có gì mới**: mỗi phiên bản kèm ghi chú thay đổi, đọc ngay trong app trước khi cài.
- **Cập nhật một chạm**: bấm **Cập nhật ngay**, app tự sao lưu dữ liệu, tải bản mới, khởi động lại và hiện tiến trình từng bước (Sao lưu → Tải bản mới → Khởi động lại → Kiểm tra → Xong). Xong tự tải lại trang.
- **Tự cứu khi lỗi**: bản mới khởi động không lên thì tự quay về bản đang chạy và khôi phục dữ liệu lúc trước khi cập nhật.
- **Quay về bản cũ**: chọn bất kỳ phiên bản trước trong danh sách; có thể khôi phục cả dữ liệu về lúc trước khi cập nhật nếu bản mới làm hỏng dữ liệu.
- **Tự cập nhật ban đêm** (tùy chọn): chọn giờ, có bản mới thì app tự cài.
- **Báo qua Telegram** (nếu đã cấu hình bot): khi có bản mới, khi bắt đầu cập nhật và khi xong / bị quay về.
- Banner **"Đã có bản mới vX.Y.Z"** hiện trên mọi máy đang mở app, bấm để tải lại.
- Thay Watchtower bằng dịch vụ cập nhật riêng (`family-organizer-updater`): không mở cổng mạng, chỉ đụng tới Family Organizer, không ảnh hưởng ứng dụng khác chạy chung máy.

### Cần làm một lần trên Pi
- Stack liu-homelab: `cd ~/liu-homelab && git pull && sudo bash setup.sh` (thêm dịch vụ cập nhật, bỏ Watchtower). Các lần sau cập nhật hoàn toàn trong app.
