import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';

export const dynamic = 'force-dynamic';

/**
 * GET /api/rss/feeds
 * Fetch user's RSS feeds
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

        const { data: feeds, error } = await supabase
            .from('rss_feeds')
            .select('*')
            .eq('user_id', user.id)
            .order('created_at', { ascending: false });

        if (error) {
            console.error('[RSS Feeds] Error fetching feeds:', error);
            return NextResponse.json(
                { error: 'Failed to fetch feeds' },
                { status: 500 }
            );
        }

        return NextResponse.json({
            success: true,
            feeds: feeds || [],
        });

    } catch (error) {
        console.error('[RSS Feeds] Error:', error);
        return NextResponse.json(
            { error: 'Failed to fetch feeds' },
            { status: 500 }
        );
    }
}

/**
 * Normalize URL - add https:// if missing, clean up trailing slashes
 */
function normalizeUrl(input: string): string {
    let url = input.trim().toLowerCase();

    // Remove trailing slashes
    url = url.replace(/\/+$/, '');

    // Add https:// if no protocol
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
        url = 'https://' + url;
    }

    return url;
}

/**
 * Common RSS feed paths to try
 */
const RSS_PATHS = [
    '/rss',
    '/feed',
    '/rss.xml',
    '/feed.xml',
    '/atom.xml',
    '/feeds/posts/default',
    '/blog/feed',
    '/blog/rss',
    '/?feed=rss2',
    '/index.xml',
];

/**
 * Try to fetch and validate an RSS feed URL
 */
async function tryFetchFeed(url: string): Promise<boolean> {
    try {
        const response = await fetch(url, {
            headers: {
                'User-Agent': 'Mozilla/5.0 (compatible; RSSFeedChecker/1.0)',
                'Accept': 'application/rss+xml, application/xml, text/xml, */*',
            },
            signal: AbortSignal.timeout(5000), // 5 second timeout
        });

        if (!response.ok) return false;

        const text = await response.text();
        // Check if it looks like RSS/Atom
        return text.includes('<rss') || text.includes('<feed') || text.includes('<channel');
    } catch {
        return false;
    }
}

/**
 * Discover RSS feed URL for a domain
 */
async function discoverRssFeed(baseUrl: string): Promise<string | null> {
    // First, try the exact URL provided
    if (await tryFetchFeed(baseUrl)) {
        return baseUrl;
    }

    // Try common RSS paths
    for (const path of RSS_PATHS) {
        const testUrl = baseUrl + path;
        console.log(`[RSS Discovery] Trying: ${testUrl}`);

        if (await tryFetchFeed(testUrl)) {
            console.log(`[RSS Discovery] Found: ${testUrl}`);
            return testUrl;
        }
    }

    return null;
}

/**
 * POST /api/rss/feeds
 * Add a new RSS feed with smart discovery
 * 
 * Body:
 * - name: Feed name (e.g., "TechCrunch")
 * - url: Website URL or RSS feed URL (can be partial like "jornaldenegocios.pt")
 */
export async function POST(request: NextRequest) {
    try {
        const supabase = await createClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json(
                { error: 'Unauthorized' },
                { status: 401 }
            );
        }

        const body = await request.json();
        let { name, url } = body;

        if (!name || !url) {
            return NextResponse.json(
                { error: 'Nome e URL são obrigatórios' },
                { status: 400 }
            );
        }

        // Normalize the URL
        const normalizedUrl = normalizeUrl(url);
        console.log(`[RSS Feeds] Input: "${url}" -> Normalized: "${normalizedUrl}"`);

        // Try to discover the RSS feed
        const discoveredUrl = await discoverRssFeed(normalizedUrl);

        if (!discoveredUrl) {
            return NextResponse.json(
                { error: `Não foi possível encontrar um feed RSS em ${normalizedUrl}. Tente adicionar o caminho do RSS (ex: /rss, /feed)` },
                { status: 400 }
            );
        }

        console.log(`[RSS Feeds] Discovered RSS URL: ${discoveredUrl}`);

        // Check if feed already exists
        const { data: existing } = await supabase
            .from('rss_feeds')
            .select('id')
            .eq('user_id', user.id)
            .eq('url', discoveredUrl)
            .single();

        if (existing) {
            return NextResponse.json(
                { error: 'Este feed já foi adicionado' },
                { status: 400 }
            );
        }

        // Insert new feed with discovered URL
        const { data: feed, error } = await supabase
            .from('rss_feeds')
            .insert({
                user_id: user.id,
                name: name.trim(),
                url: discoveredUrl,
                is_active: true,
            })
            .select()
            .single();

        if (error) {
            console.error('[RSS Feeds] Error adding feed:', error);
            return NextResponse.json(
                { error: 'Falha ao adicionar feed' },
                { status: 500 }
            );
        }

        return NextResponse.json({
            success: true,
            feed,
            message: `Feed descoberto: ${discoveredUrl}`,
            discoveredUrl,
        });

    } catch (error) {
        console.error('[RSS Feeds] Error:', error);
        return NextResponse.json(
            { error: 'Failed to add feed' },
            { status: 500 }
        );
    }
}

/**
 * DELETE /api/rss/feeds
 * Remove an RSS feed
 * 
 * Query params:
 * - id: Feed ID to delete
 */
export async function DELETE(request: NextRequest) {
    try {
        const supabase = await createClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json(
                { error: 'Unauthorized' },
                { status: 401 }
            );
        }

        const { searchParams } = new URL(request.url);
        const feedId = searchParams.get('id');

        if (!feedId) {
            return NextResponse.json(
                { error: 'ID do feed é obrigatório' },
                { status: 400 }
            );
        }

        const { error } = await supabase
            .from('rss_feeds')
            .delete()
            .eq('id', feedId)
            .eq('user_id', user.id);

        if (error) {
            console.error('[RSS Feeds] Error deleting feed:', error);
            return NextResponse.json(
                { error: 'Falha ao remover feed' },
                { status: 500 }
            );
        }

        return NextResponse.json({
            success: true,
            message: 'Feed removido com sucesso',
        });

    } catch (error) {
        console.error('[RSS Feeds] Error:', error);
        return NextResponse.json(
            { error: 'Failed to delete feed' },
            { status: 500 }
        );
    }
}
