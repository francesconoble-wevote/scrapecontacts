import os
import re
import requests
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

# Domains to exclude when scraping social links
EXCLUDE_DOMAINS = ['ballotpedia', '.gov']

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
    # Fallback via SerpAPI omitted for brevity
    return None


def find_campaign_site(bp_url):
    if not bp_url:
        return None
    try:
        resp = requests.get(bp_url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        text = soup.get_text(separator=' ').lower()
        # Only proceed if mentions campaign site
        if 'campaign site' not in text and 'campaign website' not in text:
            return None
        # Infobox and anchor-text extraction logic (omitted for brevity)
        return None  # Placeholder for actual detection
    except requests.RequestException:
        return None


def extract_social_links(url):
    if not url:
        return {}
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        links = [a['href'] for a in soup.find_all('a', href=True)]
        socials = {}
        for name, pat in SOCIAL_PATTERNS.items():
            for link in links:
                l = link.lower()
                if any(ex in l for ex in EXCLUDE_DOMAINS):
                    continue
                if re.search(pat, link, re.IGNORECASE):
                    socials[name] = link
                    break
        return socials
    except requests.RequestException:
        return {}


def get_candidate_socials(name):
    bp = find_ballotpedia_url(name)
    camp = find_campaign_site(bp)
    socials_bp = extract_social_links(bp)
    socials_camp = extract_social_links(camp) if camp else {}
    return bp, camp, socials_bp, socials_camp

# Streamlit UI
st.title("Ballotpedia Social Scraper")
name = st.text_input('Candidate Name')
lookup = st.button('Lookup')

# Initialize session state once
if 'lookup_done' not in st.session_state:
    st.session_state.lookup_done = False
    st.session_state.bp = None
    st.session_state.camp = None
    st.session_state.socials_bp = {}
    st.session_state.socials_camp = {}
    st.session_state.manual = ''

# Perform lookup
if lookup and name:
    bp, camp, sbp, scap = get_candidate_socials(name)
    st.session_state.bp = bp
    st.session_state.camp = camp
    st.session_state.socials_bp = sbp
    st.session_state.socials_camp = scap
    st.session_state.lookup_done = True
    st.session_state.manual = ''

# Show results only after pressing Lookup
if st.session_state.lookup_done:
    # Ballotpedia URL
    if st.session_state.bp:
        st.markdown(f"**Ballotpedia Page:** [Link]({st.session_state.bp})")
    else:
        st.error('Ballotpedia page not found.')

    # Campaign site display or manual input
    if st.session_state.bp:
        if st.session_state.camp:
            st.markdown(f"**Campaign Site:** [Link]({st.session_state.camp})")
        else:
            st.warning('Campaign site not found on Ballotpedia.')
            manual = st.text_input('Enter campaign site URL manually', value=st.session_state.manual)
            if manual and manual != st.session_state.camp:
                st.session_state.manual = manual
                st.session_state.camp = manual
                st.session_state.socials_camp = extract_social_links(manual)
            # If manual was entered, show it
            if st.session_state.manual:
                st.markdown(f"**Campaign Site:** [Link]({st.session_state.manual})")

    # After both Ballotpedia and campaign URL exist
    if st.session_state.bp and st.session_state.camp:
        merged = {**st.session_state.socials_bp, **st.session_state.socials_camp}
        if merged:
            st.subheader('Social Media Links')
            for plat, link in merged.items():
                st.write(f"- **{plat}:** {link}")
        else:
            st.info('No social media links found.')
