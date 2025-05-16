import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Common request headers to mimic a browser
REQUEST_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/114.0.0.0 Safari/537.36'
    )
}

# Regex patterns for phone, email, and PO Box
PHONE_PATTERN = re.compile(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
EMAIL_PATTERN = re.compile(r"[\w\.-]+@[\w\.-]+")
PO_PATTERN = re.compile(r"\bP\.?\s*O\.?\s*Box\b", re.IGNORECASE)
ZIP_PATTERN = re.compile(r"\d{5}(?:-\d{4})?")


def extract_contact_info(campaign_url):
    """
    Fetches the campaign site URL and extracts:
      - Addresses from <address> tags and lines containing ZIP codes or PO Boxes
      - Phone numbers via regex
      - Emails via regex
    Returns a dict with 'addresses', 'phones', 'emails'.
    """
    try:
        resp = requests.get(campaign_url, headers=REQUEST_HEADERS, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching {campaign_url}: {e}")
        return {'addresses': [], 'phones': [], 'emails': []}

    soup = BeautifulSoup(resp.text, 'html.parser')
    text = soup.get_text(separator='\n', strip=True)

    # 1) Extract <address> tags
    addresses = []
    for addr_tag in soup.find_all('address'):
        addr = addr_tag.get_text(separator=' ', strip=True)
        addresses.append(addr)

    # 2) Heuristic: look for lines with ZIP codes or PO Boxes
    for line in text.split('\n'):
        if ZIP_PATTERN.search(line) or PO_PATTERN.search(line):
            clean = line.strip()
            if clean and clean not in addresses:
                addresses.append(clean)

    # 3) Extract phone numbers
    phones = PHONE_PATTERN.findall(text)

    # 4) Extract emails
    emails = EMAIL_PATTERN.findall(text)

    # Deduplicate
    return {
        'addresses': list(dict.fromkeys(addresses)),
        'phones':   list(dict.fromkeys(phones)),
        'emails':   list(dict.fromkeys(emails))
    }


if __name__ == '__main__':
    raw = input(
        'Enter campaign site (e.g. example.com, www.example.com, https://example.com): '
    ).strip()
    # Normalize URL for requests
    if not raw.startswith(('http://', 'https://')):
        campaign_url = 'https://' + raw
    else:
        campaign_url = raw

    info = extract_contact_info(campaign_url)
    print("\nAddresses:")
    for a in info['addresses']:
        print(f"  - {a}")
    print("\nPhone Numbers:")
    for p in info['phones']:
        print(f"  - {p}")
    print("\nEmail Addresses:")
    for e in info['emails']:
        print(f"  - {e}")
