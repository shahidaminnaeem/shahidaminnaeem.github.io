"""Refresh public Scholar data through SerpApi. Never expose the private API key."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

AUTHOR = 'IRyoBd8AAAAJ'
TARGET = Path(__file__).resolve().parents[1] / 'data' / 'scholar.json'


def collect(fetch):
    articles, seen, metrics = [], set(), {}
    for page in range(10):
        result = fetch(page * 100)
        if result.get('error'):
            raise ValueError('Provider reported an error')
        if page == 0:
            if not result.get('author'):
                raise ValueError('Missing author profile')
            for row in result.get('cited_by', {}).get('table', []):
                for key, values in row.items():
                    if key in ('citations', 'h_index', 'i10_index'):
                        metrics[key] = values.get('all')
            if any(not isinstance(metrics.get(k), int) for k in ('citations','h_index','i10_index')):
                raise ValueError('Missing citation metrics')
        batch = result.get('articles')
        if not isinstance(batch, list):
            raise ValueError('Missing article list')
        fresh = 0
        for item in batch:
            identity = item.get('citation_id') or item.get('link') or item.get('title')
            if not identity or identity in seen:
                continue
            seen.add(identity)
            fresh += 1
            cited = item.get('cited_by') or {}
            articles.append(dict(title=item.get('title',''), authors=item.get('authors',''),
                publication=item.get('publication',''), year=item.get('year',''),
                link=item.get('link',''), citations=cited.get('value',0),
                citations_link=cited.get('link','')))
        if not result.get('serpapi_pagination', {}).get('next'):
            break
        if not fresh:
            raise ValueError('Pagination repeated articles')
    else:
        raise ValueError('Pagination limit reached; refusing an incomplete update')
    if not articles:
        raise ValueError('Empty result; previous data retained')
    return dict(updated_at=datetime.now(timezone.utc).isoformat(), author_id=AUTHOR,
                metrics=metrics, articles=articles)


def main():
    key = os.environ.get('SERPAPI_KEY')
    if not key:
        print('Scholar sync is inactive until SERPAPI_KEY is configured.')
        return 0
    def fetch(start):
        params = dict(engine='google_scholar_author', author_id=AUTHOR, hl='en',
                      sort='pubdate', num=100, start=start, api_key=key)
        with urlopen('https://serpapi.com/search.json?' + urlencode(params), timeout=90) as response:
            return json.load(response)
    try:
        data = collect(fetch)
        temporary = TARGET.with_suffix('.tmp')
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        temporary.replace(TARGET)
        print(f'Updated {len(data["articles"])} publications.')
        return 0
    except Exception:
        # Exceptions from HTTP clients might contain the request URL and secret.
        print('Scholar update failed. Previous data retained. Check API quota and account settings.', file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
