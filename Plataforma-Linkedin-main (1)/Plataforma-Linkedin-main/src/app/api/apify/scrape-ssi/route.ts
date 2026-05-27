import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';

export const dynamic = 'force-dynamic';

export async function POST(req: NextRequest) {
  try {
    const supabase = await createClient();
    const { data: { user }, error: authError } = await supabase.auth.getUser();

    if (authError || !user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    // Check if already scraped today
    const today = new Date().toISOString().split('T')[0];
    const { data: existingData } = await supabase
      .from('linkedin_ssi_metrics')
      .select('id')
      .eq('user_id', user.id)
      .eq('snapshot_date', today)
      .single();

    if (existingData) {
      return NextResponse.json({
        success: false,
        message: '⚠️ Já foi feito scraping hoje. Tente amanhã!',
      }, { status: 200 });
    }

    // Get LinkedIn cookie from database
    const { data: linkedinAuth, error: fetchError } = await supabase
      .from('user_linkedin_auth')
      .select('linkedin_li_at_cookie')
      .eq('user_id', user.id)
      .single();

    if (fetchError || !linkedinAuth?.linkedin_li_at_cookie) {
      return NextResponse.json(
        { error: 'LinkedIn cookie not found. Please log in with LinkedIn.' },
        { status: 401 }
      );
    }

    // TODO: Call Apify API to scrape SSI data
    console.log('✅ Cookie found, ready for Apify scraping');

    // Save empty metrics with timestamp
    const { error: insertError } = await supabase
      .from('linkedin_ssi_metrics')
      .insert({
        user_id: user.id,
        snapshot_date: today,
        profile_views: null,
        search_appearances: null,
        profile_strength_score: null,
        total_post_impressions: null,
        total_engagement_rate: null,
        recent_posts_count: null,
        followers_count: null,
        connection_requests: null,
        raw_payload: { status: 'pending', timestamp: new Date().toISOString() },
      });

    if (insertError) {
      console.error('Database insert error:', insertError);
      return NextResponse.json(
        { error: 'Failed to save metrics', details: insertError.message },
        { status: 500 }
      );
    }

    return NextResponse.json({
      success: true,
      message: '⏳ Scraping iniciado. Dados serão atualizados em breve.',
    });
  } catch (error: any) {
    console.error('Error in scrape-ssi:', error);
    return NextResponse.json(
      { error: error.message || 'Internal server error' },
      { status: 500 }
    );
  }
}

/**
 * Parse Apify SSI results and extract key metrics
 * Maps the SSI score and pillar breakdown to the database schema
 */
function parseApifySSIData(apifyResults: any) {
  const firstResult = Array.isArray(apifyResults) ? apifyResults[0] : apifyResults;

  // Extract the total SSI score (0-100)
  const profileStrengthScore = firstResult?.ssi_total
    ? parseInt(firstResult.ssi_total.replace(/\D/g, ''), 10) || 0
    : 0;

  return {
    profileViews: 0, // SSI page doesn't explicitly show profile views
    searchAppearances: 0, // SSI page doesn't explicitly show search appearances
    profileStrengthScore: profileStrengthScore,
    totalPostImpressions: 0, // Will be populated from analytics table separately
    totalEngagementRate: 0, // Will be populated from analytics table separately
    recentPostsCount: 0, // Will be populated from analytics table separately
    followersCount: 0, // Will be populated from analytics table separately
    connectionRequests: 0, // Will be populated from analytics table separately
  };
}
