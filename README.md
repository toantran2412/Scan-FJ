# Scan FJ

Web app (PWA) quét tài liệu bằng điện thoại cho FRESCO: chụp → tự dò mép giấy → làm thẳng → lọc rõ chữ → ghép PDF → chia sẻ. Chạy trên iPhone/Android qua trình duyệt, cài ra màn hình chính, dùng được offline. Không có máy chủ, không tài khoản: **mọi dữ liệu chỉ nằm trên điện thoại đã chụp.**

- Địa chỉ đang chạy: https://toantran2412.github.io/Scan-FJ/ (GitHub Pages, nhánh `main`, thư mục gốc)
- Bản hiện tại: xem hằng `APP_VERSION` trong `index.html` (hiện ở cuối màn hình danh sách tài liệu)

## Cấu trúc (7 file, không có bước build)

| File | Vai trò |
|---|---|
| `index.html` | Toàn bộ app: giao diện + xử lý ảnh + lưu trữ, 1 file, không framework |
| `sw.js` | Service worker: lưu app vào máy để chạy offline; `index.html`/`manifest.json` lấy mạng trước (network-first) để nhận bản mới, các file khác lấy từ bộ nhớ đệm trước |
| `manifest.json` | Tên "Scan FJ", icon, chế độ standalone để cài ra màn hình chính |
| `jspdf.umd.min.js` | jsPDF 2.5.1 (bản UMD từ npm), để tạo PDF offline |
| `icon-192.png`, `icon-512.png`, `apple-touch-icon.png` | Icon (gốc là SVG "khung quét xanh lá", xem phần Icon) |

Thư viện ngoài duy nhất tải lúc chạy: **tesseract.js 5.1.1** (jsDelivr) + bộ nhận dạng `vie+eng` (tessdata.projectnaptha.com), chỉ khi người dùng bấm "Đọc chữ"; sau lần đầu được service worker giữ lại trong máy.

## Luồng người dùng

```
Danh sách tài liệu (home)
 └─ ＋ Tài liệu mới ──► Camera (tự dò mép, tự chụp khi giấy đứng yên)
                           └─► "Giữ trang này?" (xem kết quả, đổi bộ lọc, ép khổ A4, Chỉnh góc)
                                 ├─ Giữ trang ──► Danh sách trang của tài liệu
                                 └─ Giữ & chụp tiếp ──► Camera
 └─ Mở tài liệu ──► Danh sách trang: Chụp / Thư viện / Sửa / ↑↓ / Aa (OCR) / ✕ / Lưu-chia sẻ
                      └─ Lưu / chia sẻ ──► tên file, dung lượng (Nhẹ/Vừa/Rõ) ──► bảng chia sẻ của điện thoại (1 file PDF)
```

`S.view` nhận các giá trị: `home`, `list`, `camera`, `confirm`, `edit`, `ocr`, `save`. Mỗi view có hàm `renderXxx()`; `render()` là bộ điều phối duy nhất.

## Xử lý ảnh (tất cả trong `index.html`)

