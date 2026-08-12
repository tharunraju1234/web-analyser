"""
Core analysis: crawls a site's key pages (home, about, pricing, testimonials,
contact), extracting structured data and raw text for each. AI-based
interpretation (ratings, summaries, pricing justification) lives in
ollama_client.py and is orchestrated by app.py.
"""
import re
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

SOCIAL_DOMAINS = {
    "facebook.com": "Facebook",
    "instagram.com": "Instagram",
    "twitter.com": "Twitter/X",
    "x.com": "Twitter/X",
    "linkedin.com": "LinkedIn",
    "youtube.com": "YouTube",
    "tiktok.com": "TikTok",
    "pinterest.com": "Pinterest",
}

PRODUCT_KEYWORDS = ["product", "shop", "store", "services", "solutions", "pricing", "catalog"]

PAGE_TYPE_KEYWORDS = {
    "about": ["about", "who-we-are", "our-story", "company"],
    "pricing": ["pricing", "plans", "price"],
    "contact": ["contact", "get-in-touch", "reach-us"],
    "testimonials": ["testimonial", "review", "case-stud", "success-stor"],
}


def fetch_page(url: str, browser=None, timeout_ms: int = 20000) -> dict:
    """
    Loads a page with real Chrome. If `browser` is passed (an already-launched
    Playwright browser), reuses it - lets a multi-page crawl share one Chrome
    instance instead of launching a new one per page.
    """
    own_playwright = browser is None
    p = None
    if own_playwright:
        p = sync_playwright().start()
        browser = p.chromium.launch(channel="chrome", headless=True)

    page = browser.new_page()
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        page.wait_for_timeout(1200)
        html = page.content()
        status = response.status if response else None
        final_url = page.url
    finally:
        page.close()
        if own_playwright:
            browser.close()
            p.stop()

    return {"html": html, "status": status, "final_url": final_url}


def extract_company_info(soup: BeautifulSoup, base_url: str) -> dict:
    name = None
    og_site = soup.find("meta", property="og:site_name")
    if og_site and og_site.get("content"):
        name = og_site["content"].strip()
    if not name and soup.title and soup.title.string:
        name = soup.title.string.strip()
    if not name:
        h1 = soup.find("h1")
        if h1:
            name = h1.get_text(strip=True)

    products = []
    for a in soup.find_all("a", href=True):
        link_text = a.get_text(strip=True)
        if not link_text or len(link_text) > 40:
            continue
        if any(kw in link_text.lower() for kw in PRODUCT_KEYWORDS):
            if link_text not in products:
                products.append(link_text)
    products = products[:10]

    location = None
    addr_tag = soup.find(attrs={"itemtype": re.compile("PostalAddress", re.I)})
    if addr_tag:
        location = addr_tag.get_text(" ", strip=True)
    if not location:
        footer = soup.find("footer")
        search_text = footer.get_text(" ", strip=True) if footer else soup.get_text(" ", strip=True)
        match = re.search(r'\d{1,5}\s+[A-Za-z0-9.,\s]{5,60}?(?:Street|St|Ave|Avenue|Road|Rd|Blvd|Lane|Ln|Drive|Dr)\b[^.]{0,40}', search_text)
        if not match:
            match = re.search(r'[A-Z][a-zA-Z]+,\s?[A-Z]{2}\s?\d{5}', search_text)
        if match:
            location = match.group(0).strip()

    social_handles = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        full = urljoin(base_url, href)
        domain = urlparse(full).netloc.lower().replace("www.", "")
        for social_domain, label in SOCIAL_DOMAINS.items():
            if social_domain in domain and label not in social_handles:
                social_handles[label] = full

    return {"name": name, "products": products, "location": location, "social_handles": social_handles}


