import os
import re
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
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

# Allowed domains for each platform
ALLOWED_SOCIAL_DOMAINS = {
    'Twitter':  {'twitter.com', 'www.twitter.com', 'x.com', 'www.x.com'},
    'Facebook': {'facebook.com', 'www.facebook.com'},
    'Instagram':{'instagram.com', 'www.instagram.com'},
    'Youtube':  {'youtube.com', 'www.youtube.com', 'youtu.be'},
    'Tiktok':   {'tiktok.com', 'www.tiktok.com'},
    'Linkedin': {'linkedin.com', 'www.linkedin.com'},
    'Threads':  {'threads.net', 'www.threads.net'},
    'Bluesky':  {'bsky.app', 'www.bsky.app'},
}

# Domains to exclude when scraping social links
EXCLUDE_DOMAINS = ['.gov', 'wix']

# Campaign detection exclusions
CAMPAIGN_EXCLUDE = ['jotform.com', 'docs.google.com', 'forms.google.com']

# Headers to mimic a browser
HEADERS = {'User-Agent': 'Mozilla/5.0'}


def find_ballotpedia_url(name):
    slug = name.replace(' ', '_')
    url = f"https://ballotpedia.org/{slug}"
    try:
        r = requests.head(url, headers=HEADERS, allow_redirects=True, timeout=5)
        if r.status_code < 400:
            return url
    except requests.RequestException:
        pass
    # Fallback via SerpAPI could go here
    return None


def find_campaign_site(bp_url):
    """Find the first external link on the Ballotpedia page that isn't BP or excluded."""
    if not bp_url:
        return None
    try:
        resp = requests.get(bp_url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            lhref = href.lower()
            if not href.startswith('http'):
                continue
            # skip Ballotpedia itself and common excludes
            if 'ballotpedia' in lhref or any(ex in lhref for ex in CAMPAIGN_EXCLUDE):
                continue
            return href
    except requests.RequestException:
        pass
    return None


def extract_infobox_socials(bp_url):
    """Grab the social links from Ballotpedia’s infobox table."""
    socials = {}
    if not bp_url:
        return socials
    try:
        r = requests.get(bp_url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        box = soup.find('table', class_='infobox')
        if not box:
            return socials

        for row in box.find_all('tr'):
            header = row.find('th')
            link = row.find('a', href=True)
            if not header or not link:
                continue
            label = header.get_text(strip=True).lower()
            href = link['href']
            lhref = href.lower()
            if not href.startswith('http'):
                continue
            # match by label or by pattern
            for platform, pat in SOCIAL_PATTERNS.items():
                if platform.lower() in label or re.search(pat, href, re.IGNORECASE):
                    # skip share-widget redirects
                    if 'special:redirect/media' in lhref or 'sharer.php' in lhref:
                        continue
                    # skip generic excludes
                    if any(ex in lhref for ex in EXCLUDE_DOMAINS):
                        continue
                    socials[platform] = href
        return socials
    except requests.RequestException:
        return {}


def extract_social_links(url):
    """Scrape raw <a> tags, but only keep true, direct links—
       no share widgets and no links mentioning 'ballotpedia' or any EXCLUDE_DOMAINS."""
    socials = {}
    if not url:
        return socials
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')

        for platform, pat in SOCIAL_PATTERNS.items():
            for a in soup.find_all('a', href=re.compile(pat, re.IGNORECASE)):
                href = a['href']
                lhref = href.lower()

                # skip anything that mentions 'ballotpedia' or any excluded substring (e.g. wix)
                if 'ballotpedia' in lhref or any(ex in lhref for ex in EXCLUDE_DOMAINS):
                    continue

                # parse domain
                parsed = urlparse(href)
                domain = parsed.netloc.lower().split(':')[0]

                # only accept official social domains
                if domain in ALLOWED_SOCIAL_DOMAINS.get(platform, set()):
                    socials[platform] = href
                    break

        return socials

    except requests.RequestException:
        return {}


def get_candidate_socials(name):
    bp = find_ballotpedia_url(name)
    camp = find_campaign_site(bp)
    # Ballotpedia socials = infobox + body
    sb_infobox = extract_infobox_socials(bp)
    sb_body = extract_social_links(bp)
    socials_bp = {**sb_infobox, **sb_body}
    # campaign-site socials = body only
    socials_camp = extract_social_links(camp) if camp else {}
    return bp, camp, socials_bp, socials_camp


# --- Streamlit UI ---

st.title("Ballotpedia Social Scraper")

name = st.text_input('Candidate Name')
lookup = st.button('Lookup')

# Initialize session state
if 'lookup_done' not in st.session_state:
    st.session_state.lookup_done = False
    st.session_state.bp = None
    st.session_state.camp = None
    st.session_state.socials_bp = {}
    st.session_state.socials_camp = {}
    st.session_state.camp_confirmed = None
    st.session_state.manual = ''

# Perform lookup
if lookup and name:
    bp, camp, sbp, scap = get_candidate_socials(name)
    st.session_state.bp = bp
    st.session_state.camp = camp
    st.session_state.socials_bp = sbp
    st.session_state.socials_camp = scap
    st.session_state.lookup_done = True
    st.session_state.camp_confirmed = None
    st.session_state.manual = ''

# After lookup, show Ballotpedia and campaign logic
if st.session_state.lookup_done:
    # Ballotpedia link
    if st.session_state.bp:
        st.markdown(f"**Ballotpedia Page:** [Link]({st.session_state.bp})")
    else:
        st.error('Ballotpedia page not found.')

    # Campaign site detection
    if st.session_state.bp:
        if st.session_state.camp and st.session_state.camp_confirmed is None:
            st.subheader("Detected Campaign Site")
            st.markdown(f"[{st.session_state.camp}]({st.session_state.camp})")
            col1, col2 = st.columns(2)
            if col1.button("Accept Campaign Site"):
                st.session_state.camp_confirmed = True
            if col2.button("Reject Campaign Site"):
                st.session_state.camp_confirmed = False

        # If accepted, show all socials
        if st.session_state.camp_confirmed:
            merged = {**st.session_state.socials_bp, **st.session_state.socials_camp}
            if merged:
                st.subheader('Social Media Links')
                for plat, link in merged.items():
                    st.write(f"- **{plat}:** {link}")
            else:
                st.info('No social media links found.')

        # If rejected or no campaign found, allow manual entry
        if st.session_state.camp_confirmed is False or (st.session_state.camp is None):
            if st.session_state.camp_confirmed is False:
                st.warning("Please provide the correct campaign site URL:")
            manual = st.text_input('Manual Campaign Site URL', value=st.session_state.manual)
            if st.button("Lookup Manual Campaign Site"):
                st.session_state.manual = manual
                st.session_state.camp = manual
                st.session_state.socials_camp = extract_social_links(manual)
                st.session_state.camp_confirmed = True

            # After manual lookup and confirmation, display socials
            if st.session_state.camp_confirmed and st.session_state.manual:
                merged = {**st.session_state.socials_bp, **st.session_state.socials_camp}
                if merged:
                    st.subheader('Social Media Links')
                    for plat, link in merged.items():
                        st.write(f"- **{plat}:** {link}")
                else:
                    st.info('No social media links found.')
