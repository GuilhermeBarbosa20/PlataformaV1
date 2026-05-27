import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';

export const dynamic = 'force-dynamic';

/**
 * GET /api/linkedin/profile
 * Fetches the authenticated user's LinkedIn profile information using the official LinkedIn API
 * Uses the r_profile_basicinfo scope to get profile URL, name, photo, etc.
 */
export async function GET(req: NextRequest) {
  console.log('\n========================================');
  console.log('[LINKEDIN PROFILE] GET request received');
  console.log('========================================');

  try {
    const supabase = await createClient();
    const { data: { user }, error: authError } = await supabase.auth.getUser();

    console.log('[LINKEDIN PROFILE] Auth check - User ID:', user?.id);
    console.log('[LINKEDIN PROFILE] Auth check - Error:', authError?.message || 'none');

    if (authError || !user) {
      console.log('[LINKEDIN PROFILE] ❌ Unauthorized');
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    // Check for token in header first (passed from callback)
    let accessToken = req.headers.get('x-linkedin-token');
    console.log('[LINKEDIN PROFILE] Token from header:', accessToken ? accessToken.substring(0, 20) + '...' : 'NOT PROVIDED');

    // If no header token, try session
    if (!accessToken) {
      const { data: { session } } = await supabase.auth.getSession();
      accessToken = session?.provider_token || null;
      console.log('[LINKEDIN PROFILE] Token from session:', accessToken ? accessToken.substring(0, 20) + '...' : 'NOT AVAILABLE');
    }
    
    if (!accessToken) {
      console.log('[LINKEDIN PROFILE] ❌ No access token available');
      return NextResponse.json(
        { error: 'LinkedIn access token not found. Please re-authenticate.' },
        { status: 401 }
      );
    }

    // Call LinkedIn API to get profile information
    console.log('\n[LINKEDIN PROFILE] --- Calling LinkedIn API ---');
    console.log('[LINKEDIN PROFILE] Endpoint: https://api.linkedin.com/v2/userinfo');
    
    const linkedinResponse = await fetch('https://api.linkedin.com/v2/userinfo', {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
        'LinkedIn-Version': '202401',
      },
    });

    console.log('[LINKEDIN PROFILE] Response status:', linkedinResponse.status);
    console.log('[LINKEDIN PROFILE] Response statusText:', linkedinResponse.statusText);

    if (!linkedinResponse.ok) {
      const errorText = await linkedinResponse.text();
      console.log('[LINKEDIN PROFILE] ⚠️ userinfo endpoint failed:', errorText);
      
      // Try alternative endpoint for basic profile
      console.log('[LINKEDIN PROFILE] Trying alternative endpoint: /v2/me');
      const altResponse = await fetch('https://api.linkedin.com/v2/me?projection=(id,localizedFirstName,localizedLastName,vanityName)', {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
        },
      });

      console.log('[LINKEDIN PROFILE] Alt response status:', altResponse.status);

      if (!altResponse.ok) {
        const altErrorText = await altResponse.text();
        console.log('[LINKEDIN PROFILE] ❌ Alt endpoint also failed:', altErrorText);
        return NextResponse.json(
          { error: 'Failed to fetch LinkedIn profile', details: errorText },
          { status: linkedinResponse.status }
        );
      }

      const altData = await altResponse.json();
      console.log('[LINKEDIN PROFILE] Alt data:', JSON.stringify(altData, null, 2));
      
      // Build profile URL from vanity name or ID
      const profileUrl = altData.vanityName 
        ? `https://www.linkedin.com/in/${altData.vanityName}/`
        : `https://www.linkedin.com/in/${altData.id}/`;

      console.log('[LINKEDIN PROFILE] ✅ Built profile URL from alt:', profileUrl);

      // Store in database
      await storeProfileData(supabase, user.id, profileUrl, altData.vanityName, altData);

      return NextResponse.json({
        success: true,
        profile_url: profileUrl,
        profile: {
          id: altData.id,
          firstName: altData.localizedFirstName,
          lastName: altData.localizedLastName,
          vanityName: altData.vanityName,
          profileUrl: profileUrl,
        }
      });
    }

    const profileData = await linkedinResponse.json();
    console.log('[LINKEDIN PROFILE] Profile data:', JSON.stringify(profileData, null, 2));

    // Extract profile URL from the response
    const vanityName = profileData.sub || user.user_metadata?.user_name;
    console.log('[LINKEDIN PROFILE] Vanity name extracted:', vanityName);
    
    const profileUrl = vanityName 
      ? `https://www.linkedin.com/in/${vanityName}/`
      : null;

    console.log('[LINKEDIN PROFILE] Final profile URL:', profileUrl);

    // Store in database
    await storeProfileData(supabase, user.id, profileUrl, vanityName, profileData);

    console.log('\n========================================');
    console.log('[LINKEDIN PROFILE] ✅ GET COMPLETE');
    console.log('========================================\n');

    return NextResponse.json({
      success: true,
      profile_url: profileUrl,
      profile: {
        id: profileData.sub,
        name: profileData.name,
        firstName: profileData.given_name,
        lastName: profileData.family_name,
        email: profileData.email,
        picture: profileData.picture,
        vanityName: vanityName,
        profileUrl: profileUrl,
      }
    });

  } catch (error: any) {
    console.log('[LINKEDIN PROFILE] ❌ FATAL ERROR:', error.message);
    console.log('[LINKEDIN PROFILE] Error stack:', error.stack);
    return NextResponse.json(
      { error: error.message || 'Internal server error' },
      { status: 500 }
    );
  }
}

