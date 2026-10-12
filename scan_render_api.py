import cv2
import requests


# Trong giai doan chua noi RC522, tam thoi dung cua hang STORE001.
# Sau nay bien nay se duoc thay bang Store ID doc tu RFID.
STORE_ID = "STORE001"
API_URL = "https://pbl5-render-api.onrender.com/product.php"


def tim_san_pham(store_id, product_id):
    """Gui Store ID va Product ID len PHP API, sau do in ket qua."""
    params = {
        "id": store_id,
        "product": product_id,
    }

    print("\nDang gui du lieu len server...")
    print("Store ID:", store_id)
    print("Product ID:", product_id)

    try:
        response = requests.get(API_URL, params=params, timeout=90)
        print("URL da gui:", response.url)
        print("HTTP status:", response.status_code)

        # API cua du an luon tra JSON, ke ca khi khong tim thay san pham.
        data = response.json()

        if data.get("success"):
            print("--------------------------------")
            print("TIM THAY SAN PHAM")
            print("Ten san pham:", data.get("name"))
            print("Gia:", data.get("price"))
            print("Vi tri:", data.get("location"))
            print("Han su dung:", data.get("expiry_date"))
            print("--------------------------------")
        else:
            print("SERVER KHONG TIM THAY SAN PHAM")
            print("Thong bao:", data.get("message"))

    except requests.exceptions.JSONDecodeError:
        print("Server khong tra ve JSON hop le.")
        print("Noi dung nhan duoc:", response.text)
    except requests.exceptions.RequestException as error:
        print("Khong ket noi duoc PHP API tren Render.")
        print("Chi tiet loi:", error)


cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Khong mo duoc webcam!")
    raise SystemExit(1)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

detector = cv2.barcode.BarcodeDetector()

print("===================================")
print("PBL5 - BARCODE GUI LEN RENDER")
print("C = Quet barcode va tim san pham")
print("Q / ESC = Thoat")
print("Cua hang tam thoi:", STORE_ID)
print("===================================")

try:
    while True:
        ret, frame = cap.read()

        if not ret:
            print("Khong doc duoc hinh anh tu webcam.")
            break

        cv2.putText(
            frame,
            f"Store: {STORE_ID} | C = Scan | Q = Quit",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )

        cv2.imshow("PBL5 - Barcode to Render API", frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord("c") or key == ord("C"):
            print("\nDang quet barcode...")

            success, decoded_info, decoded_type, points = (
                detector.detectAndDecodeWithType(frame)
            )

            barcode_found = False

            if success:
                for barcode, barcode_type in zip(decoded_info, decoded_type):
                    barcode = barcode.strip()

                    if barcode:
                        barcode_found = True
                        print("Quet barcode thanh cong!")
                        print("Ma:", barcode)
                        print("Loai:", barcode_type)

                        # Chi gui request sau khi camera da giai ma thanh cong.
                        tim_san_pham(STORE_ID, barcode)

            if not barcode_found:
                print("Khong doc duoc barcode. Hay dieu chinh san pham va nhan C lai.")

        elif key == ord("q") or key == ord("Q") or key == 27:
            break

except KeyboardInterrupt:
    print("\nDa dung chuong trinh.")
finally:
    cap.release()
    cv2.destroyAllWindows()
    print("Da dong webcam.")
