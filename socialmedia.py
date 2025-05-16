import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from serpapi import GoogleSearch

# Social media regex patterns
SOCIAL_PATTERNS = {
    'Twitter': r'(twitter\.com|x\.com)/',
    'Facebook': r'facebook\.com/',
    'Instagram': r'instagram\.com/',
    'Youtube': r'youtube\.com/',
    'Tiktok': r'tiktok\.com/',
    'Linkedin': r'linkedin\.com/',
    'Threads': r'threads\.net/',
    'Bluesky': r'bsky\.app/',
}

# Domains to exclude when searching for campaign site
SOCIAL_DOMAINS = [
    'twitter.com', 'x.com', 'facebook.com', 'instagram.com',
    'youtube.com', 'tiktok.com', 'linkedin.com', 'threads.net', 'bsky.app'
]

# Common request headers to mimic a browser
REQUEST_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/114.0.0.0 Safari/537.36'
    )
}


def find_ballotpedia_url(candidate_name, max_pages=2):
    """
    1) Try canonical URL: https://ballotpedia.org/First_Last
    2) Fallback: SerpAPI search for Ballotpedia page
    """
    slug = candidate_name.replace(' ', '_')
    url = f"https://ballotpedia.org/{slug}"
    try:
        resp = requests.head(url, headers=REQUEST_HEADERS, allow_redirects=True, timeout=5)
        if resp.status_code < 400:
            return url
    except requests.RequestException:
        pass

    query = f"{candidate_name} Ballotpedia site:ballotpedia.org"
    for page in range(max_pages):
        params = {
            'engine': 'google',
            'q': query,
            'start': page * 10,
            'num': 10,
            'gl': 'us',
            'hl': 'en',
            'api_key': os.getenv('SERPAPI_API_KEY')
        }
        results = GoogleSearch(params).get_dict().get('organic_results', [])
        for res in results:
            for field in ('link', 'url', 'unified_url', 'displayed_link'):
                candidate_url = res.get(field)
                if candidate_url and 'ballotpedia.org' in candidate_url:
                    return candidate_url
    return None


def find_campaign_site(candidate_bp_url, candidate_name=None):
    """
    Extracts the candidate's official campaign site by:
      1) Infobox 'Contact' section: first external link (non-gov)
      2) Infobox labels: 'campaign website', 'campaign site', 'official website' (non-gov)
      3) Fallback: external links preferring ones containing the candidate slug (non-gov)
    """
    if not candidate_bp_url:
        return None
    try:
        resp = requests.get(candidate_bp_url, headers=REQUEST_HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        infobox = soup.find('table', class_='infobox')
        if infobox:
            # 1) Contact row
            for row in infobox.find_all('tr'):
                th = row.find('th')
                td = row.find('td')
                if th and td and 'contact' in th.get_text(strip=True).lower():
                    for a in td.find_all('a', href=True):
                        href = a['href']
                        if (href.startswith('http') and
                                'mailto:' not in href and
                                'ballotpedia' not in href.lower() and
                                '.gov' not in href.lower()):
                            return href
            # 2) Specific labels
            for row in infobox.find_all('tr'):
                th = row.find('th')
                td = row.find('td')
                if th and td:
                    label = th.get_text(strip=True).lower()
                    if any(key in label for key in ('campaign website', 'campaign site', 'official website')):
                        link_tag = td.find('a', href=True)
                        href = link_tag['href'] if link_tag else ''
                        if href.startswith('http') and '.gov' not in href.lower():
                            return href
        # 3) Fallback: any external, non-gov, non-social link
        all_links = [a['href'] for a in soup.find_all('a', href=True)]
        external = [l for l in all_links
                    if (l.startswith('http') and
                        'ballotpedia' not in l.lower() and
                        not l.lower().startswith('mailto:') and
                        not any(dom in l for dom in SOCIAL_DOMAINS) and
                        '.gov' not in l.lower())]
        if candidate_name:
            slug = candidate_name.replace(' ', '_').lower()
            for link in external:
                if slug in link.lower():
                    return link
        if external:
            return external[0]
    except requests.RequestException:
        pass
    return None


def extract_social_links(url):
    """Scrapes URL, returns social media links filtering out Ballotpedia hosts and .gov."""
    if not url:
        return {}
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        links = [a['href'] for a in soup.find_all('a', href=True)]
        social_links = {}
        for name, pattern in SOCIAL_PATTERNS.items():
            for link in links:
                if 'ballotpedia' in link.lower() or '.gov' in link.lower():
                    continue
                if re.search(pattern, link, re.IGNORECASE):
                    social_links[name] = link
                    break
        return social_links
    except requests.RequestException:
        return {}


def get_candidate_socials(candidate_name):
    """Returns {'campaign_site': url_or_None, 'social_links': {...}}"""
    bp_url = find_ballotpedia_url(candidate_name)
    if not bp_url:
        print(f"❌ No Ballotpedia page found for {candidate_name}")
        return {'campaign_site': None, 'social_links': {}}

    print(f"🔗 Ballotpedia: {bp_url}")
    campaign_site = find_campaign_site(bp_url, candidate_name)
    if campaign_site:
        print(f"🌐 Campaign Site: {campaign_site}")
    else:
        print("⚠️ Campaign site not found.")

    socials_bp = extract_social_links(bp_url)
    socials_cam = extract_social_links(campaign_site) if campaign_site else {}
    merged = {}
    for platform in SOCIAL_PATTERNS:
        if platform in socials_cam:
            merged[platform] = socials_cam[platform]
        elif platform in socials_bp:
            merged[platform] = socials_bp[platform]

    return {'campaign_site': campaign_site, 'social_links': merged}


if __name__ == '__main__':
    candidate = input('Enter candidate name: ').strip()
    result = get_candidate_socials(candidate)
    if result['campaign_site']:
        print(f"🌐 Campaign Site: {result['campaign_site']}")
    if result['social_links']:
        print("📱 Social Media Links:")
        for plat, link in result['social_links'].items():
            print(f"{plat}: {link}")
    if not result['campaign_site'] and not result['social_links']:
        print('No campaign site or social links found.')
