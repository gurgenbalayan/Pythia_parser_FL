import aiohttp
from bs4 import BeautifulSoup
from utils.logger import setup_logger
import os


STATE = os.getenv("STATE")
logger = setup_logger("scraper")



async def fetch_company_details(url: str) -> dict:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                html = await response.text()
                return await parse_html_details(html)
    except Exception as e:
        logger.error(f"Error fetching data for query '{url}': {e}")
        return []
async def fetch_company_data(query: str) -> list[dict]:
    url = (
        f"https://search.sunbiz.org/Inquiry/CorporationSearch/SearchResults/"
        f"EntityName/{query}/Page1?searchNameOrder={query}"
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                html = await response.text()
                return await parse_html_search(html)
    except Exception as e:
        logger.error(f"Error fetching data for query '{query}': {e}")
        return []

async def parse_html_search(html: str) -> list[dict]:
    soup = BeautifulSoup(html, 'html.parser')
    results = []
    table = soup.find('table')
    if table:
        rows = table.find_all('tr')[1:]
        for row in rows:
            cols = row.find_all('td')
            if len(cols) == 3:
                name_tag = cols[0].find('a')
                if name_tag:
                    results.append({
                        "state": STATE,
                        "name": name_tag.text,
                        "status": cols[2].text,
                        "id": cols[1].text,
                        "url": 'https://search.sunbiz.org' + name_tag['href'].replace('&amp;', '&'),
                    })
    return results


async def parse_html_details(html: str) -> dict:
    soup = BeautifulSoup(html, 'html.parser')

    async def get_text_after_label(label_text):
        label = soup.find('label', string=label_text)
        if label and label.find_next_sibling('span'):
            return label.find_next_sibling('span').text
        return ''
    async def extract_address(soup, title):
        section = soup.find('div', class_='detailSection', string=lambda t: t and title in t)
        if not section:
            # ищем по заголовку внутри <span>
            all_sections = soup.find_all('div', class_='detailSection')
            for sec in all_sections:
                span = sec.find('span')
                if span and title.lower() in span.get_text(strip=True).lower():
                    section = sec
                    break
        if section:
            div = section.find('div')
            if div:
                return ', '.join(line.strip() for line in div.stripped_strings)
        return ''

    async def extract_registered_agent_name(soup):
        sections = soup.find_all('div', class_='detailSection')
        for section in sections:
            header_span = section.find('span')
            if header_span and 'registered agent name' in header_span.get_text(strip=True).lower():
                spans = section.find_all('span')
                for s in spans:
                    text = s.get_text(strip=True)
                    if text and 'registered agent name' not in text.lower():
                        return text
        return ''

    async def extract_document_links(soup):
        links = []
        sections = soup.find_all('div', class_='detailSection')
        for section in sections:
            # Находим <span> с текстом "Document Images"
            span = section.find('span')
            if span and 'Document Images' in span.text:
                # Ищем все теги <a> внутри таблицы
                for a_tag in section.find_all('a', href=True):
                    href = a_tag['href']
                    href_text = a_tag.text
                    if href.startswith('/'):
                        href = 'https://search.sunbiz.org' + href
                    links.append({"name": href_text, "link": href})
                break  # нашли нужный блок, дальше не ищем
        return links

    # Name (second <p> in corporationName section)
    corp_section = soup.find('div', class_='detailSection corporationName')
    name = corp_section.find_all('p')[1].text if corp_section else ''

    # Date Registered (Date Filed)
    date_registered = await get_text_after_label("Date Filed")

    # Registration Number
    registration_number = await get_text_after_label("Document Number")

    # Status
    status = await get_text_after_label("Status")

    # Entity Type — from first <p> in corporationName
    entity_type = corp_section.find_all('p')[0].text if corp_section else ''

    # Agent
    agent_name = await extract_registered_agent_name(soup)

    # Address (principal and mailing)
    principal_address = await extract_address(soup, 'Principal Address')
    mailing_address = await extract_address(soup, 'Mailing Address')

    #Documents
    document_images = await extract_document_links(soup)

    return {
        "state": STATE,
        "name": name,
        "status": status,
        "registration_number": registration_number,
        "date_registered": date_registered,
        "entity_type": entity_type,
        "agent_name": agent_name,
        "principal_address": principal_address,
        "mailing_address": mailing_address,
        "document_images": document_images
    }