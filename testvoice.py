
from gtts import gTTS

text = "Xin chào. Đây là sữa Vinamilk dâu."

tts = gTTS(
    text=text,
    lang="vi"
)

tts.save("test_vi.mp3")

print("Đã tạo file test_vi.mp3")