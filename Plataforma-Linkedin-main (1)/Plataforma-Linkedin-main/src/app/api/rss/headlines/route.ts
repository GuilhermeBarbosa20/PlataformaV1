import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';

export const dynamic = 'force-dynamic';

interface RSSItem {
    title: string;
    description: string;
    link: string;
    pubDate: string;
    feedName: string;
    feedId: string;
}

/**
 * Simple RSS parser - extracts items from RSS/Atom XML
 */
function parseRSSItems(xml: string, feedName: string, feedId: string, limit: number = 10): RSSItem[] {
    const items: RSSItem[] = [];

    try {
        // Try RSS 2.0 format first
        const itemRegex = /<item>([\s\S]*?)<\/item>/gi;
        let match;

        while ((match = itemRegex.exec(xml)) !== null && items.length < limit) {
            const itemContent = match[1];

            const title = extractTag(itemContent, 'title');
            const description = extractTag(itemContent, 'description') || extractTag(itemContent, 'content:encoded');
            const link = extractTag(itemContent, 'link') || extractGuidLink(itemContent);
            const pubDate = extractTag(itemContent, 'pubDate') || extractTag(itemContent, 'dc:date');

            if (title) {
                items.push({
                    title: cleanHTML(title),
                    description: cleanHTML(description || '').slice(0, 300),
                    link: link || '',
                    pubDate: pubDate || new Date().toISOString(),
                    feedName,
                    feedId,
                });
            }
        }

        // If no RSS items found, try Atom format
        if (items.length === 0) {
            const entryRegex = /<entry>([\s\S]*?)<\/entry>/gi;

            while ((match = entryRegex.exec(xml)) !== null && items.length < limit) {
                const entryContent = match[1];

                const title = extractTag(entryContent, 'title');
                const summary = extractTag(entryContent, 'summary') || extractTag(entryContent, 'content');
                const link = extractAtomLink(entryContent);
                const updated = extractTag(entryContent, 'updated') || extractTag(entryContent, 'published');

                if (title) {
                    items.push({
                        title: cleanHTML(title),
                        description: cleanHTML(summary || '').slice(0, 300),
                        link: link || '',
                        pubDate: updated || new Date().toISOString(),
                        feedName,
                        feedId,
                    });
                }
            }
        }
    } catch (error) {
        console.error('[RSS Parser] Error parsing feed:', error);
    }

    return items;
}