def check_robots_and_sitemap(base_url: str) -> dict:
    parsed = urlparse(base_url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    result = {"robots_txt": False, "sitemap_xml": False}
    for path, key in [("/robots.txt", "robots_txt"), ("/sitemap.xml", "sitemap_xml")]:
        try:
            r = requests.get(root + path, timeout=8)
            result[key] = r.status_code == 200
        except requests.RequestException:
            result[key] = False
    return result


def compute_seo_score(soup: BeautifulSoup, base_url: str, robots_info: dict) -> dict:
    checks = {}
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    checks["title_present"] = bool(title)
    checks["title_good_length"] = 10 <= len(title) <= 60

    meta_desc = soup.find("meta", attrs={"name": "description"})
    desc_content = meta_desc["content"].strip() if meta_desc and meta_desc.get("content") else ""
    checks["meta_description_present"] = bool(desc_content)
    checks["meta_description_good_length"] = 50 <= len(desc_content) <= 160

    h1_tags = soup.find_all("h1")
    checks["single_h1"] = len(h1_tags) == 1

    imgs = soup.find_all("img")
    imgs_with_alt = [i for i in imgs if i.get("alt", "").strip()]
    checks["images_have_alt"] = (len(imgs_with_alt) / len(imgs)) >= 0.8 if imgs else True

    checks["has_canonical"] = bool(soup.find("link", rel="canonical"))
    checks["has_viewport_meta"] = bool(soup.find("meta", attrs={"name": "viewport"}))
    checks["is_https"] = base_url.lower().startswith("https://")
    checks["has_robots_txt"] = robots_info.get("robots_txt", False)
    checks["has_sitemap_xml"] = robots_info.get("sitemap_xml", False)

    passed = sum(1 for v in checks.values() if v)
    total = len(checks)
    score = round((passed / total) * 100)
    return {"score": score, "checks": checks}


def extract_meta_tags(soup: BeautifulSoup) -> dict:
    meta = {}
    for tag in soup.find_all("meta"):
        key = tag.get("name") or tag.get("property")
        content = tag.get("content")
        if key and content:
            meta[key] = content
    html_tag = soup.find("html")
    meta["_lang"] = html_tag.get("lang") if html_tag else None
    charset_tag = soup.find("meta", charset=True)
    meta["_charset"] = charset_tag.get("charset") if charset_tag else None
    return meta


def extract_structured_data(soup: BeautifulSoup) -> list:
    import json
    blocks = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            blocks.append(data)
        except (json.JSONDecodeError, TypeError):
            continue
    return blocks


def extract_contact_info(soup: BeautifulSoup, visible_text: str) -> dict:
    emails = set()
    phones = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("mailto:"):
            emails.add(href.replace("mailto:", "").split("?")[0].strip())
        if href.startswith("tel:"):
            phones.add(href.replace("tel:", "").strip())
    text_emails = re.findall(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}', visible_text)
    emails.update(text_emails)
    text_phones = re.findall(r'(?:\+?\d{1,3}[\s.-]?)?\(?\d{3,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}', visible_text)
    for p in text_phones:
        digits = re.sub(r'\D', '', p)
        if 7 <= len(digits) <= 15:
            phones.add(p.strip())
    return {"emails": sorted(emails)[:10], "phones": sorted(phones)[:10]}


def extract_headings(soup: BeautifulSoup) -> list:
    headings = []
    for level in range(1, 7):
        for tag in soup.find_all(f"h{level}"):
            text = tag.get_text(strip=True)
            if text:
                headings.append({"level": level, "text": text})
    return headings[:40]


def extract_images_info(soup: BeautifulSoup, base_url: str) -> dict:
    imgs = soup.find_all("img")
    with_alt = [i for i in imgs if i.get("alt", "").strip()]
    without_alt = [i for i in imgs if not i.get("alt", "").strip()]
    sample = []
    for img in imgs[:12]:
        src = img.get("src") or img.get("data-src") or ""
        if src:
            sample.append({"src": urljoin(base_url, src), "alt": img.get("alt", "")})
    return {"total": len(imgs), "with_alt": len(with_alt), "without_alt": len(without_alt), "sample": sample}


def extract_links_info(soup: BeautifulSoup, base_url: str) -> dict:
    domain = urlparse(base_url).netloc.replace("www.", "")
    internal, external = 0, 0
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        full = urljoin(base_url, href)
        link_domain = urlparse(full).netloc.replace("www.", "")
        if link_domain == domain or not link_domain:
            internal += 1
        else:
            external += 1
    return {"internal": internal, "external": external, "total": internal + external}


def detect_technology(html: str, soup: BeautifulSoup) -> list:
    detected = []
    signatures = {
        "WordPress": ["wp-content", "wp-includes"],
        "Shopify": ["cdn.shopify.com", "Shopify.theme"],
        "Wix": ["static.wixstatic.com", "wix.com"],
        "Squarespace": ["squarespace.com", "static1.squarespace.com"],
        "React": ["__reactContainer", "react-dom", "data-reactroot"],
        "Next.js": ["__NEXT_DATA__", "_next/static"],
        "Vue.js": ["__vue__", "vue.js", "vue.min.js"],
        "Webflow": ["webflow.js", "webflow.com"],
        "Google Analytics": ["googletagmanager.com", "google-analytics.com"],
        "Cloudflare": ["cloudflare.com", "cf-ray"],
        "jQuery": ["jquery.min.js", "jquery.js"],
        "Bootstrap": ["bootstrap.min.css", "bootstrap.css"],
        "Tailwind CSS": ["tailwindcss", "tailwind.css"],
    }
    generator = soup.find("meta", attrs={"name": "generator"})
    generator_content = generator["content"] if generator and generator.get("content") else ""
    if generator_content:
        detected.append(generator_content)
    for name, markers in signatures.items():
        if name.lower() in generator_content.lower():
            continue
        if any(marker.lower() in html.lower() for marker in markers):
            if name not in detected:
                detected.append(name)
    return detected


def extract_favicon(soup: BeautifulSoup, base_url: str):
    for rel in ["icon", "shortcut icon", "apple-touch-icon"]:
        tag = soup.find("link", rel=lambda x: x and rel in x.lower() if x else False)
        if tag and tag.get("href"):
            return urljoin(base_url, tag["href"])
    return None


def get_visible_text(soup: BeautifulSoup, limit: int = 4000) -> str:
    soup_copy = BeautifulSoup(str(soup), "html.parser")
    for tag in soup_copy(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup_copy.get_text(separator=" ", strip=True)
    return re.sub(r'\s+', ' ', text)[:limit]


def extract_testimonials_heuristic(soup: BeautifulSoup) -> list:
    """Approximate - scans blockquotes and elements with testimonial/review-ish class names."""
    testimonials = []
    seen_texts = set()

    for bq in soup.find_all("blockquote"):
        text = bq.get_text(" ", strip=True)
        if text and 15 < len(text) < 600 and text not in seen_texts:
            testimonials.append({"quote": text, "author": None})
            seen_texts.add(text)

    for tag in soup.find_all(class_=re.compile(r'testimonial|review-item|review-card', re.I)):
        text = tag.get_text(" ", strip=True)
        if text and 15 < len(text) < 600 and text not in seen_texts:
            testimonials.append({"quote": text, "author": None})
            seen_texts.add(text)

    return testimonials[:8]


def classify_page(url: str, link_text: str):
    combined = (url + " " + link_text).lower()
    for ptype, keywords in PAGE_TYPE_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            return ptype
    return None


def discover_site_pages(soup: BeautifulSoup, base_url: str, max_pages: int = 8) -> list:
    """Scans nav/footer links for About/Pricing/Contact/Testimonials-type pages on the same domain."""
    domain = urlparse(base_url).netloc.replace("www.", "")
    seen = set()
    candidates = []

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        link_domain = parsed.netloc.replace("www.", "")
        if link_domain != domain:
            continue
        clean = full.split("#")[0].rstrip("/")
        if clean in seen or clean == base_url.rstrip("/"):
            continue
        seen.add(clean)

        link_text = a.get_text(strip=True)
        ptype = classify_page(clean, link_text)
        if ptype:
            candidates.append({"url": clean, "label": link_text or ptype.title(), "type": ptype})

    deduped = {}
    for p in candidates:
        if p["type"] not in deduped:
            deduped[p["type"]] = p
    return list(deduped.values())[:max_pages]


def analyze_site(url: str) -> dict:
    """
    Full crawl: home page + any About/Pricing/Contact/Testimonials pages found
    via nav links. Returns raw extracted data - AI interpretation (ratings,
    summaries) is layered on top by app.py using ollama_client.
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)

        home_fetch = fetch_page(url, browser=browser)
        home_soup = BeautifulSoup(home_fetch["html"], "html.parser")
        base_url = home_fetch["final_url"]

        company_info = extract_company_info(home_soup, base_url)
        robots_info = check_robots_and_sitemap(base_url)
        seo_result = compute_seo_score(home_soup, base_url, robots_info)
        home_visible_text = get_visible_text(home_soup)
        meta_tags = extract_meta_tags(home_soup)
        structured_data = extract_structured_data(home_soup)
        headings = extract_headings(home_soup)
        images_info = extract_images_info(home_soup, base_url)
        links_info = extract_links_info(home_soup, base_url)
        technology = detect_technology(home_fetch["html"], home_soup)
        favicon = extract_favicon(home_soup, base_url)
        word_count = len(home_visible_text.split())
        home_testimonials = extract_testimonials_heuristic(home_soup)
        home_contact_info = extract_contact_info(home_soup, home_visible_text)

        discovered_pages = discover_site_pages(home_soup, base_url)

        sub_pages = {}
        for page in discovered_pages:
            try:
                sub_fetch = fetch_page(page["url"], browser=browser)
                sub_soup = BeautifulSoup(sub_fetch["html"], "html.parser")
                sub_text = get_visible_text(sub_soup, limit=5000)
                entry = {"url": page["url"], "label": page["label"], "visible_text": sub_text}
                if page["type"] == "contact":
                    entry["contact_info"] = extract_contact_info(sub_soup, sub_text)
                    entry["social_handles"] = extract_company_info(sub_soup, page["url"])["social_handles"]
                if page["type"] == "testimonials":
                    entry["testimonials_heuristic"] = extract_testimonials_heuristic(sub_soup)
                sub_pages[page["type"]] = entry
            except Exception as e:
                sub_pages[page["type"]] = {"url": page["url"], "label": page["label"], "error": str(e)}

        browser.close()

    return {
        "url": base_url,
        "status": home_fetch["status"],
        "company_info": company_info,
        "seo": seo_result,
        "meta_tags": meta_tags,
        "structured_data": structured_data,
        "headings": headings,
        "images_info": images_info,
        "links_info": links_info,
        "technology": technology,
        "favicon": favicon,
        "word_count": word_count,
        "home_visible_text": home_visible_text,
        "home_testimonials": home_testimonials,
        "home_contact_info": home_contact_info,
        "discovered_pages": discovered_pages,
        "sub_pages": sub_pages,
    }