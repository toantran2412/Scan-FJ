r"""Kiểm tra luồng chính của Scan FJ bằng Playwright (Chromium headless).

Cách chạy trên Windows, trong PowerShell, tại thư mục gốc repo
(dùng `python`, không phải `python3`):
    # Cài một lần
    pip install playwright pillow
    python -m playwright install chromium

    # Mỗi lần kiểm tra: bật máy chủ tạm ở cổng 8765, chạy test, tắt máy chủ
    $env:PYTHONUTF8 = '1'
    $srv = Start-Process python -ArgumentList '-m http.server 8765' -WorkingDirectory $PWD -WindowStyle Hidden -PassThru
    Start-Sleep 2
    python tests\test_flow.py C:\duong\dan\anh_to_giay.jpg
    Stop-Process -Id $srv.Id

PYTHONUTF8=1 để in được tiếng Việt (bảng mã mặc định của Windows tiếng Việt là cp1258).

Kiểm tra: tạo 2 tài liệu từ cùng một ảnh, giữ trang, xuất PDF (tải về),
tải lại trang và xác nhận 2 tài liệu vẫn còn, không có lỗi JavaScript.
Sau đó tự dựng ảnh thử 2 bằng Pillow (tờ A4 xoay 11° trên xấp giấy lớn hơn 3 %,
góc trên trái chạm tờ giấy khác, nền gỗ tối) và xác nhận từng góc dò được nằm
phía trong tờ trên cùng: so với góc thật, khoảng cách tới tâm tờ thật không được
lớn hơn quá 0,3 % (lố ra ngoài) hay nhỏ hơn quá 2 % (lọt vào trong), tính theo
tỉ lệ khung. Mép xấp giấy lố ra 0,8–1,6 % nên bị phân biệt với tờ trên cùng.
Ảnh thử 3: cuốn sổ bìa trắng bằng 70 % kích thước xấp giấy, nằm trên xấp giấy
trắng cùng màu, không có bóng; kiểm tra 4 góc cuốn sổ theo cùng cách đo.
"""
import asyncio, itertools, math, os, random, sys, tempfile
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps
from playwright.async_api import async_playwright

URL = os.environ.get('SCAN_FJ_URL', 'http://localhost:8765/index.html')


def _font(size, bold=False):
    names = ['arialbd.ttf', 'Arial Bold.ttf', 'DejaVuSans-Bold.ttf'] if bold else ['arial.ttf', 'Arial.ttf', 'DejaVuSans.ttf']
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size)
    except TypeError:                       # Pillow < 10.1
        return ImageFont.load_default()


def _place(canvas, sheet, center, angle, shadows=()):
    """Dán tờ giấy (ảnh RGBA) lên canvas: tâm ở center, xoay angle độ (dương = theo chiều kim đồng hồ).
    shadows: các bóng (dx, dy, độ nhoè, độ đậm 0..255) vẽ trước tờ giấy. Trả về 4 góc thật tl, tr, br, bl (pixel)."""
    w, h = sheet.size
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)

    def layer(img, cx, cy):                 # điểm đích (x, y) lấy màu ở điểm nguồn = tâm tờ + R(-a)·(đích - tâm đích)
        img = img.convert('RGBa')           # nhân trước alpha để mép không bị viền đen
        t = img.transform(canvas.size, Image.AFFINE, (ca, sa, w / 2 - ca * cx - sa * cy, -sa, ca, h / 2 + sa * cx - ca * cy),
                          resample=Image.BICUBIC)
        return t.convert('RGBA')

    cx, cy = center
    for dx, dy, blur, alpha in shadows:
        canvas.alpha_composite(layer(Image.new('RGBA', (w, h), (0, 0, 0, alpha)), cx + dx, cy + dy).filter(ImageFilter.GaussianBlur(blur)))
    canvas.alpha_composite(layer(sheet, cx, cy))
    return [(cx + ca * (x - w / 2) - sa * (y - h / 2), cy + sa * (x - w / 2) + ca * (y - h / 2)) for x, y in [(0, 0), (w, 0), (w, h), (0, h)]]


