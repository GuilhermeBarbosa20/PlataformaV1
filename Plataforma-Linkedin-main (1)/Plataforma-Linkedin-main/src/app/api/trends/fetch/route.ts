import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';

export const dynamic = 'force-dynamic';

const APIFY_TOKEN = process.env.APIFY_API_TOKEN;
const APIFY_ACTOR_ID = 'LQQIXN9Othf8f7R5n'; // LinkedIn Posts Scraper actor

/**
 * POST /api/trends/fetch
 * Fetch recent posts from all monitored profiles using Apify
 * Only fetches posts from last 48 hours to optimize costs
 */
export async function POST(request: NextRequest) {
    console.log('\n========================================');
    console.log('[TRENDS FETCH] Starting fetch for monitored profiles');
    console.log('========================================');

    try {
        const supabase = await createClient();
        const { data: { user }, error: authError } = await supabase.auth.getUser();

        if (authError || !user) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        if (!APIFY_TOKEN) {
            console.log('[TRENDS FETCH] ❌ APIFY_API_TOKEN not configured');
            return NextResponse.json({ error: 'Apify não configurado' }, { status: 500 });
        }

        // Get all monitored profiles
        const { data: profiles, error: profilesError } = await supabase
            .from('monitored_profiles')
            .select('*')
            .eq('user_id', user.id);

        if (profilesError) {
            console.error('[TRENDS FETCH] Error fetching profiles:', profilesError);
            return NextResponse.json({ error: 'Failed to fetch profiles' }, { status: 500 });
        }

        if (!profiles || profiles.length === 0) {
            return NextResponse.json({
                success: true,
                message: 'Nenhum perfil monitorado',
                posts_count: 0,
            });
        }

        console.log(`[TRENDS FETCH] Found ${profiles.length} profiles to fetch`);

        // Calculate 48 hours ago
        const cutoffDate = new Date();
        cutoffDate.setHours(cutoffDate.getHours() - 48);
        console.log('[TRENDS FETCH] Fetching posts since:', cutoffDate.toISOString());

        let totalPosts = 0;
        const results: any[] = [];

        // Process each profile
        for (const profile of profiles) {
            console.log(`[TRENDS FETCH] Processing: ${profile.profile_vanity_name || profile.profile_url}`);

            try {
                // Run Apify actor for this profile
                const apifyInput = {
                    username: profile.profile_url,
                    limit: 10, // Max 10 posts per profile
                    page_number: 1,
                };

                const apifyUrl = `https://api.apify.com/v2/acts/${APIFY_ACTOR_ID}/runs?token=${APIFY_TOKEN}`;
                const runResponse = await fetch(apifyUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(apifyInput),
                });

                if (!runResponse.ok) {
                    console.error(`[TRENDS FETCH] Apify run failed for ${profile.profile_vanity_name}`);
                    continue;
                }

                const runData = await runResponse.json();
                const runId = runData.data?.id;

                if (!runId) {
                    console.error(`[TRENDS FETCH] No run ID for ${profile.profile_vanity_name}`);
                    continue;
                }

                // Wait for Apify to complete (poll with timeout)
                const maxWaitTime = 60000; // 1 minute per profile
                const pollInterval = 3000;
                const startTime = Date.now();
                let runStatus = 'RUNNING';
                let datasetId: string | null = null;

                while (runStatus === 'RUNNING' || runStatus === 'READY') {
                    if (Date.now() - startTime > maxWaitTime) break;
                    await new Promise(resolve => setTimeout(resolve, pollInterval));

                    const statusUrl = `https://api.apify.com/v2/acts/${APIFY_ACTOR_ID}/runs/${runId}?token=${APIFY_TOKEN}`;
                    const statusRes = await fetch(statusUrl);
                    if (statusRes.ok) {
                        const statusData = await statusRes.json();
                        runStatus = statusData.data?.status;
                        datasetId = statusData.data?.defaultDatasetId;
                    }
                }

                if (runStatus !== 'SUCCEEDED' || !datasetId) {
                    console.log(`[TRENDS FETCH] Run incomplete for ${profile.profile_vanity_name}`);
                    continue;
                }

                // Fetch posts from dataset
                const datasetUrl = `https://api.apify.com/v2/datasets/${datasetId}/items?token=${APIFY_TOKEN}`;
                const datasetRes = await fetch(datasetUrl);

                if (!datasetRes.ok) continue;

                const posts = await datasetRes.json();

                if (!Array.isArray(posts)) continue;

                // Filter posts from last 48 hours and save to database
                for (const post of posts) {
                    const postDate = post.postedAt || post.date || post.publishedAt;
                    let isRecent = true;

                    if (postDate) {
                        try {
                            const date = new Date(postDate);
                            isRecent = date >= cutoffDate;
                        } catch {
                            // If parsing fails, include the post
                        }
                    }

                    if (!isRecent) continue;

                    // Upsert post to database
                    const postUrn = post.urn || post.id || `${profile.id}-${Date.now()}-${Math.random()}`;

                    const { error: upsertError } = await supabase
                        .from('monitored_posts')
                        .upsert({
                            user_id: user.id,
                            profile_id: profile.id,
                            linkedin_post_urn: postUrn,
                            post_url: post.url || post.postUrl,
                            post_content: post.text || post.content || post.description || '',
                            author_name: post.authorName || profile.profile_name,
                            author_avatar_url: post.authorProfilePicture || profile.profile_avatar_url,
                            posted_at: postDate ? new Date(postDate).toISOString() : new Date().toISOString(),
                            likes_count: post.numLikes || post.likesCount || 0,
                            comments_count: post.numComments || post.commentsCount || 0,
                            updated_at: new Date().toISOString(),
                        }, {
                            onConflict: 'user_id,linkedin_post_urn',
                        });

                    if (!upsertError) {
                        totalPosts++;
                    }
                }

                // Update last_fetched_at for profile
                await supabase
                    .from('monitored_profiles')
                    .update({ last_fetched_at: new Date().toISOString() })
                    .eq('id', profile.id);

                results.push({
                    profile: profile.profile_name,
                    posts_count: posts.length,
                });

            } catch (err) {
                console.error(`[TRENDS FETCH] Error processing ${profile.profile_vanity_name}:`, err);
            }
        }

        console.log(`[TRENDS FETCH] ✅ Complete. Total posts saved: ${totalPosts}`);

        return NextResponse.json({
            success: true,
            message: `${totalPosts} posts coletados dos últimos 48 horas`,
            posts_count: totalPosts,
            profiles_processed: profiles.length,
            results,
        });

    } catch (error: any) {
        console.error('[TRENDS FETCH] Error:', error);
        return NextResponse.json({ error: error.message || 'Internal server error' }, { status: 500 });
    }
}
