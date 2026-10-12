import cv2

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Không mở được webcam!")
    exit()

print("Webcam đã mở.")
print("Nhấn Q hoặc ESC để thoát.")

while True:
    ret, frame = cap.read()

    if not ret:
        print("Không đọc được hình ảnh từ webcam.")
        break

    cv2.imshow("PBL5 - Camera", frame)

    # Đọc phím
    key = cv2.waitKey(1) & 0xFF

    # q = 113, Q = 81, ESC = 27
    if key == ord("q") or key == ord("Q") or key == 27:
        print("Đang đóng webcam...")
        break

cap.release()
cv2.destroyAllWindows()

print("Đã đóng webcam.")