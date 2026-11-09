import re
from pathlib import Path

from playwright.sync_api import sync_playwright

IDS = [
    "WXw3Oe9rZ7IvMv9sFR9WMYkt43pkpCC0APZbcXt0EMTNCwbNYHTF8KdGbwZpWg+Wb71Js9wiserMkuuXRAouXW7+ChfbtBFdCb1OkgqkkDvZjAERSMy11nPdRlk+AWW1KjTX5RkztCtXcOzg/9HOy1x2ZgOwaJgV3U+WOQCwJ+UuLNqf6mNZ8xebKdD4EMz3I/Bmcag/EU=",
    "WXw3Oe9rZ7IvMv9sFR9WMYkt43pkpCC0APZbcXt0EMTNCwbNYHTF8KdGbwZpWg%2bWb71Js9wiserMkuuXRAouXW7%2bChfbtBFdCb1OkgqkkDvZjAERSMy11nPdRlk%2bAWW1KjTX5RkztCtXcOzg%2f9HOy1x2ZgOwaJgV3U%2bWOQCwJ%2bUuLNqf6mNZ8xebKdD4EMz3I%2fBmcag%2fEU%3d",
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://rerait.telangana.gov.in/SearchList/Search", wait_until="networkidle")

    for q in IDS:
        result = page.evaluate(
            """async (q) => {
                const token = document.querySelector('input[name="__RequestVerificationToken"]').value;
                const endpoints = [
                  ['/SearchList/showFileApplicationPreviewIframe', { ID: q, Preview: '1' }],
                  ['/Home/ShowPreview', { ID: q, Preview: '1' }],
                  ['/SearchList/showFileApplicationPreview', { ID: q, Preview: '1' }],
                ];
                const out = [];
                for (const [url, body] of endpoints) {
                  const resp = await fetch(url, {
                    method: 'POST',
                    headers: {
                      'Content-Type': 'application/json',
                      'RequestVerificationToken': token,
                      'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify(body)
                  });
                  const text = await resp.text();
                  out.push({ url, status: resp.status, len: text.length, sample: text.slice(0, 200) });
                }
                return out;
            }""",
            q,
        )
        print("=== ID variant ===", q[:40], "...")
        for item in result:
            print(item)

    browser.close()
