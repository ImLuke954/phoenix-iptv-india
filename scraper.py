import os
import re
import shutil

import requests


SOURCE_PLAYLISTS_MD = "https://raw.githubusercontent.com/iptv-org/iptv/master/PLAYLISTS.md"
BASE_URL = "https://iptv-org.github.io/iptv/"
USER_REPO_URL = "https://imluke954.github.io/phoenix-iptv-india/"


def fetch(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def blocks(content):
    lines = content.splitlines()
    header = []
    result = []
    current = None
    for line in lines:
        if line.startswith("#EXTINF:"):
            if current:
                result.append(current)
            current = [line]
        elif current is not None:
            current.append(line)
        elif line.startswith("#EXTM3U"):
            header.append(line)
    if current:
        result.append(current)
    return header, result


def render(header, entries):
    return "\n".join(header + [line for entry in entries for line in entry]) + "\n"


def indian_entries(content):
    header, entries = blocks(content)
    entries = [
        entry for entry in entries
        if re.search(r'tvg-id="[^"]+\.in(?:@|")', entry[0], re.IGNORECASE)
    ]
    return header, entries


def assamese_entries(content):
    header, entries = blocks(content)
    for entry in entries:
        if 'group-title="' in entry[0]:
            entry[0] = re.sub(r'group-title="[^"]*"', 'group-title="Assames"', entry[0], count=1)
        else:
            entry[0] = entry[0].replace("#EXTINF:-1 ", '#EXTINF:-1 group-title="Assames" ', 1)
    return header, entries


def write(path, content):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def clean_old_files():
    for name in ("categories", "languages", "regions", "cities", "india"):
        if os.path.isdir(name):
            shutil.rmtree(name)
    for name in ("index.category.m3u", "index.country.m3u", "index.language.m3u", "nettv_nepal.m3u"):
        if os.path.isfile(name):
            os.remove(name)


def generate_site(category_names):
    links = [("India - All Channels", f"{USER_REPO_URL}india/index.m3u")]
    links += [(name.capitalize(), f"{USER_REPO_URL}india/categories/{name}.m3u") for name in category_names]
    links.append(("Assames", f"{USER_REPO_URL}india/assames.m3u"))
    readme = "# 📺 India IPTV Playlist Hub\n\nIndia-only IPTV playlists, updated hourly from [iptv-org/iptv](https://github.com/iptv-org/iptv).\n\n"
    readme += f"## Playlist URL\n{USER_REPO_URL}\n\n| Category | M3U Link |\n| --- | --- |\n"
    for name, url in links:
        readme += f"| {name} | [`{url}`]({url}) |\n"
    write("README.md", readme)

    cards = "".join(
        f'<div class="col-md-4"><div class="card p-3"><h5>{name}</h5><code>{url}</code><a href="{url}" class="btn btn-primary btn-sm mt-2">Copy M3U Link</a></div></div>'
        for name, url in links
    )
    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>India IPTV Playlist Hub</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"><style>body{{background:#121212;color:#e0e0e0}}.card{{background:#1e1e1e;border:1px solid #333;margin-bottom:20px}}code{{color:#03dac6;word-break:break-all}}.btn-primary{{background:#bb86fc;border:0;color:#000}}</style></head><body class="py-5"><main class="container"><h1 class="text-center mb-4">📺 India IPTV Playlist Hub</h1><p class="text-center text-muted">India-only playlists updated from iptv-org/iptv</p><div class="row">{cards}</div></main></body></html>'''
    write("index.html", html)


def scrape():
    print("Starting India-only scrape...")
    source = fetch(SOURCE_PLAYLISTS_MD)
    category_links = sorted(set(re.findall(r'https://iptv-org\.github\.io/iptv/categories/[\w./-]+\.m3u', source)))
    if not category_links:
        raise RuntimeError("No category playlists found")

    clean_old_files()
    all_entries = []
    names = []
    for link in category_links:
        name = link.rsplit("/", 1)[-1][:-4]
        print(f"Filtering India channels from {name}.m3u...")
        header, entries = indian_entries(fetch(link))
        write(f"india/categories/{name}.m3u", render(header, entries))
        all_entries.extend(entries)
        names.append(name)

    print("Downloading Assamese playlist...")
    header, entries = assamese_entries(fetch(f"{BASE_URL}languages/asm.m3u"))
    write("india/assames.m3u", render(header, entries))
    combined = []
    seen_urls = set()
    for entry in all_entries:
        stream_url = entry[-1]
        if stream_url not in seen_urls:
            seen_urls.add(stream_url)
            combined.append(entry)
    # Keep Assamese entries even when the same stream is already present in
    # another category, so IPTV players can display the Assames group.
    combined.extend(entries)
    write("india/index.m3u", render(["#EXTM3U"], combined))
    generate_site(names)
    print(f"India-only scrape completed: {len(names)} categories.")


if __name__ == "__main__":
    scrape()
