import os
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote, unquote, urljoin, urlparse
import threading
import sys


REQUEST_TIMEOUT = (5, 30)
DOWNLOADABLE_SCHEMES = ('http', 'https')
LOCAL_HOSTS = ('localhost', '127.0.0.1', '::1')
SCHEME_PREFIX = re.compile(r'^([A-Za-z][A-Za-z0-9+.\-]*)://')
UNSAFE_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED_FILENAMES = {'CON', 'PRN', 'AUX', 'NUL'} | {
    f'{prefix}{index}' for prefix in ('COM', 'LPT') for index in range(1, 10)
}


def sanitize_filename(segment):
    cleaned = UNSAFE_FILENAME_CHARS.sub('_', segment).strip().rstrip('.')
    if not cleaned:
        return None
    if cleaned.split('.')[0].upper() in RESERVED_FILENAMES:
        cleaned = f'_{cleaned}'
    return cleaned


def local_asset_path(url):
    parsed = urlparse(url)
    if parsed.scheme and parsed.scheme not in DOWNLOADABLE_SCHEMES:
        return None

    segments = []
    for segment in unquote(parsed.path).split('/'):
        if not segment or segment == '.':
            continue
        if segment == '..':
            return None
        safe_segment = sanitize_filename(segment)
        if safe_segment is None:
            return None
        segments.append(safe_segment)

    if not segments:
        return None
    return os.path.join(*segments)


def download_file(url, folder):
    relative_path = local_asset_path(url)
    if relative_path is None:
        return None

    local_file_path = os.path.join(folder, relative_path)
    os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

    response = requests.get(url, stream=True, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    with open(local_file_path, 'wb') as file:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file.write(chunk)
    return relative_path


def iter_asset_references(soup):
    for tag in soup.find_all(['link', 'script', 'img']):
        if tag.name == 'link':
            relations = [relation.lower() for relation in tag.get('rel', [])]
            if 'stylesheet' not in relations:
                continue
            attribute = 'href'
        else:
            attribute = 'src'

        value = tag.get(attribute)
        if value:
            yield tag, attribute, value


def download_website(url, folder):
    os.makedirs(folder, exist_ok=True)

    response = requests.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')

    html_file_path = os.path.join(folder, 'index.html')
    with open(html_file_path, 'wb') as file:
        file.write(response.content)

    for tag, attribute, value in iter_asset_references(soup):
        asset_url = urljoin(url, value)
        try:
            relative_path = download_file(asset_url, folder)
        except (requests.RequestException, OSError) as error:
            print(f'Skipped {asset_url}: {error}', file=sys.stderr)
            continue

        if relative_path is None:
            print(f'Skipped unsupported asset URL: {asset_url}', file=sys.stderr)
            continue

        tag[attribute] = quote(relative_path.replace(os.sep, '/'))

    with open(html_file_path, 'w', encoding='utf-8') as file:
        file.write(str(soup))


def animate_download(stop_event):
    """Display an animated 'Downloading...' message with dots."""
    dots = ['.', '..', '...']
    while not stop_event.is_set():
        for dot in dots:
            if stop_event.is_set():
                return
            sys.stdout.write("\rDownloading" + dot)
            sys.stdout.flush()
            if stop_event.wait(0.5):
                return
            sys.stdout.write("\r" + " " * (len("Downloading" + dot)) + "\r")
            sys.stdout.flush()


def default_scheme(bare_host):
    authority = bare_host.split('/', 1)[0].rsplit('@', 1)[-1]
    if authority.startswith('['):
        host = authority[1:].split(']')[0]
    else:
        host = authority.split(':')[0]
    return 'http' if host.lower() in LOCAL_HOSTS else 'https'


def normalize_url(raw_url):
    candidate = raw_url.strip()
    if not candidate:
        raise ValueError('No URL entered.')

    match = SCHEME_PREFIX.match(candidate)
    if match:
        if match.group(1).lower() not in DOWNLOADABLE_SCHEMES:
            raise ValueError(f'Unsupported URL scheme "{match.group(1)}" in: {candidate}')
    else:
        bare_host = candidate[2:] if candidate.startswith('//') else candidate
        candidate = f'{default_scheme(bare_host)}://{bare_host}'

    if not urlparse(candidate).hostname:
        raise ValueError(f'Could not read a host name from: {candidate}')
    return candidate


def main():
    try:
        website_url = normalize_url(input("Enter the URL of the website to download: "))
    except ValueError as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(1)

    website_name = sanitize_filename(urlparse(website_url).hostname) or 'site'
    output_folder = f'{website_name}_download'

    stop_animation = threading.Event()
    animation_thread = threading.Thread(
        target=animate_download, args=(stop_animation,), daemon=True
    )
    animation_thread.start()

    failure = None
    try:
        download_website(website_url, output_folder)
    except requests.RequestException as error:
        failure = error
    finally:
        stop_animation.set()
        animation_thread.join(timeout=1)

    if failure is not None:
        print(f'Download failed: {failure}', file=sys.stderr)
        sys.exit(1)

    sys.stdout.write("\rDownload complete!\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
