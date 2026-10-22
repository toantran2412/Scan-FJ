# Hướng dẫn cho Claude Code khi làm việc trong repo này

Đọc `README.md` trước: nó mô tả kiến trúc, luồng, thuật toán, lưu trữ và việc còn chờ.

## Bối cảnh
- Chủ app: Toàn (Công ty Cổ phần Thực phẩm FRESCO), quản lý sản xuất, **không lập trình**. Trao đổi và ghi chú bằng **tiếng Việt**, giải thích theo nghĩa người dùng, không dùng thuật ngữ khi không cần.
- Người dùng cuối: nhân viên công ty dùng iPhone/Android, không có tài khoản gì, dùng cả nơi không có mạng.

## Ràng buộc bắt buộc
1. **Không gửi dữ liệu ảnh/PDF/chữ OCR ra khỏi điện thoại** dưới bất kỳ hình thức nào (không fetch/XHR/beacon/WebSocket tới máy chủ nào). Chia sẻ chỉ qua `navigator.share` do người dùng bấm.
2. App phải chạy **offline** sau lần mở đầu: không thêm font/thư viện tải lúc chạy; thư viện mới phải để trong repo và thêm vào `SHELL` của `sw.js`.
3. Giữ **1 file `index.html`**, không framework, không bước build, để Toàn có thể tải 7 file lên bất kỳ máy chủ nào.
4. Mỗi lần đổi `index.html` hoặc `sw.js`: tăng `APP_VERSION` (trong `index.html`) và `CACHE` (trong `sw.js`) cùng lúc.
5. Tên app là **"Scan FJ"** (đã chốt). Không đổi nếu Toàn không yêu cầu.

## Cách kiểm tra trước khi đẩy
Máy của Toàn là **Windows**: chạy các lệnh dưới đây trong **PowerShell**, tại thư mục gốc repo (vd. `C:\dev\Scan-FJ`). Trên Windows gọi `python` (hoặc `py`), không phải `python3`. Cài một lần: `pip install playwright pillow` rồi `python -m playwright install chromium`.

```powershell
# 1. Kiểm tra cú pháp
node --check sw.js
python -c "import re,os;s=open('index.html',encoding='utf-8').read();open(os.environ['TEMP']+'/app.js','w',encoding='utf-8').write(re.findall(r'<script>(.*?)</script>',s,re.S)[0])"
node --check "$env:TEMP\app.js"

# 2. Test luồng chính: bật máy chủ tạm ở cổng 8765, chạy test, tắt máy chủ
$env:PYTHONUTF8 = '1'
$srv = Start-Process python -ArgumentList '-m http.server 8765' -WorkingDirectory $PWD -WindowStyle Hidden -PassThru
Start-Sleep 2
python tests\test_flow.py C:\duong\dan\anh_to_giay.jpg
Stop-Process -Id $srv.Id
```
Test đạt khi dòng cuối là `TẤT CẢ ĐẠT`.

Chữ tiếng Việt trên Windows: bảng mã mặc định là cp1258, nên đọc/ghi file bằng Python phải ghi rõ `encoding='utf-8'` (thiếu là lỗi `UnicodeDecodeError` khi đọc `index.html`); `PYTHONUTF8=1` để test in được tiếng Việt. Không ghi file bằng `Set-Content`/`Out-File` của PowerShell.

Headless Chromium không có camera: màn hình Chụp sẽ báo "Không mở được camera" – bình thường; dùng nút "Ảnh có sẵn" (`#fileLib`) để nạp ảnh trong test.

## Triển khai
`git push origin main` → GitHub Pages tự đăng tại https://toantran2412.github.io/Scan-FJ/ sau 1–2 phút. Không có bước nào khác.

## Việc "đóng băng" (khi Toàn chốt)
- `sw.js`: bỏ nhánh network-first, mọi request same-origin lấy từ cache trước; giữ fallback cache khi offline.
- Gộp tesseract.js (worker + core wasm) và `vie.traineddata`/`eng.traineddata` vào repo, trỏ `createWorker` tới đường dẫn cục bộ (`workerPath`, `corePath`, `langPath`), thêm vào `SHELL`.
- Đổi dòng phiên bản cuối màn hình thành "Scan FJ – bản chính thức".
