import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || new URL(request.url).origin;
  const clientId = process.env.LINKEDIN_CLIENT_ID;
  const redirectUri = `${baseUrl}/api/linkedin/callback`;

  if (!clientId) {
    console.error('[LinkedIn Auth] LINKEDIN_CLIENT_ID not configured');
    return NextResponse.redirect(`${baseUrl}/?error=linkedin_not_configured`);
  }

  // Escopos oficiais do LinkedIn para login + publicar posts
  // Nota: r_member_postAnalytics requer aprovação especial do LinkedIn
  const scopes = process.env.LINKEDIN_SCOPES || 'openid profile email w_member_social';

  // State para proteção CSRF
  const state = crypto.randomUUID();

  // Construir URL de autorização do LinkedIn (OAuth 2.0 oficial)
  const authUrl = new URL('https://www.linkedin.com/oauth/v2/authorization');
  authUrl.searchParams.set('response_type', 'code');
  authUrl.searchParams.set('client_id', clientId);
  authUrl.searchParams.set('redirect_uri', redirectUri);
  authUrl.searchParams.set('state', state);
  authUrl.searchParams.set('scope', scopes);

  console.log('[LinkedIn Auth] Redirecting to LinkedIn OAuth...');
  console.log('[LinkedIn Auth] Redirect URI:', redirectUri);

  // Salvar state em cookie para validação no callback
  const response = NextResponse.redirect(authUrl.toString());
  response.cookies.set('linkedin_oauth_state', state, {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: 600, // 10 minutos
    path: '/',
  });

  return response;
}
