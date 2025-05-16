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
CAMPAIGN_EXCLUDE = ['jotform.com', 'docs.google.com']

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
    Checks for 'campaign site' text on Ballotpedia page before scraping.
    If present, extracts the official campaign site by:
      1) Infobox 'Contact' section: first external link (non-gov, non-excluded)
      2) Infobox labels: 'campaign website', 'campaign site', 'official website'
      3) Fallback: other external links preferring candidate slug
    """
    if not candidate_bp_url:
        return None
    try:
        resp = requests.get(candidate_bp_url, headers=REQUEST_HEADERS, timeout=10)
        resp.raise_for_status()
        html = resp.text
        # Only proceed if page mentions 'campaign site' or 'campaign website'
        page_text = BeautifulSoup(html, 'html.parser').get_text(separator=' ').lower()
        if 'campaign site' not in page_text and 'campaign website' not in page_text:
            return None

        soup = BeautifulSoup(html, 'html.parser')
        infobox = soup.find('table', class_='infobox')
        if infobox:
            # 1) Contact row
            for row in infobox.find_all('tr'):
                th = row.find('th')
                td = row.find('td')
                if th and td and 'contact' in th.get_text(strip=True).lower():
                    for a in td.find_all('a', href=True):
                        href = a['href']
                        href_l = href.lower()
                        if (href.startswith('http') and
                                'mailto:' not in href_l and
                                'ballotpedia' not in href_l and
                                '.gov' not in href_l and
                                not any(ex in href_l for ex in CAMPAIGN_EXCLUDE)):
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
                        href_l = href.lower()
                        if (href.startswith('http') and
                                '.gov' not in href_l and
                                not any(ex in href_l for ex in CAMPAIGN_EXCLUDE)):
                            return href
        # 3) Fallback: any other external, non-gov, non-social, non-excluded link
        all_links = [a['href'] for a in soup.find_all('a', href=True)]
        external = [l for l in all_links
                    if (l.startswith('http') and
                        'ballotpedia' not in l.lower() and
                        not l.lower().startswith('mailto:') and
                        not any(dom in l for dom in SOCIAL_DOMAINS) and
                        '.gov' not in l.lower() and
                        not any(ex in l.lower() for ex in CAMPAIGN_EXCLUDE))]
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
                l_l = link.lower()
                if 'ballotpedia' in l_l or '.gov' in l_l:
                    continue
                if re.search(pattern, link, re.IGNORECASE):
                    social_links[name] = link
                    break
        return social_links
    except requests.RequestException:
        return {}


def get_candidate_socials(candidate_name):
    """Returns {'ballotpedia_url': url_or_None, 'campaign_site': url_or_None, 'social_links': {...}}"""
    bp_url = find_ballotpedia_url(candidate_name)
    if not bp_url:
        st.error(f"❌ No Ballotpedia page found for {candidate_name}")
        return {'ballotpedia_url': None, 'campaign_site': None, 'social_links': {}}

    campaign_site = find_campaign_site(bp_url, candidate_name)
    socials_bp = extract_social_links(bp_url)
    socials_cam = extract_social_links(campaign_site) if campaign_site else {}
    merged = {}
    for platform in SOCIAL_PATTERNS:
        if platform in socials_cam:
            merged[platform] = socials_cam[platform]
        elif platform in socials_bp:
            merged[platform] = socials_bp[platform]

    return {'ballotpedia_url': bp_url, 'campaign_site': campaign_site, 'social_links': merged}

# Streamlit UI
st.title("Ballotpedia Social Scraper")
candidate = st.text_input('Candidate Name', '')
if st.button('Lookup'):
    result = get_candidate_socials(candidate)
    bp = result['ballotpedia_url']
    camp = result['campaign_site']
    socials = result['social_links']

    if bp:
        st.markdown(f"**Ballotpedia Page:** [Link]({bp})")
    else:
        st.warning('Ballotpedia page not found.')

    if camp:
        st.markdown(f"**Campaign Site:** [Link]({camp})")
    else:
        st.warning('Campaign site not found.')
        # Prompt for manual campaign URL
        manual = st.text_input('Enter campaign site URL manually')
        if manual:
            camp = manual
            st.markdown(f"**Campaign Site:** [Link]({camp})")
            socials = extract_social_links(camp)

    if socials:
        st.subheader('Social Media Links')
        for plat, link in socials.items():
            st.write(f"- **{plat}:** {link}")
    else:
        st.info('No social media links found.')
