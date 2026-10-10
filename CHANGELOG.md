# Thay đổi

Ghi theo phiên bản, mới nhất ở trên. Nội dung mục của từng phiên bản được dùng làm ghi chú
hiển thị trong **Thiết lập → Hệ thống & Sao lưu → Phiên bản & Cập nhật**.

## [1.4.0] - 2026-10-10

### Mới
- **Trợ lý nâng cao ghi được Thu chi**: nhờ trợ lý ghi, sửa, xoá khoản thu/chi — kiểu "hôm nay đi chợ hết 250k", "tiền điện tháng 9 thực ra là 900 nghìn, sửa lại giúp mình", "xoá khoản đổ xăng hôm 7/10". Như các mục khác, trợ lý chỉ **đề xuất**; bạn xem thẻ rồi bấm **Duyệt** mới có thay đổi.
  - Thẻ Duyệt luôn ghi **số tiền đầy đủ** (vd. 1.200.000₫), Thu hay Chi, hạng mục, ngày; sửa thì hiện "cũ → mới", xoá hiện màu đỏ.
  - Số tiền nói kiểu "250k", "1tr2", "1,5 triệu", "2 triệu rưỡi" được đổi chính xác; nói chưa rõ (vd. "1,5" mà không có đơn vị) thì trợ lý hỏi lại chứ không đoán.
  - Khoản chi phải thuộc một hạng mục đang dùng (kể cả hạng mục gia đình tự thêm); chưa rõ hạng mục thì trợ lý hỏi lại kèm nút chọn. Không nói ngày thì ghi hôm nay.
  - Sửa qua trợ lý chỉ đổi đúng thứ bạn nói — ảnh hoá đơn và các thông tin khác giữ nguyên. Xoá giao dịch thì xoá luôn ảnh hoá đơn của nó.
  - Chỉ Admin và Thành viên nhờ trợ lý ghi thu chi được (giống trong app). Nếu ai đó vừa sửa giao dịch trong lúc bạn chưa bấm Duyệt, thẻ báo dữ liệu đã thay đổi và không ghi đè.
  - Vài giao dịch cũ có số tiền lẻ (không tròn đồng) thì trợ lý không sửa/xoá được — bạn sửa trực tiếp trong mục **Thu chi**.

### Sửa lỗi
- Nhật ký hoạt động giờ ghi lại đầy đủ việc thêm và sửa giao dịch thu chi (trước đây dòng nhật ký có thể bị mất).

### Ghi chú
- Trợ lý cũ vẫn được giữ làm đường lui khi trợ lý nâng cao tắt hoặc tạm lỗi.
- Quay về bản 1.3.0 vẫn được; đề xuất Thu chi còn chờ Duyệt lúc đó sẽ báo "chưa hỗ trợ".

## [1.3.0] - 2026-10-10

### Mới
- **Trợ lý nâng cao làm được Việc và Lịch**: nhờ trợ lý tạo, sửa, xoá việc và sự kiện — kiểu "giao Bin đổ rác trước 6 giờ tối mai", "dời họp phụ huynh sang 2 giờ chiều thứ Ba", "thêm lịch học bơi mỗi thứ Ba". Như với Đi chợ, trợ lý chỉ **đề xuất**; bạn xem thẻ rồi bấm **Duyệt** mới có thay đổi.
  - Tên việc/lịch trùng nhau (vd. hai lịch "Sinh nhật") thì trợ lý hỏi lại kèm nút chọn.
  - Dời giờ một sự kiện thì giờ kết thúc dời theo, giữ nguyên độ dài.
  - Lịch lặp mà không nói lặp tới khi nào thì mặc định lặp 1 năm — thẻ Duyệt ghi rõ ngày, sửa lại được trong app.
  - Trợ lý không đánh dấu hoàn thành, không duyệt hay trả lại việc của con — những việc đó vẫn làm trong mục **Việc**.
  - Quyền giữ đúng như trong app: Con chỉ sửa việc mình tạo hoặc được giao (việc được giao thì chỉ đổi trạng thái), không tự đặt điểm thưởng, không xoá việc; Khách không thêm/sửa lịch; chỉ người tạo (hoặc Admin) sửa/xoá được một sự kiện.
  - Nếu ai đó vừa sửa việc/lịch trong lúc bạn chưa bấm Duyệt, thẻ báo dữ liệu đã thay đổi và không ghi đè.

### Sửa lỗi
- Thêm sự kiện chung giờ hiện cả trong mục **Thông báo** của app (trước đây chỉ có thông báo đẩy trên điện thoại).
- Sửa một sự kiện không còn vô tình đổi được người tạo của sự kiện đó.

### Ghi chú
- Quay về bản 1.2.0 vẫn được; đề xuất Việc/Lịch còn chờ Duyệt lúc đó sẽ báo "chưa hỗ trợ".

## [1.2.0] - 2026-10-10

### Mới
- **Trợ lý nâng cao** (tùy chọn, Admin bật trong **Thiết lập → Hệ thống & Sao lưu → Trợ lý nâng cao**): hỏi trợ lý về dữ liệu thật của gia đình — Đi chợ, Việc, Lịch, Thu chi — kiểu "tuần này nhà mình tiêu bao nhiêu cho ăn uống?", "mai có lịch gì?".
  - Nhờ trợ lý **thêm/sửa/xoá món Đi chợ**: trợ lý chỉ **đề xuất**, hiện thành thẻ để bạn xem từng thay đổi rồi bấm **Duyệt** — không bấm thì không có gì bị đổi.
  - Chưa rõ ý thì trợ lý hỏi lại, kèm nút chọn nhanh.
  - Mỗi người chỉ thấy và nhờ trợ lý làm những gì mình vốn được phép trong app.
  - Chưa bật, hoặc trợ lý nâng cao tạm lỗi → app tự dùng trợ lý cũ như trước.
- Trang **Cập nhật** báo nếu trợ lý nâng cao chưa chạy được sau khi cập nhật (app vẫn chạy bình thường).

### Cần làm một lần trên Pi (chỉ khi muốn dùng Trợ lý nâng cao)
- Cần một dịch vụ AI tương thích OpenAI (địa chỉ, khóa, tên model). Thêm các biến `AGENT_*` vào `.env` và service `family-organizer-agent` vào `docker-compose.yml` theo README, mục **Trợ lý nâng cao**. Không làm bước này thì mọi thứ vẫn như cũ.

### Ghi chú
- Dịch vụ cập nhật tự nâng cấp sau khi lên bản này. Từ lần cập nhật **kế tiếp**, nó cập nhật luôn cả trợ lý nâng cao cùng phiên bản với app; trợ lý lỗi không làm app bị quay về (trợ lý được giữ ở bản trước).
- Cập nhật bị lỗi và tự quay về thì dịch vụ cập nhật giữ nguyên bản đang chạy của nó.
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
