import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import os
import re
from urllib.parse import urljoin, urlparse
from PIL import Image
from io import BytesIO

# 1. Setup
output_dir = "doctor_photos"
os.makedirs(output_dir, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

def sanitize_filename(name):
    return re.sub(r'[^a-zA-Z0-9_\-]', '', str(name).replace(' ', '_'))

def resolve_image_url(src, page_url):
    """
    Manipal uses src="../uploads/doctors_photo/..."
    urljoin() resolves ../ one level up from the slug, giving the WRONG path.
    The correct path is always at the domain root: /uploads/doctors_photo/...
    So we strip all leading ../ and build from the domain root.
    """
    parsed = urlparse(page_url)
    domain_root = f"{parsed.scheme}://{parsed.netloc}"

    # Strip all leading ../ or ./ from the relative path
    clean_src = re.sub(r'^(\.\.\/|\.\/)+', '', src)

    # Build from domain root
    return f"{domain_root}/{clean_src}"

def run_scraper():
    print("Loading Doctor Dump from Excel...")
    df = pd.read_excel('Doctor dump.xlsx', sheet_name='Doctor Dump')
    df.columns = df.columns.str.strip()

    success_count = 0
    fail_count = 0

    for index, row in df.iterrows():
        doc_name = row.get('Doctor Name')
        url = row.get('doctor_profile_url')

        if pd.isna(url) or not str(url).startswith('http'):
            print(f"[{index}] Skipping {doc_name}: Invalid URL.")
            fail_count += 1
            continue

        safe_name = sanitize_filename(doc_name)
        file_path = f"{output_dir}/{safe_name}.jpg"

        if os.path.exists(file_path):
            print(f"[{index}] Already have {doc_name}. Skipping...")
            success_count += 1
            continue

        try:
            print(f"[{index}] Fetching {doc_name}...")
            response = requests.get(url, headers=HEADERS, timeout=10)

            if response.status_code != 200:
                print(f"  -> Failed: HTTP {response.status_code}")
                fail_count += 1
                continue

            soup = BeautifulSoup(response.text, 'html.parser')

            # PRIMARY: Exact selector confirmed from Manipal DevTools + raw HTML inspection.
            # <div class="img-doc-appont"> contains <img class="img-responsive img_profile">
            img_tags = soup.select('.img-doc-appont img.img_profile')

            # FALLBACK 1: Relax to just the parent div in case img class varies
            if not img_tags:
                img_tags = soup.select('.img-doc-appont img')

            # FALLBACK 2: Match by the confirmed uploads path in src
            if not img_tags:
                img_tags = [
                    tag for tag in soup.find_all('img')
                    if 'uploads/doctors_photo' in (tag.get('src') or tag.get('data-src') or '')
                ]

            # FALLBACK 3: Search by doctor's first name in alt text
            if not img_tags:
                first_name = str(doc_name).replace('Dr.', '').strip().split()[0]
                img_tags = soup.find_all('img', alt=re.compile(first_name, re.I))

            image_saved = False

            # Test every found tag until one works
            for tag in img_tags:
                # Manipal uses loading="lazy" with src — also check data-src
                src = tag.get('data-src') or tag.get('src')

                if not src:
                    continue

                src_lower = src.lower()

                # THE BLACKLIST: Reject anything that is clearly not a doctor portrait
                garbage_keywords = ['.svg', 'icon', 'logo', 'default', 'avatar',
                                    'placeholder', 'dummy', 'banner', 'illustration',
                                    'razorpay', 'payment', 'spinner', 'loading',
                                    'news', 'blog', 'patient', 'stock']
                if any(word in src_lower for word in garbage_keywords):
                    continue

                # KEY FIX: Manipal uses "../uploads/..." relative URLs.
                # Strip the ../ and resolve from domain root instead of urljoin.
                if src.startswith('..') or src.startswith('./'):
                    test_url = resolve_image_url(src, url)
                else:
                    test_url = urljoin(url, src)

                print(f"  -> Trying: {test_url}")

                # Try to download this specific URL
                img_response = requests.get(test_url, headers=HEADERS, timeout=10)

                if img_response.status_code == 200:
                    try:
                        img = Image.open(BytesIO(img_response.content))

                        # Reject images too small to be a portrait (icons, logos)
                        if img.width < 80 or img.height < 80:
                            print(f"  -> Skipping too-small image {img.width}x{img.height}: {src}")
                            continue

                        img = img.convert('RGB')
                        img.save(file_path, 'JPEG')

                        print(f"  -> Success: Saved {safe_name}.jpg  ({img.width}x{img.height})")
                        image_saved = True
                        success_count += 1
                        break
                    except Exception:
                        continue
                else:
                    print(f"  -> HTTP {img_response.status_code} for {test_url}")

            if not image_saved:
                print(f"  -> Failed: No valid doctor photo found for {doc_name}")
                fail_count += 1

        except Exception as e:
            print(f"  -> Error fetching {doc_name}: {e}")
            fail_count += 1

        # Do not remove the sleep. Respect the target server.
        time.sleep(2)

    print(f"\nScraping Complete. Success: {success_count} | Failed: {fail_count}")

if __name__ == "__main__":
    run_scraper()