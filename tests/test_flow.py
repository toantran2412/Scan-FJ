"""Kiểm tra luồng chính của Scan FJ bằng Playwright (Chromium headless).

Cách chạy (trong thư mục gốc repo):
    pip install playwright && playwright install chromium
    python3 -m http.server 8765 &
    python3 tests/test_flow.py /duong/dan/anh_to_giay.jpg

Kiểm tra: tạo 2 tài liệu từ cùng một ảnh, giữ trang, xuất PDF (tải về),
tải lại trang và xác nhận 2 tài liệu vẫn còn, không có lỗi JavaScript.
"""
import asyncio, os, sys
from playwright.async_api import async_playwright

URL = os.environ.get('SCAN_FJ_URL', 'http://localhost:8765/index.html')


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

        await browser.close()
        if errors:
            print('LỖI JAVASCRIPT:', *errors, sep='\n  ')
            sys.exit(1)
        print('TẤT CẢ ĐẠT')


if __name__ == '__main__':
    if len(sys.argv) < 2 or not os.path.exists(sys.argv[1]):
        print('Cách dùng: python3 tests/test_flow.py /duong/dan/anh_to_giay.jpg')
        sys.exit(2)
    asyncio.run(main(os.path.abspath(sys.argv[1])))
