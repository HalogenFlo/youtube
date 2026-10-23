# Luồng Flow video theo shot

Chức năng: Hướng dẫn dựng clip kể chuyện theo shot thay cho ảnh di chuyển.
Lý do: Người dùng yêu cầu phong cách tương tự video hoạt hình 3D tham chiếu.
Nguồn tham khảo: https://deepmind.google/technologies/veo/

Chọn Google Flow video, nội dung Kể chuyện kiến thức, phong cách Hoạt hình 3D kể chuyện. Trục truyện được lập trước khi viết lời dẫn. Story script có thể cung cấp shots với action/camera/state_before/state_after. Thời lượng giọng đọc quyết định số shot tối đa 6 giây; mỗi shot có cache theo prompt/phong cách. Clip quá ngắn hoặc lỗi sẽ báo lỗi, không lặp video hoặc lấy ảnh bù.

Bộ lọc biên tập và đạo diễn giữ phong cách 3D đã chọn. Nhánh video truyền style_preset tới bộ điều khiển Flow. Ảnh cache không được coi là clip đã hoàn thành. Clip cũ chưa có cinematic_shots không được tái sử dụng cho luồng mới.

Giới hạn: model video thực tế phụ thuộc lựa chọn trong tài khoản/giao diện Flow. Chưa tự động chọn hoặc xác minh Veo 3.1, chưa tự động upload ảnh nhân vật hay ràng buộc Ingredients/first-last frame. Chỉ dẫn nhất quán trong prompt chưa bảo đảm đồng nhất nhân vật giữa các shot; cần xem bản nháp và tạo lại shot lỗi. Không bảo đảm chất lượng tương đương video tham chiếu chỉ bằng đổi prompt.
