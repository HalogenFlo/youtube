# Lumi

Chức năng: Nhân vật mặc định của luồng HTML/Canvas.
Lý do: Sử dụng thiết kế do người dùng cung cấp.
Nguồn: C:/Users/Admin/Downloads/lumi-animation-v2.html.

original.html giữ nguyên thiết kế và bộ điều khiển gốc. character.svg là phần SVG được trích xuất, không vẽ lại nhân vật. Bộ dựng src/cartoon_timeline.js điều khiển các nhóm tay, chân, mắt, tóc theo thời gian xác định.

Luồng HTML dùng Chrome để kết hợp SVG với phong cảnh. Nếu Chrome không dựng được Lumi, báo lỗi thay vì đổi sang nhân vật khác. Thiết kế này áp dụng cho video HTML mới; các ảnh đã tạo bằng Google Flow là một luồng riêng.
