'use server';

import { redirect } from 'next/navigation';
import { createClient } from '@/utils/supabase/server';

const baseUrl = process.env.NEXT_PUBLIC_BASE_URL ?? 'http://localhost:3000';

export async function signInWithLinkedIn() {
  // Redireciona para o fluxo OAuth customizado que inclui w_member_social
  redirect(`${baseUrl}/api/linkedin/auth`);
}

export async function signOut() {
  const supabase = await createClient();
  await supabase.auth.signOut();
  redirect('/');
}