function extractTag(content: string, tag: string): string | null {
    // Try CDATA first
    const cdataRegex = new RegExp(`<${tag}[^>]*><!\\[CDATA\\[([\\s\\S]*?)\\]\\]><\\/${tag}>`, 'i');
    const cdataMatch = content.match(cdataRegex);
    if (cdataMatch) return cdataMatch[1].trim();

    // Try regular tag
    const regex = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)<\\/${tag}>`, 'i');
    const match = content.match(regex);
    return match ? match[1].trim() : null;
}

function extractGuidLink(content: string): string | null {
    const match = content.match(/<guid[^>]*>(https?:\/\/[^<]+)<\/guid>/i);
    return match ? match[1] : null;
}

function extractAtomLink(content: string): string | null {
    // Look for <link href="..." /> or <link>...</link>
    const hrefMatch = content.match(/<link[^>]+href=["']([^"']+)["'][^>]*\/?>/i);
    if (hrefMatch) return hrefMatch[1];

    const tagMatch = content.match(/<link>([^<]+)<\/link>/i);
    return tagMatch ? tagMatch[1] : null;
}

/**
 * Detect encoding from XML declaration or Content-Type
 */
function detectEncoding(buffer: ArrayBuffer, contentType?: string | null): string {
    // First, try to read the XML declaration with ASCII
    const asciiDecoder = new TextDecoder('ascii', { fatal: false });
    const start = asciiDecoder.decode(buffer.slice(0, 200));

    // Check XML declaration for encoding
    const xmlMatch = start.match(/<\?xml[^>]+encoding=["']([^"']+)["']/i);
    if (xmlMatch) {
        const enc = xmlMatch[1].toLowerCase();
        // Map common encodings
        if (enc === 'iso-8859-1' || enc === 'latin1' || enc === 'latin-1') {
            return 'iso-8859-1';
        }
        if (enc === 'windows-1252' || enc === 'cp1252') {
            return 'windows-1252';
        }
        return enc;
    }

    // Check Content-Type header
    if (contentType) {
        const charsetMatch = contentType.match(/charset=([^\s;]+)/i);
        if (charsetMatch) {
            return charsetMatch[1].toLowerCase();
        }
    }

    return 'utf-8';
}

/**
 * Decode buffer with proper encoding
 */
function decodeWithEncoding(buffer: ArrayBuffer, encoding: string): string {
    try {
        const decoder = new TextDecoder(encoding, { fatal: false });
        return decoder.decode(buffer);
    } catch (error) {
        // Fallback to UTF-8
        console.warn(`[RSS] Failed to decode with ${encoding}, falling back to UTF-8`);
        const decoder = new TextDecoder('utf-8', { fatal: false });
        return decoder.decode(buffer);
    }
}

function cleanHTML(text: string): string {
    return text
        .replace(/<[^>]+>/g, '') // Remove HTML tags
        .replace(/&nbsp;/g, ' ')
        .replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'")
        .replace(/&apos;/g, "'")
        .replace(/&#(\d+);/g, (_, code) => String.fromCharCode(parseInt(code, 10)))
        .replace(/&#x([0-9a-f]+);/gi, (_, code) => String.fromCharCode(parseInt(code, 16)))
        .replace(/&([a-z]+);/gi, (match, entity) => {
            // Common HTML entities
            const entities: Record<string, string> = {
                'ntilde': 'ñ', 'Ntilde': 'Ñ',
                'aacute': 'á', 'Aacute': 'Á',
                'eacute': 'é', 'Eacute': 'É',
                'iacute': 'í', 'Iacute': 'Í',
                'oacute': 'ó', 'Oacute': 'Ó',
                'uacute': 'ú', 'Uacute': 'Ú',
                'agrave': 'à', 'Agrave': 'À',
                'egrave': 'è', 'Egrave': 'È',
                'igrave': 'ì', 'Igrave': 'Ì',
                'ograve': 'ò', 'Ograve': 'Ò',
                'ugrave': 'ù', 'Ugrave': 'Ù',
                'atilde': 'ã', 'Atilde': 'Ã',
                'otilde': 'õ', 'Otilde': 'Õ',
                'acirc': 'â', 'Acirc': 'Â',
                'ecirc': 'ê', 'Ecirc': 'Ê',
                'icirc': 'î', 'Icirc': 'Î',
                'ocirc': 'ô', 'Ocirc': 'Ô',
                'ucirc': 'û', 'Ucirc': 'Û',
                'auml': 'ä', 'Auml': 'Ä',
                'euml': 'ë', 'Euml': 'Ë',
                'iuml': 'ï', 'Iuml': 'Ï',
                'ouml': 'ö', 'Ouml': 'Ö',
                'uuml': 'ü', 'Uuml': 'Ü',
                'ccedil': 'ç', 'Ccedil': 'Ç',
                'euro': '€', 'pound': '£', 'yen': '¥',
                'copy': '©', 'reg': '®', 'trade': '™',
                'mdash': '—', 'ndash': '–', 'hellip': '…',
                'lsquo': '\u2018', 'rsquo': '\u2019', 'ldquo': '\u201c', 'rdquo': '\u201d',
            };
            return entities[entity] || match;
        })
        .replace(/\s+/g, ' ')
        .trim();
}

/**
 * GET /api/rss/headlines
 * Fetch headlines from all active RSS feeds
 */
export async function GET(request: NextRequest) {
    try {
        const supabase = await createClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json(
                { error: 'Unauthorized' },
                { status: 401 }
            );
        }

        // Fetch active feeds
        const { data: feeds, error: feedsError } = await supabase
            .from('rss_feeds')
            .select('*')
            .eq('user_id', user.id)
            .eq('is_active', true);

        if (feedsError) {
            console.error('[RSS Headlines] Error fetching feeds:', feedsError);
            return NextResponse.json(
                { error: 'Failed to fetch feeds' },
                { status: 500 }
            );
        }

        if (!feeds || feeds.length === 0) {
            return NextResponse.json({
                success: true,
                headlines: [],
                message: 'Nenhum feed RSS ativo',
            });
        }

        // Fetch headlines from each feed
        const allHeadlines: RSSItem[] = [];
        const feedErrors: string[] = [];

        await Promise.all(
            feeds.map(async (feed) => {
                try {
                    console.log(`[RSS Headlines] Fetching: ${feed.name} (${feed.url})`);

                    const response = await fetch(feed.url, {
                        headers: {
                            'User-Agent': 'Mozilla/5.0 (compatible; LinkedInPostGenerator/1.0)',
                            'Accept': 'application/rss+xml, application/xml, text/xml, */*',
                        },
                        next: { revalidate: 0 },
                    });

                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}`);
                    }

                    // Get raw buffer for encoding detection
                    const buffer = await response.arrayBuffer();
                    const contentType = response.headers.get('content-type');
                    const encoding = detectEncoding(buffer, contentType);
                    const xml = decodeWithEncoding(buffer, encoding);

                    console.log(`[RSS Headlines] Encoding detected: ${encoding} for ${feed.name}`);
                    const items = parseRSSItems(xml, feed.name, feed.id, 10);

                    console.log(`[RSS Headlines] Found ${items.length} items from ${feed.name}`);
                    allHeadlines.push(...items);

                    // Update last_fetched_at
                    await supabase
                        .from('rss_feeds')
                        .update({ last_fetched_at: new Date().toISOString() })
                        .eq('id', feed.id);

                } catch (error: any) {
                    console.error(`[RSS Headlines] Error fetching ${feed.name}:`, error.message);
                    feedErrors.push(`${feed.name}: ${error.message}`);
                }
            })
        );

        // Sort by date (most recent first)
        allHeadlines.sort((a, b) => {
            try {
                return new Date(b.pubDate).getTime() - new Date(a.pubDate).getTime();
            } catch {
                return 0;
            }
        });

        return NextResponse.json({
            success: true,
            headlines: allHeadlines,
            feedCount: feeds.length,
            errors: feedErrors.length > 0 ? feedErrors : undefined,
        });

    } catch (error) {
        console.error('[RSS Headlines] Error:', error);
        return NextResponse.json(
            { error: 'Failed to fetch headlines' },
            { status: 500 }
        );
    }
}
