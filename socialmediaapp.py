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

# Domains to exclude when scraping social links (added 'wix')
EXCLUDE_DOMAINS = ['ballotpedia', '.gov', 'wix']

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
            # skip Ballotpedia internals and excluded domains
            if 'ballotpedia.org' in lhref or any(ex in lhref for ex in CAMPAIGN_EXCLUDE):
                continue
            return href
        return None
    except requests.RequestException:
        return None


def extract_social_links(url):
    if not url:
        return {}
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        socials = {}
        for name, pat in SOCIAL_PATTERNS.items():
            match = soup.find('a', href=re.compile(pat, re.IGNORECASE))
            if match:
                href = match['href']
                lhref = href.lower()
                # skip excluded domains including wix
                if any(ex in lhref for ex in EXCLUDE_DOMAINS):
                    continue
                socials[name] = href
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

# Initialize session state
if 'lookup_done' not in st.session_state:
    st.session_state.lookup_done = False
    st.session_state.bp = None
    st.session_state.camp = None
    st.session_state.socials_bp = {}
    st.session_state.socials_camp = {}
    st.session_state.manual = ''
    st.session_state.confirm = None

# Perform lookup
if lookup and name:
    bp, camp, sbp, scap = get_candidate_socials(name)
    st.session_state.bp = bp
    st.session_state.camp = camp
    st.session_state.socials_bp = sbp
    st.session_state.socials_camp = scap
    st.session_state.lookup_done = True
    st.session_state.manual = ''
    st.session_state.confirm = None

# Show results after lookup
if st.session_state.lookup_done:
    # Ballotpedia URL
    if st.session_state.bp:
        st.markdown(f"**Ballotpedia Page:** [Link]({st.session_state.bp})")
    else:
        st.error('Ballotpedia page not found.')

    # Campaign site detection + user confirmation
    if st.session_state.bp:
        if st.session_state.camp:
            st.subheader("Detected Campaign Site")
            st.markdown(f"[{st.session_state.camp}]({st.session_state.camp})")
            st.session_state.confirm = st.radio(
                "Is this the correct campaign site?",
                ("Yes", "No"),
                key="confirm_site"
            )
            if st.session_state.confirm == "No":
                manual = st.text_input(
                    'Enter campaign site URL manually',
                    value=st.session_state.manual,
                    key="manual_site"
                )
                if manual and manual != st.session_state.camp:
                    st.session_state.manual = manual
                    st.session_state.camp = manual
                    st.session_state.socials_camp = extract_social_links(manual)
        else:
            st.warning('Campaign site not found on Ballotpedia.')
            manual = st.text_input(
                'Enter campaign site URL manually',
                value=st.session_state.manual,
                key="manual_site"
            )
            if manual:
                st.session_state.manual = manual
                st.session_state.camp = manual
                st.session_state.socials_camp = extract_social_links(manual)

        # If user provided manual URL, show it
        if st.session_state.manual:
            st.markdown(f"**Campaign Site:** [Link]({st.session_state.manual})")

    # Merge and display social links
    if st.session_state.bp and st.session_state.camp:
        merged = {**st.session_state.socials_bp, **st.session_state.socials_camp}
        if merged:
            st.subheader('Social Media Links')
            for plat, link in merged.items():
                st.write(f"- **{plat}:** {link}")
        else:
            st.info('No social media links found.')
