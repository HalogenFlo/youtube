# Thư viện video & Giọng VieNeu theo vai

## Thư viện video (MuseAI Studio → "📚 Thư viện video")
- Liệt kê mọi `.mp4` trong `video_studio/output/`, mới nhất trước: xem video, tải về, **xóa** (phải tick xác nhận).
- Chọn một video ở danh sách để xem/tải; khi chưa chọn, ứng dụng chỉ đọc metadata. Các video còn lại không được nạp vào bộ nhớ để tạo nút tải.
- Mỗi video có metadata đăng bài lưu ở `<tên>.publish.json` (tự tạo khi pipeline xong, sửa tay được):
  - **Tiêu đề** ≤ 100 ký tự, bỏ `<` `>`.
  - **Hashtag** tối đa 5 theo quy ước của ứng dụng, ưu tiên chủ đề cụ thể rồi nhóm nội dung. Video vẽ tay luôn có **#giaotieplade**; các kiểu còn lại có **#hochoidoday**, không trộn hai kênh. MuseAI đề xuất từ khóa tìm kiếm theo từng bài, ứng dụng giữ một chỗ cho hashtag kênh. Video cũ được bổ sung khi mở thư viện; phần chỉnh sửa được giữ.
  - Tránh tự đề xuất các thẻ tăng tiếp cận chung không liên quan (`#fyp #viral #trending ...`). Đây là lựa chọn của ứng dụng, không phải danh sách thẻ bị nền tảng cấm. `#shorts` được phép khi phù hợp. Không bảo đảm lượt xem hoặc việc duyệt video.
  - **Mô tả** = *mô tả cố định* + nội dung + dòng minh bạch AI + hashtag, luôn ≤ 5000 byte UTF-8. Đoạn liên hệ quá dài được rút về tối đa 2000 byte và có cảnh báo; phần nội dung dùng ngân sách còn lại, giữ dòng minh bạch AI và hashtag kênh. Ký tự tiếng Việt/emoji không bị cắt hỏng.
  - **Caption TikTok** giới hạn theo 2200 đơn vị UTF-16 đã cấu hình, kể cả emoji. Hashtag được ghép từ ô hashtag TikTok khi lưu; nội dung caption sửa riêng, không giữ lại bộ thẻ cũ.
  - YouTube yêu cầu khai báo AI với nội dung chân thực thuộc diện áp dụng; hoạt hình phi thực tế không mặc nhiên bắt buộc. TikTok yêu cầu nhãn với hình, âm thanh, video AI chân thực và khuyến khích minh bạch các dạng khác. Hashtag không thay thao tác khai báo khi bắt buộc.
- **Mô tả cố định** (liên hệ mua pipeline / Gemini Pro / MuseAI) sửa ở expander đầu trang, lưu vào `video_studio/library_config.json` (không đưa lên git). Nhớ thay `[ĐIỀN ZALO / EMAIL CỦA BẠN]`.
- Xóa chỉ gỡ video + file cùng tên (`.json`, `.publish.json`, `.srt`, `.ass`, ảnh bìa) trong thư mục output; không đụng file ngoài.

Nguồn kiểm tra chính sách: [hashtag YouTube](https://support.google.com/youtube/answer/6390658?hl=en), [khai báo AI YouTube](https://support.google.com/youtube/answer/14328491?hl=en), [khai báo AI TikTok](https://support.tiktok.com/en/using-tiktok/creating-videos/ai-generated-content).

## Giọng VieNeu theo vai
- Giọng dẫn chuyện = giọng chọn trong form. Mỗi nhân vật được gán **một giọng VieNeu riêng** (nam/nữ theo vai), không trùng giọng dẫn chuyện, cùng tên luôn cùng giọng (`src/voice_casting.py`).
- Bảng giọng được lưu ở `voice_casting.json` trong thư mục dựng và bộ nhớ series; tập sau/viết tiếp dùng bảng đã lưu ngay cả khi thứ tự nhân vật đổi. Series cũ được khôi phục bảng giọng từ metadata các tập đã dựng nếu còn các file đó. Giọng dẫn đã lưu cũng được giữ khi viết tiếp.
- Khi bật lồng tiếng, lỗi TTS, thiếu file audio hoặc lỗi ghép phụ đề đều làm dừng sản xuất; không xuất video câm rồi báo hoàn thành. MuseAI yêu cầu âm thanh giọng nói thật, không dùng âm báo thử nghiệm thay lời đọc.
- Cảm xúc từng câu (`emotion`: happy, excited, surprised, angry, sad, thinking, neutral) chỉnh **tốc độ đọc** (VieNeu chỉ hỗ trợ tốc độ, không có cao độ).
- Với Edge TTS: cảm xúc chỉnh cả tốc độ và cao độ, mỗi tên nhân vật nhận một preset giọng riêng.
- "🔊 Nghe thử giọng đọc" ở đầu trang MuseAI cho nghe thử giọng + cảm xúc trước khi sản xuất.
- Hạn chế: giao diện hiện chọn 6 preset (nam: Hải Đăng, Thiện Minh; nữ: Mai Anh, Trúc Ly, Thùy Dung, Ngọc Huyền). Trừ giọng dẫn ra khỏi kho phân vai; khi hết giọng cùng giới, nhân vật mới phải dùng lại giọng. Các nhân vật cũ giữ giọng đã lưu.
