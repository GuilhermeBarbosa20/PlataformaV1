import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';

export const dynamic = 'force-dynamic';

const APIFY_TOKEN = process.env.APIFY_API_TOKEN;
const APIFY_ACTOR_ID = 'LQQIXN9Othf8f7R5n'; // LinkedIn Posts Scraper actor

/**
 * POST /api/apify/scrape-posts
 * Scrapes LinkedIn posts from a user's profile using Apify
 * This is called on first login to analyze the user's content history
 */
export async function POST(req: NextRequest) {
  console.log('\n========================================');
  console.log('[APIFY SCRAPER] POST request received');
  console.log('========================================');

  try {
    const supabase = await createClient();
    const { data: { user }, error: authError } = await supabase.auth.getUser();

    console.log('[APIFY SCRAPER] Auth check - User ID:', user?.id);
    console.log('[APIFY SCRAPER] Auth check - Error:', authError?.message || 'none');

    if (authError || !user) {
      console.log('[APIFY SCRAPER] ❌ Unauthorized - no user');
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    // Get request body
    let body: any = {};
    try {
      body = await req.json();
      console.log('[APIFY SCRAPER] Request body:', JSON.stringify(body, null, 2));
    } catch (e) {
      console.log('[APIFY SCRAPER] No JSON body provided');
    }

    // Check if user has already been analyzed
    const { data: userAgent, error: agentError } = await supabase
      .from('user_agents')
      .select('*')
      .eq('user_id', user.id)
      .single();

    console.log('[APIFY SCRAPER] User agent fetch error:', agentError?.message || 'none');
    console.log('[APIFY SCRAPER] User agent data:', JSON.stringify(userAgent, null, 2));

    // If already analyzed, don't run again
    if (userAgent?.has_been_analyzed) {
      console.log('[APIFY SCRAPER] ⚠️ Already analyzed, returning early');
      return NextResponse.json({
        success: false,
        message: '⚠️ Seus posts já foram analisados anteriormente. Esta operação só pode ser executada uma vez.',
        already_analyzed: true,
        analyzed_at: userAgent.themes_suggested_at,
        posts_count: userAgent.scraped_posts_count,
      });
    }

    // Get profile URL from multiple sources
    console.log('\n[APIFY SCRAPER] --- Finding Profile URL ---');
    
    // Priority 1: From request body
    let profileUrl = body.profile_url;
    console.log('[APIFY SCRAPER] From request body:', profileUrl || 'NOT PROVIDED');
    
    // Priority 2: From user_agents table
    if (!profileUrl) {
      profileUrl = userAgent?.linkedin_profile_url;
      console.log('[APIFY SCRAPER] From user_agents:', profileUrl || 'NOT FOUND');
    }

    // Priority 3: From user_linkedin_auth table
    if (!profileUrl) {
      const { data: linkedinAuth, error: linkedinError } = await supabase
        .from('user_linkedin_auth')
        .select('linkedin_profile_url')
        .eq('user_id', user.id)
        .single();

      console.log('[APIFY SCRAPER] user_linkedin_auth error:', linkedinError?.message || 'none');
      profileUrl = linkedinAuth?.linkedin_profile_url;
      console.log('[APIFY SCRAPER] From user_linkedin_auth:', profileUrl || 'NOT FOUND');
    }

    // Priority 4: From user metadata
    if (!profileUrl) {
      const metadata = user.user_metadata || {};
      console.log('[APIFY SCRAPER] User metadata:', JSON.stringify(metadata, null, 2));
      
      const vanityName = metadata.user_name || metadata.preferred_username || metadata.nickname;
      console.log('[APIFY SCRAPER] Vanity name from metadata:', vanityName || 'NOT FOUND');
      
      if (vanityName) {
        profileUrl = `https://www.linkedin.com/in/${vanityName}/`;
        console.log('[APIFY SCRAPER] Built URL from vanity:', profileUrl);
      }
    }

    if (!profileUrl) {
      console.log('[APIFY SCRAPER] ❌ No profile URL found from any source!');
      return NextResponse.json(
        { 
          error: 'LinkedIn profile URL not found. Please ensure your profile is properly connected.',
          hint: 'Try re-authenticating with LinkedIn.',
          debug: {
            has_user_agent: !!userAgent,
            user_metadata: user.user_metadata,
          }
        },
        { status: 400 }
      );
    }

    console.log('[APIFY SCRAPER] ✅ Final profile URL:', profileUrl);

    // Check Apify token
    console.log('\n[APIFY SCRAPER] --- Apify Configuration ---');
    console.log('[APIFY SCRAPER] APIFY_TOKEN exists:', !!APIFY_TOKEN);
    console.log('[APIFY SCRAPER] APIFY_TOKEN (first 10 chars):', APIFY_TOKEN?.substring(0, 10) || 'NOT SET');
    console.log('[APIFY SCRAPER] Actor ID:', APIFY_ACTOR_ID);

    if (!APIFY_TOKEN) {
      console.log('[APIFY SCRAPER] ❌ Apify API token not configured!');
      return NextResponse.json(
        { error: 'Apify API token not configured' },
        { status: 500 }
      );
    }

    // Calculate date 12 months ago for filtering
    const twelveMonthsAgo = new Date();
    twelveMonthsAgo.setMonth(twelveMonthsAgo.getMonth() - 12);
    console.log('[APIFY SCRAPER] Filtering posts since:', twelveMonthsAgo.toISOString());

    // Prepare Apify input
    const apifyInput = {
      username: profileUrl,
      limit: 100,
      page_number: 1,
    };

    console.log('\n[APIFY SCRAPER] --- Starting Apify Run ---');
    console.log('[APIFY SCRAPER] Input:', JSON.stringify(apifyInput, null, 2));
    
    const apifyUrl = `https://api.apify.com/v2/acts/${APIFY_ACTOR_ID}/runs?token=${APIFY_TOKEN}`;
    console.log('[APIFY SCRAPER] API URL:', apifyUrl.replace(APIFY_TOKEN, 'TOKEN_HIDDEN'));

    const apifyResponse = await fetch(apifyUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(apifyInput),
    });

    console.log('[APIFY SCRAPER] Response status:', apifyResponse.status);
    console.log('[APIFY SCRAPER] Response statusText:', apifyResponse.statusText);

    if (!apifyResponse.ok) {
      const errorText = await apifyResponse.text();
      console.log('[APIFY SCRAPER] ❌ Apify API error response:', errorText);
      return NextResponse.json(
        { error: 'Failed to start Apify scraping', details: errorText },
        { status: apifyResponse.status }
      );
    }

    const runData = await apifyResponse.json();
    console.log('[APIFY SCRAPER] Run data:', JSON.stringify(runData, null, 2));
    
    const runId = runData.data?.id;
    console.log('[APIFY SCRAPER] Run ID:', runId);

    if (!runId) {
      console.log('[APIFY SCRAPER] ❌ No run ID in response');
      return NextResponse.json(
        { error: 'Failed to get Apify run ID', response: runData },
        { status: 500 }
      );
    }

    console.log('[APIFY SCRAPER] ⏳ Run started, polling for completion...');

    // Wait for the run to complete (polling with timeout)
    const maxWaitTime = 120000; // 2 minutes max
    const pollInterval = 5000; // Check every 5 seconds
    const startTime = Date.now();
    let runStatus = 'RUNNING';
    let datasetId: string | null = null;
    let pollCount = 0;

    while (runStatus === 'RUNNING' || runStatus === 'READY') {
      if (Date.now() - startTime > maxWaitTime) {
        console.log('[APIFY SCRAPER] ⚠️ Timeout reached after', maxWaitTime, 'ms');
        break;
      }

      await new Promise(resolve => setTimeout(resolve, pollInterval));
      pollCount++;

      const statusUrl = `https://api.apify.com/v2/acts/${APIFY_ACTOR_ID}/runs/${runId}?token=${APIFY_TOKEN}`;
      console.log(`[APIFY SCRAPER] Poll #${pollCount} - Checking status...`);

      const statusResponse = await fetch(statusUrl);
      console.log(`[APIFY SCRAPER] Poll #${pollCount} - Response status:`, statusResponse.status);
      
      if (statusResponse.ok) {
        const statusData = await statusResponse.json();
        runStatus = statusData.data?.status;
        datasetId = statusData.data?.defaultDatasetId;
        console.log(`[APIFY SCRAPER] Poll #${pollCount} - Run status: ${runStatus}`);
        console.log(`[APIFY SCRAPER] Poll #${pollCount} - Dataset ID: ${datasetId}`);
      } else {
        console.log(`[APIFY SCRAPER] Poll #${pollCount} - Failed to get status`);
      }
    }

    console.log('\n[APIFY SCRAPER] --- Run Complete ---');
    console.log('[APIFY SCRAPER] Final status:', runStatus);
    console.log('[APIFY SCRAPER] Dataset ID:', datasetId);
    console.log('[APIFY SCRAPER] Total poll attempts:', pollCount);

    if (runStatus !== 'SUCCEEDED' || !datasetId) {
      console.log('[APIFY SCRAPER] ⚠️ Run did not succeed, storing partial info');
      
      await supabase
        .from('user_agents')
        .upsert({
          user_id: user.id,
          linkedin_profile_url: profileUrl,
          scraped_posts_data: { apify_run_id: runId, status: runStatus },
          updated_at: new Date().toISOString(),
        }, {
          onConflict: 'user_id',
        });

      return NextResponse.json({
        success: false,
        message: '⏳ Scraping em andamento. Os resultados serão processados em breve.',
        run_id: runId,
        status: runStatus,
        dataset_id: datasetId,
      });
    }

    // Fetch the scraped data from the dataset
    console.log('\n[APIFY SCRAPER] --- Fetching Dataset ---');
    const datasetUrl = `https://api.apify.com/v2/datasets/${datasetId}/items?token=${APIFY_TOKEN}`;
    console.log('[APIFY SCRAPER] Dataset URL:', datasetUrl.replace(APIFY_TOKEN, 'TOKEN_HIDDEN'));

    const datasetResponse = await fetch(datasetUrl);
    console.log('[APIFY SCRAPER] Dataset response status:', datasetResponse.status);

    if (!datasetResponse.ok) {
      const errorText = await datasetResponse.text();
      console.log('[APIFY SCRAPER] ❌ Dataset fetch error:', errorText);
      return NextResponse.json(
        { error: 'Failed to fetch scraped data from Apify', details: errorText },
        { status: 500 }
      );
    }

    const scrapedPosts = await datasetResponse.json();
    console.log('[APIFY SCRAPER] Raw posts count:', Array.isArray(scrapedPosts) ? scrapedPosts.length : 'NOT AN ARRAY');
    console.log('[APIFY SCRAPER] Raw posts type:', typeof scrapedPosts);
    
    if (Array.isArray(scrapedPosts) && scrapedPosts.length > 0) {
      console.log('[APIFY SCRAPER] First post sample:', JSON.stringify(scrapedPosts[0], null, 2));
    }
    
    // Filter posts from last 12 months
    const recentPosts = filterPostsByDate(scrapedPosts, twelveMonthsAgo);
    console.log('[APIFY SCRAPER] Filtered posts count (last 12 months):', recentPosts.length);

    // Store the scraped posts in user_agents
    console.log('\n[APIFY SCRAPER] --- Storing in Database ---');
    const upsertData = {
      user_id: user.id,
      linkedin_profile_url: profileUrl,
      scraped_posts_count: recentPosts.length,
      scraped_posts_data: recentPosts,
      last_scrape_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    console.log('[APIFY SCRAPER] Upserting data (without posts):', {
      ...upsertData,
      scraped_posts_data: `[${recentPosts.length} posts]`,
    });

    const { error: updateError } = await supabase
      .from('user_agents')
      .upsert(upsertData, {
        onConflict: 'user_id',
      });

    if (updateError) {
      console.log('[APIFY SCRAPER] ❌ Database update error:', updateError);
    } else {
      console.log('[APIFY SCRAPER] ✅ Data stored successfully');
    }

    console.log('\n========================================');
    console.log('[APIFY SCRAPER] ✅ COMPLETE');
    console.log('========================================\n');

    return NextResponse.json({
      success: true,
      message: `✅ ${recentPosts.length} posts coletados dos últimos 12 meses!`,
      posts_count: recentPosts.length,
      profile_url: profileUrl,
      run_id: runId,
      dataset_id: datasetId,
    });

  } catch (error: any) {
    console.log('[APIFY SCRAPER] ❌ FATAL ERROR:', error);
    console.log('[APIFY SCRAPER] Error stack:', error.stack);
    return NextResponse.json(
      { error: error.message || 'Internal server error' },
      { status: 500 }
    );
  }
}

/**
 * GET /api/apify/scrape-posts
 * Check the status of scraped posts or get existing data
 */
export async function GET(req: NextRequest) {
  console.log('[APIFY SCRAPER] GET request received');

  try {
    const supabase = await createClient();
    const { data: { user }, error: authError } = await supabase.auth.getUser();

    if (authError || !user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const { data: userAgent } = await supabase
      .from('user_agents')
      .select('*')
      .eq('user_id', user.id)
      .single();

    if (!userAgent) {
      return NextResponse.json({
        has_been_analyzed: false,
        posts_count: 0,
        message: 'Nenhum dado de posts encontrado',
      });
    }

    return NextResponse.json({
      has_been_analyzed: userAgent.has_been_analyzed,
      posts_count: userAgent.scraped_posts_count || 0,
      last_scrape_at: userAgent.last_scrape_at,
      themes_suggested_at: userAgent.themes_suggested_at,
      analysis_summary: userAgent.analysis_summary,
      profile_url: userAgent.linkedin_profile_url,
    });

  } catch (error: any) {
    console.error('[APIFY SCRAPER] GET Error:', error);
    return NextResponse.json(
      { error: error.message || 'Internal server error' },
      { status: 500 }
    );
  }
}

/**
 * Filter posts to only include those from the last N months
 */
function filterPostsByDate(posts: any[], sinceDate: Date): any[] {
  console.log('[APIFY SCRAPER] filterPostsByDate called');
  console.log('[APIFY SCRAPER] Posts is array:', Array.isArray(posts));
  console.log('[APIFY SCRAPER] Posts length:', posts?.length || 0);
  console.log('[APIFY SCRAPER] Since date:', sinceDate.toISOString());

  if (!Array.isArray(posts)) {
    console.log('[APIFY SCRAPER] ⚠️ Posts is not an array, returning empty');
    return [];
  }

  const filtered = posts.filter(post => {
    // Try different date field names the actor might return
    const postDate = post.postedAt || post.date || post.publishedAt || post.created_at || post.timestamp;
    
    if (!postDate) {
      // If no date, include the post (might be recent)
      return true;
    }

    try {
      const date = new Date(postDate);
      return date >= sinceDate;
    } catch {
      return true; // Include if date parsing fails
    }
  });

  console.log('[APIFY SCRAPER] Filtered result count:', filtered.length);
  return filtered;
}
