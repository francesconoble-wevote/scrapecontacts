import os
import re
import requests
from bs4 import BeautifulSoup
from serpapi import GoogleSearch
import streamlit as st

# Regex patterns for social media
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
# Domains to exclude
EXCLUDE_DOMAINS = ['ballotpedia', '.gov']
# Request headers
REQUEST_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/114.0.0.0 Safari/537.36'
    )
}

# Functions

def find_ballotpedia_url(name, max_pages=2):
    slug = name.replace(' ', '_')
    url = f"https://ballotpedia.org/{slug}"
    try:
        r = requests.head(url, headers=REQUEST_HEADERS, allow_redirects=True, timeout=5)
        if r.status_code < 400:
            return url
    except requests.RequestException:
        pass
    query = f"{name} Ballotpedia site:ballotpedia.org"
    for page in range(max_pages):
        params = {
            'engine': 'google', 'q': query,
            'start': page*10, 'num': 10,
            'gl': 'us', 'hl': 'en',
            'api_key': os.getenv('SERPAPI_API_KEY')
        }
        results = GoogleSearch(params).get_dict().get('organic_results', [])
        for res in results:
            for field in ('link','url','displayed_link'):
                u = res.get(field, '')
                if 'ballotpedia.org' in u:
                    return u
    return None


def find_campaign_site(bp_url, name=None):
    try:
        r = requests.get(bp_url, headers=REQUEST_HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        # Infobox contact
        infobox = soup.find('table', class_='infobox')
        if infobox:
            for tr in infobox.find_all('tr'):
                th = tr.find('th')
                td = tr.find('td')
                if th and td and 'contact' in th.get_text(strip=True).lower():
                    for a in td.find_all('a', href=True):
                        href = a['href']
                        if href.startswith('http') and not any(dom in href for dom in EXCLUDE_DOMAINS):
                            return href
        # Fallback
        links = [a['href'] for a in soup.find_all('a', href=True)]
        external = [l for l in links if l.startswith('http') and not any(dom in l for dom in EXCLUDE_DOMAINS)]
        if name:
            slug = name.replace(' ', '_').lower()
            for l in external:
                if slug in l.lower():
                    return l
        return external[0] if external else None
    except:
        return None


def extract_social_links(site_url):
    try:
        r = requests.get(site_url, headers=REQUEST_HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        links = [a['href'] for a in soup.find_all('a', href=True)]
        socials = {}
        for name, pat in SOCIAL_PATTERNS.items():
            for l in links:
                if re.search(pat, l, re.IGNORECASE) and not any(dom in l for dom in EXCLUDE_DOMAINS):
                    socials[name] = l
                    break
        return socials
    except:
        return {}


def get_candidate_socials(name):
    bp = find_ballotpedia_url(name)
    campaign = find_campaign_site(bp, name) if bp else None
    socials = extract_social_links(campaign) if campaign else {}
    return bp, campaign, socials

# Streamlit UI
st.title("Ballotpedia Campaign & Social Scraper")
name = st.text_input("Candidate Name", "")
if st.button("Lookup"):
    bp_url, camp_url, socials = get_candidate_socials(name)
    if bp_url:
        st.markdown(f"**Ballotpedia URL:** [Link]({bp_url})")
    else:
        st.warning("Ballotpedia page not found.")
    if camp_url:
        st.markdown(f"**Campaign Site:** [Link]({camp_url})")
    else:
        st.warning("Campaign site not found.")
    if socials:
        st.subheader("Social Media Links")
        for k, v in socials.items():
            st.markdown(f"- **{k}:** [Link]({v})")
    else:
        st.info("No social media links found.")
