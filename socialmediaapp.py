import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from serpapi import GoogleSearch
import streamlit as st

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
# Additional domains to exclude for campaign detection
CAMPAIGN_EXCLUDE = ['jotform.com', 'docs.google.com', 'forms.google.com']

# Common request headers to mimic a browser
REQUEST_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/114.0.0.0 Safari/537.36'
    )
}


def find_ballotpedia_url(candidate_name, max_pages=2):
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
            'engine': 'google', 'q': query,
            'start': page*10, 'num': 10,
            'gl': 'us', 'hl': 'en',
            'api_key': os.getenv('SERPAPI_API_KEY')
        }
        results = GoogleSearch(params).get_dict().get('organic_results', [])
        for res in results:
            for field in ('link','url','unified_url','displayed_link'):
                u = res.get(field, '')
                if 'ballotpedia.org' in u:
                    return u
    return None


def find_campaign_site(candidate_bp_url, candidate_name=None):
    if not candidate_bp_url:
        return None
    try:
        resp = requests.get(candidate_bp_url, headers=REQUEST_HEADERS, timeout=10)
        resp.raise_for_status()
        page_text = BeautifulSoup(resp.text, 'html.parser').get_text(separator=' ').lower()
        if 'campaign site' not in page_text and 'campaign website' not in page_text:
            return None
        soup = BeautifulSoup(resp.text, 'html.parser')
        infobox = soup.find('table', class_='infobox')
        if infobox:
            for row in infobox.find_all('tr'):
                th = row.find('th'); td = row.find('td')
                if th and td and 'contact' in th.get_text(strip=True).lower():
                    for a in td.find_all('a', href=True):
                        href = a['href']; l = href.lower()
                        if href.startswith('http') and not any(x in l for x in ['mailto:','ballotpedia','.gov']+CAMPAIGN_EXCLUDE):
                            return href
            for row in infobox.find_all('tr'):
                th = row.find('th'); td = row.find('td')
                if th and td:
                    lbl = th.get_text(strip=True).lower()
                    if any(key in lbl for key in ('campaign website','campaign site','official website')):
                        a = td.find('a', href=True)
                        if a:
                            href = a['href']; l = href.lower()
                            if href.startswith('http') and not any(x in l for x in ['.gov']+CAMPAIGN_EXCLUDE):
                                return href
        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True).lower()
            href = a['href']; l = href.lower()
            if any(k in text for k in ('campaign site','campaign website')) and href.startswith('http') and not any(x in l for x in ['ballotpedia','.gov']+CAMPAIGN_EXCLUDE):
                return href
    except requests.RequestException:
        pass
    return None


def extract_social_links(url):
    if not url:
        return {}
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        links = [a['href'] for a in soup.find_all('a', href=True)]
        socials = {}
        for name, pat in SOCIAL_PATTERNS.items():
            for lnk in links:
                l = lnk.lower()
                if any(x in l for x in ['ballotpedia','.gov']):
                    continue
                if re.search(pat, lnk, re.IGNORECASE):
                    socials[name] = lnk
                    break
        return socials
    except requests.RequestException:
        return {}


def get_candidate_socials(candidate_name):
    bp = find_ballotpedia_url(candidate_name)
    if not bp:
        st.error(f"❌ No Ballotpedia page found for {candidate_name}")
        return
    camp = find_campaign_site(bp, candidate_name)
    socials_bp = extract_social_links(bp)
    socials_camp = extract_social_links(camp) if camp else {}
    return bp, camp, {**socials_bp, **socials_camp}

# Streamlit UI
st.title("Ballotpedia Social Scraper")
name = st.text_input('Candidate Name')
if 'bp' not in st.session_state:
    st.session_state['bp'] = None
    st.session_state['camp'] = None
    st.session_state['socials'] = {}

if st.button('Lookup') and name:
    st.session_state['bp'], st.session_state['camp'], st.session_state['socials'] = get_candidate_socials(name)

if st.session_state['bp']:
    st.markdown(f"**Ballotpedia Page:** [Link]({st.session_state['bp']})")
else:
    st.warning('Ballotpedia page not found.')

if st.session_state['camp']:
    st.markdown(f"**Campaign Site:** [Link]({st.session_state['camp']})")
else:
    st.warning('Campaign site not found.')
    manual = st.text_input('Manual campaign site URL')
    if manual:
        st.session_state['camp'] = manual
        st.session_state['socials'] = extract_social_links(manual)
        st.markdown(f"**Campaign Site:** [Link]({manual})")

if st.session_state['socials']:
    st.subheader('Social Media Links')
    for p, link in st.session_state['socials'].items():
        st.write(f"- **{p}:** {link}")
else:
    st.info('No social media links found.')