/**
 * POST /api/linkedin/profile
 * Alternative method that tries to get profile from Supabase user metadata
 * when the LinkedIn API direct call fails
 */
export async function POST(req: NextRequest) {
  console.log('\n========================================');
  console.log('[LINKEDIN PROFILE] POST request received');
  console.log('========================================');

  try {
    const supabase = await createClient();
    const { data: { user }, error: authError } = await supabase.auth.getUser();

    console.log('[LINKEDIN PROFILE POST] Auth check - User ID:', user?.id);

    if (authError || !user) {
      console.log('[LINKEDIN PROFILE POST] ❌ Unauthorized');
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    // Try to extract profile URL from user metadata
    const metadata = user.user_metadata || {};
    console.log('[LINKEDIN PROFILE POST] User metadata:', JSON.stringify(metadata, null, 2));

    const vanityName = metadata.user_name || 
                       metadata.preferred_username || 
                       metadata.nickname ||
                       metadata.custom_claims?.vanityName;

    console.log('[LINKEDIN PROFILE POST] Vanity name found:', vanityName || 'NOT FOUND');

    if (!vanityName) {
      // Check if we have stored profile URL
      const { data: linkedinAuth } = await supabase
        .from('user_linkedin_auth')
        .select('linkedin_profile_url')
        .eq('user_id', user.id)
        .single();

      console.log('[LINKEDIN PROFILE POST] Stored profile URL:', linkedinAuth?.linkedin_profile_url || 'NOT FOUND');

      if (linkedinAuth?.linkedin_profile_url) {
        return NextResponse.json({
          success: true,
          profile_url: linkedinAuth.linkedin_profile_url,
          source: 'database',
        });
      }

      console.log('[LINKEDIN PROFILE POST] ❌ Could not determine profile URL');
      return NextResponse.json(
        { error: 'Could not determine LinkedIn profile URL from metadata' },
        { status: 400 }
      );
    }

    const profileUrl = `https://www.linkedin.com/in/${vanityName}/`;
    console.log('[LINKEDIN PROFILE POST] ✅ Built profile URL:', profileUrl);

    // Store in database
    await storeProfileData(supabase, user.id, profileUrl, vanityName, metadata);

    console.log('\n========================================');
    console.log('[LINKEDIN PROFILE POST] ✅ COMPLETE');
    console.log('========================================\n');

    return NextResponse.json({
      success: true,
      profile_url: profileUrl,
      source: 'metadata',
      vanity_name: vanityName,
    });

  } catch (error: any) {
    console.log('[LINKEDIN PROFILE POST] ❌ ERROR:', error.message);
    return NextResponse.json(
      { error: error.message || 'Internal server error' },
      { status: 500 }
    );
  }
}

/**
 * Helper to store profile data in database
 */
async function storeProfileData(
  supabase: any, 
  userId: string, 
  profileUrl: string | null, 
  vanityName: string | null,
  profileData: any
) {
  console.log('[STORE PROFILE] Storing profile data...');
  console.log('[STORE PROFILE] User ID:', userId);
  console.log('[STORE PROFILE] Profile URL:', profileUrl);
  console.log('[STORE PROFILE] Vanity Name:', vanityName);

  // Update user_linkedin_auth
  const { error: updateError } = await supabase
    .from('user_linkedin_auth')
    .upsert({
      user_id: userId,
      linkedin_profile_url: profileUrl,
      linkedin_profile_name: profileData.name || `${profileData.given_name || ''} ${profileData.family_name || ''}`.trim(),
      linkedin_profile_photo: profileData.picture,
      linkedin_li_at_cookie: '',
      updated_at: new Date().toISOString(),
    }, {
      onConflict: 'user_id',
    });

  if (updateError) {
    console.log('[STORE PROFILE] ⚠️ Error updating user_linkedin_auth:', updateError.message);
  } else {
    console.log('[STORE PROFILE] ✅ user_linkedin_auth updated');
  }

  // Update user_agents record
  const { error: agentError } = await supabase
    .from('user_agents')
    .upsert({
      user_id: userId,
      linkedin_profile_url: profileUrl,
      linkedin_vanity_name: vanityName,
      updated_at: new Date().toISOString(),
    }, {
      onConflict: 'user_id',
    });

  if (agentError) {
    console.log('[STORE PROFILE] ⚠️ Error updating user_agents:', agentError.message);
  } else {
    console.log('[STORE PROFILE] ✅ user_agents updated');
  }
}
