// Netlify Function: CORS proxy for scraping tender websites

export async function handler(event) {
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Content-Type': 'application/json',
  };

  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 200, headers, body: '' };
  }

  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, headers, body: JSON.stringify({ error: 'Method not allowed' }) };
  }

  try {
    const { url, keyword } = JSON.parse(event.body);

    if (!url) {
      return { statusCode: 400, headers, body: JSON.stringify({ error: 'URL is required' }) };
    }

    // Build search URL based on known sites
    let searchUrl = url;
    if (keyword) {
      const encoded = encodeURIComponent(keyword);
      if (url.includes('nowymarketing.pl')) searchUrl = `https://nowymarketing.pl/?s=${encoded}`;
      else if (url.includes('wirtualnemedia.pl')) searchUrl = `https://www.wirtualnemedia.pl/wyniki?zapytanie=${encoded}`;
      else if (url.includes('marketingprzykawie.pl')) searchUrl = `https://marketingprzykawie.pl/?s=${encoded}`;
      else if (url.includes('press.pl')) searchUrl = `https://www.press.pl/szukaj?q=${encoded}`;
      else if (url.includes('mmponline.pl')) searchUrl = `https://mmponline.pl/szukaj?q=${encoded}`;
      else if (url.includes('platformazakupowa.pl') && !url.includes('pzp24')) searchUrl = `https://platformazakupowa.pl/all?search=${encoded}`;
      else if (url.includes('oneplace.marketplanet.pl')) searchUrl = `https://oneplace.marketplanet.pl/zapytania-ofertowe-przetargi?query=${encoded}`;
    }

    const resp = await fetch(searchUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept': 'text/html,application/xhtml+xml',
      },
      signal: AbortSignal.timeout(8000),
    });

    const html = await resp.text();
    const results = parseResults(html, searchUrl, keyword);

    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({ results, searchUrl }),
    };
  } catch (err) {
    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({ results: [], error: err.message }),
    };
  }
}

function parseResults(html, sourceUrl, keyword) {
  const results = [];
  const seen = new Set();

  let sourceName = '';
  try {
    sourceName = new URL(sourceUrl).hostname.replace('www.', '');
  } catch { sourceName = sourceUrl; }

  const headingLinkPattern = /<h[1-4][^>]*>[\s\S]*?<a\s+[^>]*href="([^"]*)"[^>]*>([\s\S]*?)<\/a>[\s\S]*?<\/h[1-4]>/gi;
  let match;
  while ((match = headingLinkPattern.exec(html)) !== null) {
    const link = match[1];
    const title = stripTags(match[2]).trim();
    addResult(results, seen, title, link, sourceName, sourceUrl, keyword, '');
  }

  const articlePattern = /<article[^>]*>([\s\S]*?)<\/article>/gi;
  while ((match = articlePattern.exec(html)) !== null) {
    const block = match[1];
    const linkMatch = block.match(/<a\s+[^>]*href="([^"]*)"[^>]*>([\s\S]*?)<\/a>/i);
    if (linkMatch) {
      const title = stripTags(linkMatch[2]).trim();
      const link = linkMatch[1];
      const snippetMatch = block.match(/<p[^>]*>([\s\S]*?)<\/p>/i);
      const snippet = snippetMatch ? stripTags(snippetMatch[1]).trim().substring(0, 300) : '';
      addResult(results, seen, title, link, sourceName, sourceUrl, keyword, snippet);
    }
  }

  const divPattern = /<div\s+[^>]*class="[^"]*(?:result|item|post|card|entry|news|tender)[^"]*"[^>]*>([\s\S]*?)<\/div>\s*(?:<\/div>|\s*<div)/gi;
  while ((match = divPattern.exec(html)) !== null) {
    const block = match[1];
    const linkMatch = block.match(/<a\s+[^>]*href="([^"]*)"[^>]*>([\s\S]*?)<\/a>/i);
    if (linkMatch) {
      const title = stripTags(linkMatch[2]).trim();
      const link = linkMatch[1];
      const snippetMatch = block.match(/<p[^>]*>([\s\S]*?)<\/p>/i);
      const snippet = snippetMatch ? stripTags(snippetMatch[1]).trim().substring(0, 300) : '';
      addResult(results, seen, title, link, sourceName, sourceUrl, keyword, snippet);
    }
  }

  const simpleHeadingPattern = /<h[23][^>]*>\s*<a\s+[^>]*href="([^"]*)"[^>]*>([\s\S]*?)<\/a>\s*<\/h[23]>/gi;
  while ((match = simpleHeadingPattern.exec(html)) !== null) {
    const link = match[1];
    const title = stripTags(match[2]).trim();
    addResult(results, seen, title, link, sourceName, sourceUrl, keyword, '');
  }

  return results.slice(0, 30);
}

function addResult(results, seen, title, link, sourceName, sourceUrl, keyword, snippet) {
  if (!title || title.length < 10) return;
  const key = title.toLowerCase();
  if (seen.has(key)) return;

  if (link && !link.startsWith('http')) {
    try {
      link = new URL(link, sourceUrl).href;
    } catch { /* keep relative */ }
  }

  if (keyword) {
    const text = (title + ' ' + snippet).toLowerCase();
    const words = keyword.toLowerCase().split(/\s+/);
    if (!words.some(w => text.includes(w))) return;
  }

  seen.add(key);
  results.push({
    title: title.substring(0, 200),
    url: link || sourceUrl,
    source_name: sourceName,
    source_url: sourceUrl,
    snippet: snippet || '',
    keyword: keyword || '',
  });
}

function stripTags(html) {
  return html.replace(/<[^>]*>/g, '').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ');
}
