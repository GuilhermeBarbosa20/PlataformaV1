import { NextResponse } from 'next/server';
import { createClient } from '@/utils/supabase/server';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();

    if (!user) {
      return NextResponse.json({ 
        connected: false, 
        reason: 'not_authenticated',
        message: 'Usuário não autenticado'
      });
    }

    // Buscar credenciais do LinkedIn
    const { data: auth, error } = await supabase
      .from('user_linkedin_auth')
      .select('linkedin_access_token, linkedin_person_urn, token_expires_at')
      .eq('user_id', user.id)
      .single();

    if (error || !auth) {
      return NextResponse.json({ 
        connected: false, 
        reason: 'no_credentials',
        message: 'LinkedIn não conectado para publicação'
      });
    }

    const { linkedin_access_token, linkedin_person_urn, token_expires_at } = auth;

    // Verificar se tem token e person_urn
    if (!linkedin_access_token || !linkedin_person_urn) {
      return NextResponse.json({ 
        connected: false, 
        reason: 'incomplete_credentials',
        message: 'Credenciais do LinkedIn incompletas'
      });
    }

    // Verificar se o token expirou
    if (token_expires_at && new Date(token_expires_at) < new Date()) {
      return NextResponse.json({ 
        connected: false, 
        reason: 'token_expired',
        message: 'Token do LinkedIn expirou. Reconecte sua conta.'
      });
    }

    // Verificar se vai expirar em breve (menos de 7 dias)
    const sevenDaysFromNow = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000);
    const expiringSoon = token_expires_at && new Date(token_expires_at) < sevenDaysFromNow;

    return NextResponse.json({ 
      connected: true,
      expiresAt: token_expires_at,
      expiringSoon,
      message: expiringSoon 
        ? 'LinkedIn conectado, mas o token expira em breve'
        : 'LinkedIn conectado e pronto para publicar'
    });

  } catch (error: any) {
    console.error('[LinkedIn Status] Error:', error);
    return NextResponse.json({ 
      connected: false, 
      reason: 'error',
      message: 'Erro ao verificar status do LinkedIn'
    });
  }
}
