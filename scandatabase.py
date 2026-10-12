

import cv2
import sqlite3

# ==========================================
# KẾT NỐI DATABASE
# ==========================================

conn = sqlite3.connect("products.db")
cursor = conn.cursor()

# ==========================================
# MỞ WEBCAM
# ==========================================

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Khong mo duoc webcam!")
    exit()

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

# Barcode detector
detector = cv2.barcode.BarcodeDetector()

print("===================================")
print("PBL5 - NHAN DIEN SAN PHAM")
print("===================================")
print("C = Quet san pham")
print("Q = Thoat")
print("===================================")

try:

    while True:

        ret, frame = cap.read()

        if not ret:
            print("Khong doc duoc webcam!")
            break

        # Hiển thị hướng dẫn
        cv2.putText(
            frame,
            "C = Scan | Q = Quit",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2
        )

        cv2.imshow(
            "PBL5 - Product Scanner",
            frame
        )

        key = cv2.waitKey(1) & 0xFF

        # ==================================
        # NHẤN C ĐỂ QUÉT
        # ==================================

        if key == ord("c") or key == ord("C"):

            print("\nDang quet barcode...")

            success, decoded_info, decoded_type, points = \
                detector.detectAndDecodeWithType(frame)

            barcode_found = False

            if success:

                for barcode, barcode_type in zip(
                    decoded_info,
                    decoded_type
                ):

                    if barcode:

                        barcode_found = True

                        print("----------------------------")
                        print("QUET BARCODE THANH CONG")
                        print("Barcode:", barcode)
                        print("Loai:", barcode_type)

                        # ==============================
                        # TRA DATABASE
                        # ==============================

                        cursor.execute("""
                            SELECT name, price, location
                            FROM products
                            WHERE barcode = ?
                        """, (barcode,))

                        product = cursor.fetchone()

                        # ==============================
                        # NẾU TÌM THẤY
                        # ==============================

                        if product:

                            name, price, location = product

                            print()
                            print("TIM THAY SAN PHAM!")
                            print("----------------------------")
                            print("Ten:", name)
                            print(
                                "Gia:",
                                f"{price:,}",
                                "VND"
                            )
                            print("Vi tri:", location)
                            print("----------------------------")

                        # ==============================
                        # KHÔNG TÌM THẤY
                        # ==============================

                        else:

                            print()
                            print(
                                "SAN PHAM KHONG CO "
                                "TRONG DATABASE!"
                            )

                            print(
                                "Barcode:",
                                barcode
                            )

            if not barcode_found:

                print(
                    "Khong doc duoc barcode. "
                    "Hay dieu chinh san pham va thu lai."
                )

        # ==================================
        # THOÁT
        # ==================================

        elif (
            key == ord("q")
            or key == ord("Q")
            or key == 27
        ):
            break

except KeyboardInterrupt:

    print("\nDa dung chuong trinh.")

finally:

    cap.release()
    conn.close()
    cv2.destroyAllWindows()

    print("Da dong webcam.")