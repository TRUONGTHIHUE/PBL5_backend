import cv2
import time

# =========================
# MỞ WEBCAM
# =========================
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Không mở được webcam!")
    exit()

# Tăng độ phân giải webcam
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

# Tạo detector một lần duy nhất
detector = cv2.barcode.BarcodeDetector()

# Danh sách barcode đã quét
scanned_barcodes = []

print("===================================")
print("PBL5 - THU THAP BARCODE SAN PHAM")
print("===================================")
print("C : Chụp và quét barcode")
print("R : Xóa danh sách barcode đã quét")
print("L : Xem danh sách barcode")
print("Q / ESC : Thoát")
print("===================================")

try:
    while True:

        ret, frame = cap.read()

        if not ret:
            print("Không đọc được webcam.")
            break

        # Hiển thị số lượng mã đã quét
        text = f"Products scanned: {len(scanned_barcodes)}"

        cv2.putText(
            frame,
            text,
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2
        )

        cv2.putText(
            frame,
            "C = Scan | L = List | Q = Quit",
            (20, 75),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        cv2.imshow("PBL5 - Barcode Scanner", frame)

        key = cv2.waitKey(1) & 0xFF

        # ==================================
        # NHẤN C - CHỤP VÀ QUÉT
        # ==================================
        if key == ord("c") or key == ord("C"):

            print("\nĐang chụp...")

            # Lưu ảnh riêng theo thời gian
            filename = f"barcode_{int(time.time())}.jpg"

            cv2.imwrite(filename, frame)

            print("Đã lưu ảnh:", filename)
            print("Đang quét barcode...")

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

                        print("--------------------------------")
                        print("QUÉT THÀNH CÔNG")
                        print("Barcode:", barcode)
                        print("Loại:", barcode_type)

                        # Kiểm tra barcode đã có chưa
                        if barcode not in scanned_barcodes:

                            scanned_barcodes.append(barcode)

                            print("Đã thêm vào danh sách!")
                            print(
                                "Tổng số sản phẩm:",
                                len(scanned_barcodes)
                            )

                        else:
                            print("Mã này đã được quét trước đó!")

                        print("--------------------------------")

            if not barcode_found:

                print("KHÔNG ĐỌC ĐƯỢC BARCODE.")
                print("Hãy thử:")
                print("- Giữ sản phẩm yên")
                print("- Đưa barcode gần hơn / xa hơn")
                print("- Tránh ánh sáng phản chiếu")
                print("- Đảm bảo camera lấy nét")
                print("- Nhấn C để chụp lại")

        # ==================================
        # NHẤN L - XEM DANH SÁCH
        # ==================================
        elif key == ord("l") or key == ord("L"):

            print("\n========== DANH SÁCH BARCODE ==========")

            if len(scanned_barcodes) == 0:

                print("Chưa có sản phẩm nào.")

            else:

                for i, barcode in enumerate(
                    scanned_barcodes,
                    start=1
                ):
                    print(f"{i}. {barcode}")

            print("========================================")

        # ==================================
        # NHẤN R - RESET
        # ==================================
        elif key == ord("r") or key == ord("R"):

            scanned_barcodes.clear()

            print("\nĐã xóa danh sách barcode.")

        # ==================================
        # THOÁT
        # ==================================
        elif (
            key == ord("q")
            or key == ord("Q")
            or key == 27
        ):
            print("\nĐang thoát...")
            break

except KeyboardInterrupt:

    # Ctrl + C sẽ không còn hiện traceback dài
    print("\nBạn đã dừng chương trình bằng Ctrl + C.")

finally:

    cap.release()
    cv2.destroyAllWindows()

    print("\n===================================")
    print("CÁC BARCODE ĐÃ QUÉT")
    print("===================================")

    for i, barcode in enumerate(
        scanned_barcodes,
        start=1
    ):
        print(f"{i}. {barcode}")

    print("===================================")
    print("Đã đóng webcam.")