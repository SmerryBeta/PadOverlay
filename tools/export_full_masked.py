"""整张源拼图：用 alpha 掩码乘 RGB，导出预览图。"""
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QImage, QPainter, qAlpha, qBlue, qGreen, qRed, qRgba
from PyQt5.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "skins" / "neon_pad"
LOCAL = OUT / "_source_sheet.png"
ASSET = Path(
    r"C:\Users\30724\.cursor\projects\s-pyProjects-PadOverlay\assets"
    r"\Xbox__________-32d41a5f-bf5b-44c7-a8c8-cb6d2fb700a2.png"
)


def main() -> int:
    app = QApplication([])
    src_path = LOCAL if LOCAL.exists() else ASSET
    src = QImage(str(src_path)).convertToFormat(QImage.Format_ARGB32)
    if src.isNull():
        print("bad", src_path)
        return 1
    w, h = src.width(), src.height()
    print("src", src_path, w, h)

    # 保留 straight alpha 的整图（A=0 清脏 RGB）
    straight = QImage(w, h, QImage.Format_ARGB32)
    straight.fill(0)
    # 预乘版用于贴到棋盘/品红
    premul = QImage(w, h, QImage.Format_ARGB32)
    premul.fill(0)
    zero = partial = opaque = 0
    for y in range(h):
        for x in range(w):
            c = src.pixel(x, y)
            a = qAlpha(c)
            if a == 0:
                zero += 1
                continue
            r, g, b = qRed(c), qGreen(c), qBlue(c)
            straight.setPixel(x, y, qRgba(r, g, b, a))
            # RGB *= A/255
            premul.setPixel(
                x, y, qRgba((r * a) // 255, (g * a) // 255, (b * a) // 255, a)
            )
            if a == 255:
                opaque += 1
            else:
                partial += 1
    premul_pm = premul.convertToFormat(QImage.Format_ARGB32_Premultiplied)

    cell = 16
    light, dark = QColor(210, 210, 210), QColor(160, 160, 160)
    board = QImage(w, h, QImage.Format_ARGB32)
    for y in range(h):
        for x in range(w):
            board.setPixelColor(
                x, y, light if ((x // cell) + (y // cell)) % 2 == 0 else dark
            )

    checker = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    checker.fill(0)
    p = QPainter(checker)
    p.drawImage(0, 0, board)
    p.drawImage(0, 0, premul_pm)
    p.end()

    magenta = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    magenta.fill(QColor(255, 0, 255))
    p2 = QPainter(magenta)
    p2.drawImage(0, 0, premul_pm)
    p2.end()

    OUT.mkdir(parents=True, exist_ok=True)
    p_checker = OUT / "_full_masked_checker.png"
    p_magenta = OUT / "_full_masked_magenta.png"
    p_alpha = OUT / "_full_masked_alpha.png"
    checker.save(str(p_checker), "PNG")
    magenta.save(str(p_magenta), "PNG")
    straight.save(str(p_alpha), "PNG")
    print(p_checker)
    print(p_magenta)
    print(p_alpha)
    print("zero/partial/opaque", zero, partial, opaque)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
