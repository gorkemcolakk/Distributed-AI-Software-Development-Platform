import google.generativeai as genai

# Buraya kendi API anahtarını yaz
genai.configure(api_key="api.key")

print("Senin API anahtarın için kullanılabilir modeller:")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print("-", m.name)