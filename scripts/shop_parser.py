"""Download all product images from a WooCommerce shop.

Given a shop URL, this script walks through all categories and
products, saving product images into a local directory structure.

Example:
    python shop_parser.py https://fialki-ok.ru/shop/
"""
from __future__ import annotations

import os
import re
from urllib.parse import urlparse
from typing import Iterable

import requests
from bs4 import BeautifulSoup


INVALID_CHARS = re.compile(r'[\\/:*?"<>|]')


def sanitize(name: str) -> str:
    """Return ``name`` stripped of characters that are invalid in filenames."""
    return INVALID_CHARS.sub('_', name).strip()


def download_image(url: str, path: str) -> None:
    """Download ``url`` to ``path`` creating parent folders if needed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    response = requests.get(url, stream=True, timeout=10)
    response.raise_for_status()
    with open(path, 'wb') as file:
        for chunk in response.iter_content(chunk_size=8192):
            file.write(chunk)


def parse_product(url: str, base_dir: str) -> None:
    """Download all images for a single product page."""
    html = requests.get(url, timeout=10).text
    soup = BeautifulSoup(html, 'html.parser')

    title_tag = soup.select_one('h1.product_title')
    if not title_tag:
        return
    title = sanitize(title_tag.get_text(strip=True))
    product_dir = os.path.join(base_dir, title)
    os.makedirs(product_dir, exist_ok=True)

    images: Iterable[str] = [
        img.get('src')
        for img in soup.select('div.woocommerce-product-gallery__image img')
        if img.get('src')
    ]
    for index, img_url in enumerate(images, 1):
        parsed = urlparse(img_url)
        ext = os.path.splitext(parsed.path)[1] or '.jpg'
        filename = f"{title} - {index}{ext}"
        download_image(img_url, os.path.join(product_dir, filename))


def parse_category(url: str, base_dir: str) -> None:
    """Parse a category page, recursing into subcategories and products."""
    os.makedirs(base_dir, exist_ok=True)
    html = requests.get(url, timeout=10).text
    soup = BeautifulSoup(html, 'html.parser')

    # Recurse into subcategories
    for cat_link in soup.select('ul.children li.cat-item a'):
        name = sanitize(cat_link.get_text(strip=True))
        new_dir = os.path.join(base_dir, name)
        parse_category(cat_link.get('href'), new_dir)

    # Download products on this page
    for prod_link in soup.select(
        'ul.products li.product a.woocommerce-LoopProduct-link'
    ):
        parse_product(prod_link.get('href'), base_dir)

    # Handle pagination
    next_link = soup.select_one('a.next')
    if next_link and next_link.get('href'):
        parse_category(next_link['href'], base_dir)


def parse_shop(url: str) -> None:
    """Entry point for parsing the entire shop tree starting at ``url``."""
    parsed = urlparse(url)
    root_dir = os.path.join('img', parsed.netloc, parsed.path.strip('/'))
    os.makedirs(root_dir, exist_ok=True)

    html = requests.get(url, timeout=10).text
    soup = BeautifulSoup(html, 'html.parser')

    for cat_link in soup.select('ul.product-categories li a'):
        name = sanitize(cat_link.get_text(strip=True))
        parse_category(cat_link.get('href'), os.path.join(root_dir, name))


if __name__ == '__main__':
    import sys

    if len(sys.argv) != 2:
        print('Usage: python shop_parser.py <shop_url>')
        raise SystemExit(1)

    parse_shop(sys.argv[1])
