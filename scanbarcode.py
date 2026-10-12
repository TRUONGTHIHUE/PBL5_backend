import cv2

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Không mở được webcam!")
    exit()

# Tạo Barcode Detector
detector = cv2.barcode.BarcodeDetector()

print("Đưa barcode sản phẩm trước camera.")
print("Nhấn Q để thoát.")

last_barcode = None

while True:
    ret, frame = cap.read()

    if not ret:
        break

    # Phát hiện + giải mã barcode
    success, decoded_info, decoded_type, points = detector.detectAndDecodeWithType(frame)

    if success:
        for barcode, barcode_type in zip(decoded_info, decoded_type):

            if barcode and barcode != last_barcode:
                print("----------------------------")
                print("Đã quét được barcode!")
                print("Mã:", barcode)
                print("Loại:", barcode_type)

                last_barcode = barcode

    cv2.imshow("PBL5 - Barcode Scanner", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()