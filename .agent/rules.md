# Luật Phát Triển Dự Án (Agent Rules)

## 1. Ngôn ngữ & Giao tiếp
- Luôn trả lời và giải thích bằng tiếng Việt.
- Giữ nguyên các thuật ngữ kỹ thuật phổ biến khi không có bản dịch phù hợp.
- Trả lời ngắn gọn, trực tiếp, tập trung vào yêu cầu chính.
- Ưu tiên ví dụ thực tế thay vì lý thuyết dài dòng.
- Định dạng Markdown rõ ràng, dễ đọc.

## 2. Quy tắc Lập trình (Strict Functional Programming)
- Ưu tiên tuyệt đối phong cách Functional Programming.
- Hạn chế sử dụng OOP trừ khi thật sự cần thiết.
- Tránh biến đổi trạng thái (Immutability):
  - Dùng `const` thay cho `let`, `var` trong JS/TS.
  - Sử dụng `map()`, `filter()`, `reduce()` thay cho `for`, `while`.
- Chia nhỏ logic thành các `pure function` (không side-effect, dễ test).
- Xử lý lỗi tường minh, sử dụng Try-Catch hoặc Result Pattern.

## 3. Quy tắc Chỉnh sửa File & Context
- **Minimal Change**: Chỉ sửa đúng phần cần thiết, không refactor toàn bộ file nếu không yêu cầu.
- **Read Before Write**: Luôn đọc file/context trước khi sửa.
- **Copyright**: Mọi file mới tạo phải bắt đầu bằng mô tả chức năng, lý do tạo và link trích dẫn nếu có.
- **Verification**: Sau khi sửa, đề xuất lệnh terminal chạy test/build/lint hoặc cách verify cụ thể.
- **Double Check**: Rà soát kỹ syntax, import, type errors trước khi hoàn thành.

## 4. Quy tắc Tư duy (DeepThink)
Trước mọi hành động (lập trình, sửa file, debug, thiết kế):
Phải phân tích trong khối:
```xml
<deepthink>
1. Phân tích yêu cầu
2. Đánh giá rủi ro
3. Kế hoạch thực hiện
4. Dự đoán kết quả
5. Edge cases có thể xảy ra
</deepthink>
```
- Không đoán mò API/codebase. Tìm tài liệu liên quan trước khi thực hiện.
- Đọc kỹ README, cấu trúc dự án và quy ước lập trình trước khi code.
