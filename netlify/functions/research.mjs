// Netlify Function: Client research - fetches company website info

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
    const { domain } = JSON.parse(event.body);

    if (!domain) {
      return { statusCode: 200, headers, body: JSON.stringify({ title: '', description: '', text: '' }) };
    }

    const fetchHeaders = {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      'Accept-Language': 'pl-PL,pl;q=0.9',
      'Accept': 'text/html',
    };

    const resp = await fetch(`https://${domain}`, {
      headers: fetchHeaders,
      signal: AbortSignal.timeout(8000),
    });

    const html = await resp.text();

    const titleMatch = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
    const title = titleMatch ? stripTags(titleMatch[1]).trim() : '';

    const descMatch = html.match(/<meta\s+[^>]*name=["']description["'][^>]*content=["']([\s\S]*?)["'][^>]*>/i)
      || html.match(/<meta\s+[^>]*content=["']([\s\S]*?)["'][^>]*name=["']description["'][^>]*>/i);
    const description = descMatch ? stripTags(descMatch[1]).trim() : '';

    let bodyHtml = html
      .replace(/<script[\s\S]*?<\/script>/gi, '')
      .replace(/<style[\s\S]*?<\/style>/gi, '')
      .replace(/<nav[\s\S]*?<\/nav>/gi, '')
      .replace(/<footer[\s\S]*?<\/footer>/gi, '')
      .replace(/<header[\s\S]*?<\/header>/gi, '');
    const text = stripTags(bodyHtml).replace(/\s+/g, ' ').trim().substring(0, 2000);

    const socialPatterns = [
      { name: 'Facebook', pattern: /href="(https?:\/\/(?:www\.)?facebook\.com\/[^"]+)"/i },
      { name: 'LinkedIn', pattern: /href="(https?:\/\/(?:www\.)?linkedin\.com\/[^"]+)"/i },
      { name: 'Instagram', pattern: /href="(https?:\/\/(?:www\.)?instagram\.com\/[^"]+)"/i },
      { name: 'Twitter/X', pattern: /href="(https?:\/\/(?:www\.)?(?:twitter|x)\.com\/[^"]+)"/i },
      { name: 'YouTube', pattern: /href="(https?:\/\/(?:www\.)?youtube\.com\/[^"]+)"/i },
      { name: 'TikTok', pattern: /href="(https?:\/\/(?:www\.)?tiktok\.com\/[^"]+)"/i },
    ];

    const socialMedia = [];
    for (const { name, pattern } of socialPatterns) {
      const match = html.match(pattern);
      if (match) {
        socialMedia.push({ name, url: match[1] });
      }
    }

    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({ title, description, text, socialMedia }),
    };
  } catch (err) {
    return {
      statusCode: 200,
      headers,
      body: JSON.stringify({ title: '', description: '', text: '', error: err.message }),
    };
  }
}

function stripTags(html) {
  return html.replace(/<[^>]*>/g, '').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&nbsp;/g, ' ');
}