def _wood(rnd, W, H):
    """Nền gỗ tối: vân ngang + hạt nhỏ (ảnh RGBA)."""
    grain = Image.frombytes('L', (1, 180), rnd.randbytes(180)).resize((W, H), Image.BICUBIC)            # vân gỗ ngang
    fine = Image.frombytes('L', (W // 4, H // 4), rnd.randbytes((W // 4) * (H // 4))).resize((W, H), Image.BICUBIC)
    return ImageOps.colorize(Image.blend(grain, fine, 0.3), black=(30, 18, 10), white=(96, 62, 38)).convert('RGBA')


def _finish(canvas, path):
    """Trên sáng hơn dưới ~8 %, hơi nhoè như ảnh chụp; ghi JPEG ra path."""
    W, H = canvas.size
    light = Image.linear_gradient('L').resize((W, H)).point(lambda v: 255 - v * 20 // 255)
    img = ImageChops.multiply(canvas.convert('RGB'), Image.merge('RGB', [light] * 3)).filter(ImageFilter.GaussianBlur(0.8))
    img.save(path, quality=88)


def make_stack_image(path):
    """Ảnh thử 2, khổ dọc như ảnh điện thoại: tờ A4 có chữ xoay 11° nằm trên xấp giấy trắng lớn hơn 3 % mỗi chiều,
    góc trên trái chạm một tờ giấy trắng khác, nền gỗ tối. Ghi JPEG ra path.
    Trả về 4 góc thật của tờ trên cùng theo tỉ lệ khung (x / rộng, y / cao)."""
    rnd = random.Random(2024)
    W, H = 1500, 2000
    canvas = _wood(rnd, W, H)

    pw, ph = 900, round(900 * 2 ** 0.5)     # tờ A4
    center, angle = (770, 1030), 11
    # xấp giấy: 3 tờ lớn hơn 3 % mỗi chiều, xếp lệch nhau vài px
    sw, sh = round(pw * 1.03), round(ph * 1.03)
    for dx, dy, da, v, shadows in [(4, 5, 0.25, 222, [(12, 16, 14, 140)]), (-3, 2, -0.2, 228, [(0, 0, 2, 60)]), (0, 0, 0, 234, [(0, 0, 2, 60)])]:
        _place(canvas, Image.new('RGBA', (sw, sh), (v, v - 2, v - 6, 255)), (center[0] + dx, center[1] + dy), angle + da, shadows)

    # tờ giấy trên cùng (chưa dán) để biết góc trên trái, rồi đặt tờ giấy khác luồn dưới góc đó
    top = Image.new('RGBA', (pw, ph), (248, 247, 242, 255))
    d = ImageDraw.Draw(top)
    d.text((80, 90), 'BIÊN BẢN GIAO NHẬN', font=_font(52, True), fill=(20, 20, 20))
    d.text((80, 165), 'Công ty CP Thực phẩm FRESCO', font=_font(30), fill=(40, 40, 40))
    lines = ['Ngày: 22/10/2026          Số: GN-0102', 'Bên nhận: Trường Tiểu học ABC',
             '1. Rau muống .................. 10 kg', '2. Cải thảo ...................... 7 kg',
             '3. Cà chua ........................ 5 kg', '4. Bí xanh ......................... 9 kg']
    for i, t in enumerate(lines):
        d.text((80, 260 + i * 72), t, font=_font(30), fill=(30, 30, 30))
    for i in range(9):                      # đoạn văn chữ nhỏ (vạch xám)
        d.rectangle((80, 700 + i * 36, 80 + rnd.randint(480, 740), 714 + i * 36), fill=(95, 95, 95))
    d.text((120, ph - 230), 'Bên giao', font=_font(30, True), fill=(30, 30, 30))
    d.text((pw - 300, ph - 230), 'Bên nhận', font=_font(30, True), fill=(30, 30, 30))

    a = math.radians(angle)
    tlx = center[0] - math.cos(a) * pw / 2 + math.sin(a) * ph / 2
    tly = center[1] - math.sin(a) * pw / 2 - math.cos(a) * ph / 2
    oa = math.radians(-20)                  # tờ khác xoay -20°, góc dưới phải luồn 22 px dưới góc trên trái tờ trên cùng
    bx, by = tlx + 22, tly + 22
    ocx = bx - (math.cos(oa) * pw / 2 - math.sin(oa) * ph / 2)
    ocy = by - (math.sin(oa) * pw / 2 + math.cos(oa) * ph / 2)
    _place(canvas, Image.new('RGBA', (pw, ph), (244, 243, 238, 255)), (ocx, ocy), -20, [(8, 10, 10, 110)])

    corners = _place(canvas, top, center, angle, [(0, 0, 2, 70), (3, 4, 5, 70)])
    _finish(canvas, path)
    return [(x / W, y / H) for x, y in corners]


def make_notebook_image(path):
    """Ảnh thử 3, khổ dọc: cuốn sổ bìa trắng bằng 70 % kích thước xấp giấy, nằm trên xấp giấy trắng cùng màu,
    không có bóng – chỉ có mép sổ là một dải hơi xám mảnh; xấp giấy chiếm ~87 % khung, nền gỗ tối. Ghi JPEG ra path.
    Trả về 4 góc thật của cuốn sổ theo tỉ lệ khung (x / rộng, y / cao)."""
    rnd = random.Random(7)
    W, H = 1500, 2000
    canvas = _wood(rnd, W, H)
    white = (240, 239, 235, 255)
    sw, sh = 1380, 1900                     # xấp giấy, xoay 2°
    for dx, dy, da, shadows in [(5, 4, 0.3, [(14, 18, 16, 150)]), (-3, 2, -0.2, [(0, 0, 2, 60)]), (0, 0, 0, [(0, 0, 2, 60)])]:
        _place(canvas, Image.new('RGBA', (sw, sh), white), (750 + dx, 1000 + dy), 2 + da, shadows)

    nw, nh = round(sw * 0.7), round(sh * 0.7)   # cuốn sổ 70 %, xoay 5°, cùng màu với xấp giấy, không bóng
    book = Image.new('RGBA', (nw, nh), white)
    d = ImageDraw.Draw(book)
    d.rectangle((0, 0, nw - 1, nh - 1), outline=(214, 213, 208, 255), width=8)      # mép sổ hơi xám
    d.text((250, 250), 'SỔ GHI CHÉP', font=_font(80, True), fill=(25, 25, 25))
    d.rectangle((150, 520, nw - 150, 760), outline=(60, 60, 60), width=4)            # ô nhãn in trên bìa
    d.text((190, 560), 'Bộ phận: Sản xuất', font=_font(40), fill=(40, 40, 40))
    d.text((190, 650), 'Năm: 2026', font=_font(40), fill=(40, 40, 40))
    d.text((nw // 2 - 90, nh - 190), 'FRESCO', font=_font(44, True), fill=(60, 60, 60))
    corners = _place(canvas, book, (770, 1020), 5)
    _finish(canvas, path)
    return [(x / W, y / H) for x, y in corners]


def corner_offsets(truth, found):
    """Ghép 4 góc dò được với 4 góc thật (cách ghép có độ lệch lớn nhất nhỏ nhất), rồi đo từng góc dò được
    lố ra ngoài hay lọt vào trong tờ thật: khoảng cách tới tâm tờ thật của góc dò được trừ của góc thật
    (dương = lố ra ngoài, âm = lọt vào trong). Toạ độ theo tỉ lệ khung (x / rộng, y / cao).
    Trả về [(góc thật, góc dò được, độ lố)]."""
    best = None
    for perm in itertools.permutations(found):
        err = max(max(abs(f[0] - t[0]), abs(f[1] - t[1])) for t, f in zip(truth, perm))
        if best is None or err < best[0]:
            best = (err, list(zip(truth, perm)))
    cx, cy = sum(t[0] for t in truth) / 4, sum(t[1] for t in truth) / 4
    return [(t, f, math.hypot(f[0] - cx, f[1] - cy) - math.hypot(t[0] - cx, t[1] - cy)) for t, f in best[1]]


async def check_corners(pg, title, make):
    """Dựng ảnh thử bằng make(path), nạp vào màn Chụp, kiểm tra từng góc dò được nằm phía trong vật thật:
    lố ra ngoài ≤ 0,3 %, lọt vào trong ≤ 2 % (theo khung)."""
    print(title)
    while await pg.evaluate('S.view') != 'home':
        await pg.click('#btnBack')
    with tempfile.TemporaryDirectory() as tmp:
        image = os.path.join(tmp, 'anh_thu.jpg')
        truth = make(image)
        await pg.click('#bNew')
        await pg.wait_for_selector('#fileLib', state='attached')
        await pg.set_input_files('#fileLib', image)
        await pg.wait_for_selector('#bKeep', timeout=60000)
    found = await pg.evaluate("S.cur.corners.map(c=>[c.x/S.cur.src.width, c.y/S.cur.src.height])")
    rows = corner_offsets(truth, found)
    print('  cho phép: lố ra ngoài ≤ 0,3 %, lọt vào trong ≤ 2 % (theo khung)')
    for t, f, d in rows:
        print(f'  góc thật ({t[0]:.3f}, {t[1]:.3f}) | dò được ({f[0]:.3f}, {f[1]:.3f}) | '
              + (f'lố ra {d * 100:.2f} %' if d > 0 else f'lọt vào {-d * 100:.2f} %'))
    bad = [d for _, _, d in rows if d > 0.003 or d < -0.02]
    assert not bad, 'góc dò được lố ra quá 0,3 % hoặc lọt vào quá 2 %: ' + ', '.join(f'{d * 100:+.2f} %' for d in bad)


async def add_page_from_file(pg, image):
    await pg.set_input_files('#fileLib', image)
    await pg.wait_for_selector('#bKeep', timeout=60000)
    q = await pg.evaluate("S.cur.corners.map(c=>[Math.round(c.x/S.cur.src.width*100)/100,Math.round(c.y/S.cur.src.height*100)/100])")
    size = await pg.evaluate("S.cur.out.width+'x'+S.cur.out.height")
    print('  góc dò được:', q, '| sau cắt:', size)
    await pg.click('#bKeep')
    await pg.wait_for_selector('#bPdf')


async def main(image):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={'width': 400, 'height': 860}, device_scale_factor=2)
        pg = await ctx.new_page()
        errors = []
        pg.on('pageerror', lambda e: errors.append(str(e)))
        pg.on('console', lambda m: errors.append('console: ' + m.text) if m.type == 'error' else None)

        await pg.goto(URL)
        await pg.wait_for_timeout(500)
        await pg.evaluate("indexedDB.deleteDatabase('fresco-scan'); localStorage.clear()")
        await pg.reload()
        await pg.wait_for_selector('#bNew')

        print('Tài liệu 1')
        await pg.click('#bNew')              # camera không có trong headless -> báo lỗi, vẫn ở màn Chụp
        await pg.wait_for_selector('#fileLib', state='attached')
        await add_page_from_file(pg, image)
        await add_page_from_file(pg, image)  # trang 2 cùng tài liệu
        n = await pg.eval_on_selector_all('.page', 'e=>e.length')
        assert n == 2, f'mong 2 trang, có {n}'

        print('Xuất PDF')
        await pg.click('#bPdf')
        await pg.wait_for_selector('#bDown')
        async with pg.expect_download() as dl:
            await pg.click('#bDown')
        d = await dl.value
        size = os.path.getsize(await d.path())
        print('  PDF:', d.suggested_filename, size, 'bytes')
        assert size > 20000, 'PDF quá nhỏ'

        print('Tài liệu 2')
        await pg.click('#btnBack')           # về danh sách trang
        await pg.click('#btnBack')           # về home
        await pg.click('#bNew')
        await add_page_from_file(pg, image)
        await pg.click('#btnBack')

        print('Tải lại trang')
        await pg.reload()
        await pg.wait_for_selector('.doc', timeout=20000)
        await pg.wait_for_timeout(500)
        names = await pg.eval_on_selector_all('.dname', 'e=>e.map(x=>x.textContent)')
        metas = await pg.eval_on_selector_all('.dmeta', 'e=>e.map(x=>x.textContent)')
        print('  tài liệu còn lại:', list(zip(names, metas)))
        assert len(names) == 2, f'mong 2 tài liệu sau khi tải lại, có {len(names)}'

        await check_corners(pg, 'Ảnh thử 2: tờ giấy trên xấp giấy, góc trên trái chạm tờ khác', make_stack_image)
        await check_corners(pg, 'Ảnh thử 3: cuốn sổ trên xấp giấy trắng cùng màu, không có bóng', make_notebook_image)

        await browser.close()
        if errors:
            print('LỖI JAVASCRIPT:', *errors, sep='\n  ')
            sys.exit(1)
        print('TẤT CẢ ĐẠT')


if __name__ == '__main__':
    if len(sys.argv) < 2 or not os.path.exists(sys.argv[1]):
        print(r'Cách dùng: python tests\test_flow.py C:\duong\dan\anh_to_giay.jpg')
        sys.exit(2)
    asyncio.run(main(os.path.abspath(sys.argv[1])))
