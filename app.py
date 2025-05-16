import re
import requests
from bs4 import BeautifulSoup
import streamlit as st

# Request headers to mimic a browser
REQUEST_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/114.0.0.0 Safari/537.36'
    )
}

# Regex patterns
PHONE_PATTERN = re.compile(r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
EMAIL_PATTERN = re.compile(r"[\w\.-]+@[\w\.-]+")
PO_PATTERN = re.compile(r"\bP\.?\s*O\.?\s*Box\b", re.IGNORECASE)
ZIP_PATTERN = re.compile(r"\d{5}(?:-\d{4})?")


def extract_contact_info(url: str):
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        st.error(f"Error fetching URL: {e}")
        return [], [], []

    soup = BeautifulSoup(resp.text, 'html.parser')
    text = soup.get_text(separator='\n', strip=True)

    # Addresses
    addresses = []
    for tag in soup.find_all('address'):
        addr = tag.get_text(separator=' ', strip=True)
        if addr:
            addresses.append(addr)
    # Lines with ZIP or PO Box
    for line in text.split('\n'):
        if ZIP_PATTERN.search(line) or PO_PATTERN.search(line):
            line = line.strip()
            if line not in addresses:
                addresses.append(line)

    # Phones
    phones = PHONE_PATTERN.findall(text)

    # Emails
    emails = EMAIL_PATTERN.findall(text)

    # Deduplicate
    return list(dict.fromkeys(addresses)), list(dict.fromkeys(phones)), list(dict.fromkeys(emails))

# Streamlit UI
st.title("Campaign Site Contact Scraper")
st.write("Enter a campaign website URL to extract addresses, phone numbers, and email addresses.")

url_input = st.text_input("Campaign Site URL", placeholder="https://www.example.com")
if st.button("Extract Contact Info") and url_input:
    # Normalize URL
    if not url_input.startswith(('http://', 'https://')):
        url_input = 'https://' + url_input
    st.info(f"Fetching data from: {url_input}")

    addrs, phones, emails = extract_contact_info(url_input)

    st.subheader("Addresses")
    if addrs:
        for a in addrs:
            st.write(f"- {a}")
    else:
        st.write("No addresses found.")

    st.subheader("Phone Numbers")
    if phones:
        for p in phones:
            st.write(f"- {p}")
    else:
        st.write("No phone numbers found.")

    st.subheader("Email Addresses")
    if emails:
        for e in emails:
            st.write(f"- {e}")
    else:
        st.write("No email addresses found.")