1. `loadFile()` – đọc ảnh, xoay theo EXIF, thu về tối đa 2400 px cạnh dài.
2. `regionCorners()` – **dò tờ giấy**: thu nhỏ 400 px → ngưỡng sáng `(Otsu + p95)/2` → **cắt vùng sáng theo mép** (bỏ các điểm có gradient > 28, nở 1 px: đường bóng mỏng giữa hai tờ giấy chạm nhau sẽ tách chúng ra) → mở hình thái → thành phần liên thông: **ưu tiên vùng chứa tâm khung**, không có thì lấy vùng lớn nhất (≥12 % khung) → bao lồi (`convexHull`) → Douglas–Peucker (`dpClosed`) → chọn 4 đỉnh diện tích lớn nhất → sắp xếp tl,tr,br,bl → **kiểm tra lấp đầy**: vùng (đã lấp các lỗ do chữ) phải chiếm ≥ 88 % diện tích tứ giác, nếu không (giấy dính với tờ khác thành hình L) thì bỏ. Thử lần lượt: **không cắt mép** (ổn với biểu mẫu có kẻ ngang sát lề) → cắt mép + mở 1 px (giấy chạm tờ khác) → cắt mép + mở 3 px; thất bại hết → `defaultCorners()` (khung lùi 4 %). Mỗi góc được đẩy ra ngoài 0,5 px (hoặc 2 px khi có cắt mép, ở thang 400 px) để bù phần đã co; khung ra hơi lọt vào trong tờ giấy ~0,5 % để không dính viền nền.
3. `warp()` – biến đổi phối cảnh (homography từ `squareToQuad`, nội suy song tuyến). Nếu `p.a4 !== false` và tỉ lệ cạnh trong 0.5–0.95 (hoặc 1.05–2.0) thì **ép về khổ A4** (1:√2); cạnh dài tối đa 2600 px.
4. `applyFilter()` – `enhance` (mặc định): ước lượng nền giấy theo ô (trung bình 30 % điểm sáng nhất mỗi ô, làm mượt 2 lần) rồi chia để nền trắng, chữ đen, giữ màu; `bw`: ngưỡng thích nghi theo trung bình cục bộ (ảnh tích phân); `gray`: kéo giãn 2–98 %; `none`.
5. `rotateCanvas()` – xoay 0/90/180/270.
6. `process(p)` chạy 3→5, ghi `p.out`, xoá `p.blob` (ảnh JPEG đã mã hoá để lưu).

Camera: `getUserMedia` (`facingMode: environment`, ideal 4032×3024 → máy tự chọn mức cao nhất). Mỗi 200 ms vẽ khung xuống 320 px, chạy `regionCorners`, vẽ viền lên overlay; 6 khung liên tiếp ổn định (dịch góc < 1.5 % cạnh) → tự chụp. Stream được **giữ mở** khi chuyển qua lại các màn hình của cùng tài liệu (chỉ tắt ở màn hình home / rời tab) để Safari không hỏi quyền lại.

PDF: `buildPdf()` – A4 dọc/ngang theo từng trang, ảnh thu về `QUAL[quality].px` và JPEG `q`; trang đúng tỉ lệ A4 đổ sát mép, trang khác căn giữa lề 8 mm. Chia sẻ bằng `navigator.share({files:[File]})`; không hỗ trợ thì tải về bằng `<a download>`.

## Lưu trữ (chỉ trên máy)

IndexedDB `fresco-scan` phiên bản 2, hai store: `docs` (`id,name,created,order`) và `pages` (`id,docId,order,blob(JPEG),ocr,filter,rot`). `saveAll()` ghi lại toàn bộ (mã hoá blob trước, rồi mới mở transaction – transaction IndexedDB tự đóng nếu `await` bên trong). `loadAll()` dựng lại; trang cũ không có `docId` (bản trước v4) được gom vào tài liệu "Scan cũ". Trang tải lại từ DB có `src=null` nên không "Sửa" góc được nữa (chỉ xoay/lọc đã mất) – chấp nhận.

`localStorage['fresco-scan-doc']`: `{quality, autoShot}`.

## Việc còn chờ quyết định của Toàn

- **Đóng băng (freeze)** khi đã chốt: đổi `sw.js` sang cache-first cho cả `index.html` (không kiểm tra mạng nữa), gộp bộ nhận dạng OCR tiếng Việt vào gói (+~10 MB lúc cài) để "Đọc chữ" cũng offline, đổi dòng phiên bản thành "bản chính thức".
- Tên miền riêng (vd. `scan.fresco.vn`) nếu muốn hộp thoại iOS hiện tên công ty thay vì `toantran2412.github.io` (GitHub Pages hỗ trợ CNAME miễn phí).
- Chưa thử trên Android thật và trên hoá đơn nhỏ / giấy màu.

