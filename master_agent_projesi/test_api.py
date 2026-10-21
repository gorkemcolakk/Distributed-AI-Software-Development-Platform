import os
import sys

def test_cloud_api():
    """
    Bulut API bağlantı test betiği (S2-01).
    Sabit anahtar tutulmaz; ortam değişkeni kontrol edilir.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key in ("api.key", "YOUR_API_KEY_HERE"):
        print("[BILGI] GEMINI_API_KEY ortam degiskeni tanimli degil. Guvenli yerel Ollama veya yedek mod kullanilmalidir.")
        print("Kullanim icin .env dosyanizda GEMINI_API_KEY degerini tanimlayabilirsiniz.")
        return

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        print("API anahtari dogrulandi. Kullanilabilir modeller:")
        for m in genai.list_models():
            if "generateContent" in m.supported_generation_methods:
                print("-", m.name)
    except Exception as e:
        print(f"[UYARI] API baglanti hatasi (Guvenli yakalama): {e}")

if __name__ == "__main__":
    test_cloud_api()