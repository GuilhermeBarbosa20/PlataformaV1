import { NextRequest, NextResponse } from 'next/server';
import { createClient as createAdminClient } from '@supabase/supabase-js';
import { createServerClient } from '@supabase/ssr';
import { cookies } from 'next/headers';

export const dynamic = 'force-dynamic';

// Gera uma senha determinística baseada no LinkedIn ID + secret
function generateUserPassword(linkedinId: string, secret: string): string {
  // Combinação simples mas segura - em produção pode usar HMAC
  const combined = `${linkedinId}:${secret}:linkedin_oauth_user`;
  // Criar um hash simples convertendo para base64
  const base64 = Buffer.from(combined).toString('base64');
  return `Lnkd_${base64.substring(0, 32)}!`;
}

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const code = searchParams.get('code');
  const state = searchParams.get('state');
  const error = searchParams.get('error');
  const errorDescription = searchParams.get('error_description');

  const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || request.nextUrl.origin;

  // Verificar erro retornado pelo LinkedIn
  if (error) {
    console.error('[LinkedIn Callback] Error from LinkedIn:', error, errorDescription);
    return NextResponse.redirect(`${baseUrl}/?error=linkedin_${error}`);
  }

  // Verificar state para proteção CSRF
  const savedState = request.cookies.get('linkedin_oauth_state')?.value;
  if (!state || state !== savedState) {
    console.error('[LinkedIn Callback] State mismatch - possible CSRF attack');
    return NextResponse.redirect(`${baseUrl}/?error=invalid_state`);
  }

  if (!code) {
    console.error('[LinkedIn Callback] No authorization code received');
    return NextResponse.redirect(`${baseUrl}/?error=no_code`);
  }

  try {
    const clientId = process.env.LINKEDIN_CLIENT_ID;
    const clientSecret = process.env.LINKEDIN_CLIENT_SECRET;
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
    const passwordSecret = process.env.LINKEDIN_PASSWORD_SECRET || supabaseServiceKey; // Use service key como fallback
    const redirectUri = `${baseUrl}/api/linkedin/callback`;

    if (!clientId || !clientSecret) {
      throw new Error('LinkedIn credentials not configured');
    }

    if (!supabaseUrl || !supabaseServiceKey || !supabaseAnonKey) {
      throw new Error('Supabase credentials not configured');
    }

    console.log('[LinkedIn Callback] Exchanging code for access token...');

    // 1. Trocar authorization code por access_token (API oficial do LinkedIn)
    const tokenResponse = await fetch('https://www.linkedin.com/oauth/v2/accessToken', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        grant_type: 'authorization_code',
        code,
        client_id: clientId,
        client_secret: clientSecret,
        redirect_uri: redirectUri,
      }),
    });

    if (!tokenResponse.ok) {
      const errorText = await tokenResponse.text();
      console.error('[LinkedIn Callback] Token exchange failed:', tokenResponse.status, errorText);
      throw new Error('Failed to exchange code for token');
    }

    const tokenData = await tokenResponse.json();
    const accessToken = tokenData.access_token;
    const expiresIn = tokenData.expires_in || 5184000;
    const refreshToken = tokenData.refresh_token || null;

    console.log('[LinkedIn Callback] Access token received, expires_in:', expiresIn);

    // 2. Buscar informações do usuário do LinkedIn
    const userInfoResponse = await fetch('https://api.linkedin.com/v2/userinfo', {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
      },
    });

    if (!userInfoResponse.ok) {
      console.error('[LinkedIn Callback] Failed to get user info:', userInfoResponse.status);
      throw new Error('Failed to get LinkedIn user info');
    }

    const userInfo = await userInfoResponse.json();

    console.log('[LinkedIn Callback] LinkedIn user info:', {
      sub: userInfo.sub,
      email: userInfo.email,
      name: userInfo.name,
    });

    const linkedinId = userInfo.sub;
    const email = userInfo.email;
    const name = userInfo.name;
    const picture = userInfo.picture;
    const personUrn = `urn:li:person:${linkedinId}`;
    const expiresAt = new Date(Date.now() + expiresIn * 1000).toISOString();

    if (!email) {
      throw new Error('LinkedIn did not provide email address');
    }

    // Gerar senha determinística para este usuário
    const userPassword = generateUserPassword(linkedinId, passwordSecret!);

    // 3. Criar cliente Supabase Admin
    const supabaseAdmin = createAdminClient(supabaseUrl, supabaseServiceKey, {
      auth: {
        autoRefreshToken: false,
        persistSession: false,
      },
    });

    // 4. Tentar criar usuário ou atualizar existente
    let supabaseUser: any = null;
    let isNewUser = false;

    console.log('[LinkedIn Callback] Attempting to create/find user...');

    // Tentar criar o usuário com senha
    const { data: newUser, error: createError } = await supabaseAdmin.auth.admin.createUser({
      email,
      password: userPassword,
      email_confirm: true,
      user_metadata: {
        full_name: name,
        avatar_url: picture,
        linkedin_id: linkedinId,
        provider: 'linkedin',
      },
    });

    if (createError) {
      if (createError.code === 'email_exists' || createError.message?.includes('already been registered')) {
        console.log('[LinkedIn Callback] User already exists, fetching and updating password...');

        // Buscar usuário existente
        const { data: usersData } = await supabaseAdmin.auth.admin.listUsers({
          page: 1,
          perPage: 1000
        });

        supabaseUser = usersData?.users?.find(u => u.email?.toLowerCase() === email.toLowerCase());

        if (!supabaseUser) {
          console.error('[LinkedIn Callback] Could not find existing user');
          throw new Error('User exists but could not be found');
        }

        console.log('[LinkedIn Callback] Found existing user:', supabaseUser.id);

        // Atualizar usuário com nova senha e metadata
        await supabaseAdmin.auth.admin.updateUserById(supabaseUser.id, {
          password: userPassword,
          user_metadata: {
            ...supabaseUser.user_metadata,
            full_name: name,
            avatar_url: picture,
            linkedin_id: linkedinId,
          },
        });
      } else {
        console.error('[LinkedIn Callback] Failed to create user:', createError);
        throw createError;
      }
    } else {
      supabaseUser = newUser.user;
      isNewUser = true;
      console.log('[LinkedIn Callback] New user created:', supabaseUser.id);
    }

    // 5. Salvar tokens do LinkedIn na tabela user_linkedin_auth
    console.log('[LinkedIn Callback] Saving LinkedIn tokens for user:', supabaseUser.id);
    console.log('[LinkedIn Callback] Person URN:', personUrn);
    console.log('[LinkedIn Callback] Token expires at:', expiresAt);

    const { data: existingAuth, error: existingAuthError } = await supabaseAdmin
      .from('user_linkedin_auth')
      .select('id')
      .eq('user_id', supabaseUser.id)
      .single();

    if (existingAuthError && existingAuthError.code !== 'PGRST116') {
      console.error('[LinkedIn Callback] Error checking existing auth:', existingAuthError);
    }

    const authData = {
      user_id: supabaseUser.id,
      linkedin_access_token: accessToken,
      linkedin_refresh_token: refreshToken,
      linkedin_person_urn: personUrn,
      token_expires_at: expiresAt,
      updated_at: new Date().toISOString(),
    };

    let saveError: any = null;
    if (existingAuth) {
      console.log('[LinkedIn Callback] Updating existing auth record...');
      const { error } = await supabaseAdmin
        .from('user_linkedin_auth')
        .update(authData)
        .eq('user_id', supabaseUser.id);
      saveError = error;
    } else {
      console.log('[LinkedIn Callback] Creating new auth record...');
      const { error } = await supabaseAdmin
        .from('user_linkedin_auth')
        .insert({
          ...authData,
          created_at: new Date().toISOString(),
        });
      saveError = error;
    }

    if (saveError) {
      console.error('[LinkedIn Callback] FAILED to save LinkedIn tokens:', saveError);
      throw new Error('Failed to save LinkedIn tokens: ' + saveError.message);
    }

    console.log('[LinkedIn Callback] LinkedIn tokens saved successfully!');

    // 6. Fazer login com senha usando SSR client para setar cookies corretamente
    const cookieStore = await cookies();

    const supabaseSSR = createServerClient(supabaseUrl, supabaseAnonKey, {
      cookies: {
        get(name: string) {
          return cookieStore.get(name)?.value;
        },
        set(name: string, value: string, options: any) {
          try {
            cookieStore.set({ name, value, ...options });
          } catch (error) {
            // Ignore errors in read-only context
          }
        },
        remove(name: string, options: any) {
          try {
            cookieStore.set({ name, value: '', ...options });
          } catch (error) {
            // Ignore errors in read-only context
          }
        },
      },
    });

    console.log('[LinkedIn Callback] Signing in with password...');

    const { data: signInData, error: signInError } = await supabaseSSR.auth.signInWithPassword({
      email,
      password: userPassword,
    });

    if (signInError) {
      console.error('[LinkedIn Callback] Sign in failed:', signInError);
      throw new Error('Failed to create session: ' + signInError.message);
    }

    console.log('[LinkedIn Callback] Session created successfully!');
    console.log('[LinkedIn Callback] User:', signInData.user?.email);

    // Check if user has completed onboarding
    const { data: userAgent } = await supabaseAdmin
      .from('user_agents')
      .select('onboarding_completed')
      .eq('user_id', supabaseUser.id)
      .maybeSingle();

    const needsOnboarding = isNewUser || !userAgent?.onboarding_completed;
    console.log('[LinkedIn Callback] Needs onboarding:', needsOnboarding);

    // Redirecionar para onboarding se necessário, senão para home
    const redirectPath = needsOnboarding ? '/onboarding' : '/';
    const response = NextResponse.redirect(`${baseUrl}${redirectPath}`);

    // Limpar cookie de state
    response.cookies.delete('linkedin_oauth_state');

    return response;

  } catch (err: any) {
    console.error('[LinkedIn Callback] Error:', err);

    const response = NextResponse.redirect(`${baseUrl}/?error=auth_failed&message=${encodeURIComponent(err.message)}`);
    response.cookies.delete('linkedin_oauth_state');

    return response;
  }
}