## Kiểm tra

`tests/test_flow.py` (Playwright, Chromium headless, khung hình điện thoại 400×860): tạo 2 tài liệu từ một ảnh, giữ trang, xuất PDF, tải lại trang kiểm tra dữ liệu còn. Chạy trên Windows, trong **PowerShell**, tại thư mục gốc repo (dùng `python`, không phải `python3`):

```powershell
# Cài một lần
pip install playwright
python -m playwright install chromium

# Mỗi lần kiểm tra: bật máy chủ tạm ở cổng 8765, chạy test, tắt máy chủ
$env:PYTHONUTF8 = '1'
$srv = Start-Process python -ArgumentList '-m http.server 8765' -WorkingDirectory $PWD -WindowStyle Hidden -PassThru
Start-Sleep 2
python tests\test_flow.py C:\duong\dan\anh_to_giay.jpg
Stop-Process -Id $srv.Id
```

Ảnh thử: ảnh chụp một tờ giấy bất kỳ đặt trên nền tối. Test đạt khi dòng cuối là `TẤT CẢ ĐẠT`.

Kiểm tra cú pháp nhanh (PowerShell):

```powershell
node --check sw.js
python -c "import re,os;s=open('index.html',encoding='utf-8').read();open(os.environ['TEMP']+'/app.js','w',encoding='utf-8').write(re.findall(r'<script>(.*?)</script>',s,re.S)[0])"
node --check "$env:TEMP\app.js"
```

Lưu ý Windows: bảng mã mặc định là cp1258, nên đọc/ghi file bằng Python phải ghi rõ `encoding='utf-8'` (hoặc đặt `$env:PYTHONUTF8 = '1'`); không ghi file bằng `Set-Content`/`Out-File` của PowerShell vì sẽ hỏng chữ tiếng Việt.

## Quy ước khi sửa

- Mỗi lần đổi `index.html`/`sw.js`: tăng `APP_VERSION` trong `index.html` **và** tên `CACHE` trong `sw.js` (vd. `scan-fj-v7`), nếu không máy người dùng có thể giữ bản cũ.
- Giao diện toàn bộ tiếng Việt, không dùng font ngoài (chạy offline), không thêm thư viện tải lúc chạy ngoài tesseract.
- Không bao giờ thêm lệnh gửi dữ liệu ảnh/PDF ra ngoài điện thoại (yêu cầu của chủ app).
- Đẩy lên `main` là GitHub Pages tự đăng sau 1–2 phút.

## Icon

Nguồn SVG của icon (khung quét 4 góc vàng, tờ giấy nghiêng, nền xanh lá) nằm trong `README` này để dựng lại khi cần:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1f6b52"/><stop offset="1" stop-color="#0f3d2e"/></linearGradient></defs>
<rect width="512" height="512" rx="112" fill="url(#g)"/>
<g transform="rotate(-8 256 256)"><rect x="156" y="116" width="200" height="270" rx="18" fill="#f6f2e8"/>
<rect x="186" y="160" width="90" height="14" rx="7" fill="#1f6b52" opacity=".85"/><rect x="186" y="196" width="140" height="10" rx="5" fill="#9a958a"/>
<rect x="186" y="222" width="140" height="10" rx="5" fill="#9a958a"/><rect x="186" y="248" width="110" height="10" rx="5" fill="#9a958a"/><rect x="186" y="274" width="140" height="10" rx="5" fill="#9a958a"/></g>
<rect x="96" y="300" width="320" height="16" rx="8" fill="#e8b84a"/><rect x="96" y="300" width="320" height="16" rx="8" fill="#fff" opacity=".35"/>
<g fill="none" stroke="#e8b84a" stroke-width="22" stroke-linecap="round"><path d="M92 160 v-50 h50"/><path d="M420 160 v-50 h-50"/><path d="M92 352 v50 h50"/><path d="M420 352 v50 h-50"/></g>
</svg>
```
