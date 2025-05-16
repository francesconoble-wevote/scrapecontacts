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
    # fallback SerpAPI logic omitted for brevity
    return None


def find_campaign_site(bp_url):
    if not bp_url:
        return None
    try:
        r = requests.get(bp_url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        text = soup.get_text(separator=' ').lower()
        if 'campaign site' not in text and 'campaign website' not in text:
            return None
        # infobox and anchor-text detection omitted for brevity
        return None  # placeholder
    except:
        return None


def extract_social_links(url):
    if not url:
        return {}
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        links = [a['href'] for a in soup.find_all('a', href=True)]
        socials = {}
        for name, pat in SOCIAL_PATTERNS.items():
            for l in links:
                if any(ex in l.lower() for ex in EXCLUDE_DOMAINS):
                    continue
                if re.search(pat, l, re.IGNORECASE):
                    socials[name] = l
                    break
        return socials
    except:
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
# initialize state
for k in ('bp', 'camp', 'socials_bp', 'socials_camp'):
    if k not in st.session_state:
        st.session_state[k] = None if k != 'socials_bp' and k != 'socials_camp' else {}

if st.button('Lookup') and name:
    bp, camp, sbp, scap = get_candidate_socials(name)
    st.session_state.bp = bp
    st.session_state.camp = camp
    st.session_state.socials_bp = sbp
    st.session_state.socials_camp = scap

# Display Ballotpedia URL
if st.session_state.bp:
    st.markdown(f"**Ballotpedia Page:** [Link]({st.session_state.bp})")
else:
    st.warning('Ballotpedia page not found.')

# Campaign site logic
if st.session_state.bp:
    if st.session_state.camp:
        st.markdown(f"**Campaign Site:** [Link]({st.session_state.camp})")
        # both bp and camp checked, now show socials
        merged = {**st.session_state.socials_bp, **st.session_state.socials_camp}
        if merged:
            st.subheader('Social Media Links')
            for p, link in merged.items():
                st.write(f"- **{p}:** {link}")
        else:
            st.info('No social media links found.')
    else:
        st.warning('Campaign site not found.')
        manual = st.text_input('Manual campaign site URL')
        if manual:
            st.session_state.camp = manual
            st.session_state.socials_camp = extract_social_links(manual)
            # after manual input, trigger UI rerun
            st.experimental_rerun()
