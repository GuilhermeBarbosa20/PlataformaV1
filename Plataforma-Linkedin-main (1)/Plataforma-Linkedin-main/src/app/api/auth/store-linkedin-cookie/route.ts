import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';

export const dynamic = 'force-dynamic';

export async function POST(req: NextRequest) {
  try {
    const supabase = await createClient();

    // Get user from Supabase Auth
    const {
      data: { user },
      error: authError,
    } = await supabase.auth.getUser();

    if (authError || !user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    // Parse request body
    const { liAtCookie } = await req.json();

    if (!liAtCookie) {
      return NextResponse.json(
        { error: 'liAtCookie is required' },
        { status: 400 }
      );
    }

    // Get user's LinkedIn profile info from Supabase Auth metadata (if available)
    const userMetadata = user.user_metadata || {};
    const linkedinProfileUrl = userMetadata.profile_url || null;
    const linkedinProfileName = userMetadata.full_name || user.email || null;
    const linkedinProfilePhoto = userMetadata.picture || null;

    // Upsert the user's LinkedIn auth data
    const { error: insertError } = await supabase
      .from('user_linkedin_auth')
      .upsert(
        {
          user_id: user.id,
          linkedin_li_at_cookie: liAtCookie,
          linkedin_profile_url: linkedinProfileUrl,
          linkedin_profile_name: linkedinProfileName,
          linkedin_profile_photo: linkedinProfilePhoto,
          cookie_expires_at: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(), // 30 days
        },
        { onConflict: 'user_id' }
      );

    if (insertError) {
      console.error('Database insert error:', insertError);
      return NextResponse.json(
        { error: 'Failed to store LinkedIn cookie', details: insertError.message },
        { status: 500 }
      );
    }

    return NextResponse.json({
      success: true,
      message: 'LinkedIn cookie stored successfully',
    });
  } catch (error: any) {
    console.error('Error storing LinkedIn cookie:', error);
    return NextResponse.json(
      { error: error.message || 'Internal server error' },
      { status: 500 }
    );
  }
}
