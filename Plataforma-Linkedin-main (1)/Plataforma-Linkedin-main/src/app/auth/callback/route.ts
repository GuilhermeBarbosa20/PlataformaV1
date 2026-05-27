import { NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';

export const dynamic = 'force-dynamic';

// Get the base URL from environment or fallback to origin
const getBaseUrl = (requestOrigin: string) => {
  return process.env.NEXT_PUBLIC_BASE_URL || requestOrigin;
};

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const baseUrl = getBaseUrl(origin);
  const code = searchParams.get('code');
  const next = searchParams.get('next') ?? '/';

  console.log('\n========================================');
  console.log('[AUTH CALLBACK] Starting OAuth callback');
  console.log('========================================');
  console.log('[AUTH CALLBACK] Code received:', code ? 'YES' : 'NO');
  console.log('[AUTH CALLBACK] Origin:', origin);
  console.log('[AUTH CALLBACK] Base URL:', baseUrl);

  if (code) {
    const supabase = await createClient();
    const { data: sessionData, error } = await supabase.auth.exchangeCodeForSession(code);
    
    console.log('[AUTH CALLBACK] exchangeCodeForSession - Error:', error?.message || 'null');
    
    if (!error && sessionData?.user) {
      console.log('[AUTH CALLBACK] ✅ Session established!');
      
      const user = sessionData.user;
      const session = sessionData.session;
      
      console.log('[AUTH CALLBACK] User ID:', user.id);
      console.log('[AUTH CALLBACK] User Email:', user.email);
      console.log('[AUTH CALLBACK] User created_at:', user.created_at);
      console.log('[AUTH CALLBACK] Provider token exists:', !!session?.provider_token);

      // Save LinkedIn OAuth credentials if available
      if (session?.provider_token) {
        console.log('[AUTH CALLBACK] Saving LinkedIn credentials...');
        
        // Get person URN from user metadata
        // LinkedIn provides 'sub' in the identity data which is the person ID
        const identities = user.identities || [];
        const linkedinIdentity = identities.find((id: any) => id.provider === 'linkedin_oidc' || id.provider === 'linkedin');
        const personId = linkedinIdentity?.identity_data?.sub || user.user_metadata?.sub;
        const personUrn = personId ? `urn:li:person:${personId}` : null;

        console.log('[AUTH CALLBACK] LinkedIn Person URN:', personUrn);

        // Store LinkedIn credentials
        const { error: linkedinError } = await supabase
          .from('user_linkedin_auth')
          .upsert({
            user_id: user.id,
            linkedin_access_token: session.provider_token,
            linkedin_person_urn: personUrn,
            linkedin_li_at_cookie: session.provider_token, // Keep for compatibility
            linkedin_profile_url: user.user_metadata?.profile_url || null,
            linkedin_profile_name: user.user_metadata?.full_name || user.user_metadata?.name || null,
            linkedin_profile_photo: user.user_metadata?.picture || user.user_metadata?.avatar_url || null,
            token_expires_at: session.expires_at 
              ? new Date(session.expires_at * 1000).toISOString() 
              : new Date(Date.now() + 60 * 24 * 60 * 60 * 1000).toISOString(), // 60 days default
            cookie_expires_at: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
            updated_at: new Date().toISOString(),
          }, { onConflict: 'user_id' });

        if (linkedinError) {
          console.error('[AUTH CALLBACK] Error saving LinkedIn credentials:', linkedinError.message);
        } else {
          console.log('[AUTH CALLBACK] ✅ LinkedIn credentials saved!');
        }
      }

      // Check if this is a first-time login by looking at when the user was created
      const userCreatedAt = new Date(user.created_at);
      const now = new Date();
      const minutesSinceCreation = (now.getTime() - userCreatedAt.getTime()) / (1000 * 60);
      const isNewUser = minutesSinceCreation < 5; // User created less than 5 minutes ago
      
      console.log('[AUTH CALLBACK] Minutes since user creation:', minutesSinceCreation.toFixed(2));
      console.log('[AUTH CALLBACK] Is new user (created < 5 min ago):', isNewUser);

      // Check if user needs onboarding (not completed or new user)
      const { data: userAgent, error: agentError } = await supabase
        .from('user_agents')
        .select('onboarding_completed, onboarding_step, linkedin_profile_url, has_been_analyzed')
        .eq('user_id', user.id)
        .maybeSingle();

      console.log('[AUTH CALLBACK] User Agent check error:', agentError?.message || 'none');
      console.log('[AUTH CALLBACK] User Agent:', userAgent);

      // Determine if onboarding is needed
      const needsOnboarding = isNewUser || !userAgent?.onboarding_completed;

      console.log('[AUTH CALLBACK] Needs onboarding:', needsOnboarding);

      if (needsOnboarding) {
        console.log('[AUTH CALLBACK] 🚀 Redirecting to onboarding...');
        
        // Create initial user_agent record if not exists
        const { error: upsertError } = await supabase
          .from('user_agents')
          .upsert({
            user_id: user.id,
            has_been_analyzed: false,
            onboarding_completed: false,
            onboarding_step: 'profile_url',
            photos_uploaded_count: 0,
            agent_config: {
              user_metadata: user.user_metadata,
              created_at: new Date().toISOString(),
              is_first_login: isNewUser,
            },
            updated_at: new Date().toISOString(),
          }, { onConflict: 'user_id' });

        if (upsertError) {
          console.log('[AUTH CALLBACK] Error creating user_agent:', upsertError.message);
        }

        return NextResponse.redirect(`${baseUrl}/onboarding`);
      }

      console.log('[AUTH CALLBACK] User already onboarded, redirecting to:', next);
      return NextResponse.redirect(`${baseUrl}${next}`);
    }
  }

  console.log('[AUTH CALLBACK] ❌ Auth failed, redirecting home');
  return NextResponse.redirect(`${baseUrl}/`);
}


