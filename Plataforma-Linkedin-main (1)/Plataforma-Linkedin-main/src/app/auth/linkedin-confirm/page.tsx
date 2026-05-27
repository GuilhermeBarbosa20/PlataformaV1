'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { createClient } from '@/utils/supabase/client';

export default function LinkedInConfirmPage() {
    const router = useRouter();
    const [status, setStatus] = useState('Conectando com LinkedIn...');
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const supabase = createClient();

        const handleAuth = async () => {
            try {
                console.log('[LinkedIn Confirm] Checking URL for session tokens...');
                console.log('[LinkedIn Confirm] URL:', window.location.href);

                // Verificar se há erro na URL primeiro
                const hashParams = new URLSearchParams(window.location.hash.substring(1));
                const urlParams = new URLSearchParams(window.location.search);

                const errorParam = hashParams.get('error') || urlParams.get('error');
                const errorDesc = hashParams.get('error_description') || urlParams.get('error_description');

                if (errorParam) {
                    console.error('[LinkedIn Confirm] Error in URL:', errorParam, errorDesc);
                    throw new Error(errorDesc || errorParam);
                }

                // Tentar obter sessão - o cliente Supabase deve processar tokens automaticamente
                const { data: { session }, error: sessionError } = await supabase.auth.getSession();

                console.log('[LinkedIn Confirm] getSession result:', session ? 'Session found' : 'No session', sessionError);

                if (sessionError) {
                    console.error('[LinkedIn Confirm] Session error:', sessionError);
                    throw sessionError;
                }

                if (session) {
                    console.log('[LinkedIn Confirm] Session established! User:', session.user.email);
                    setStatus('Login com LinkedIn realizado com sucesso!');
                    setTimeout(() => {
                        router.push('/');
                        router.refresh();
                    }, 1000);
                    return;
                }

                // Se não tem sessão imediata, escutar por mudanças de estado
                console.log('[LinkedIn Confirm] No immediate session, listening for auth changes...');
                setStatus('Finalizando autenticação...');

                const { data: { subscription } } = supabase.auth.onAuthStateChange((event, newSession) => {
                    console.log('[LinkedIn Confirm] Auth state change:', event);
                    if (event === 'SIGNED_IN' && newSession) {
                        console.log('[LinkedIn Confirm] SIGNED_IN event received!');
                        setStatus('Autenticado! Redirecionando...');
                        subscription.unsubscribe();
                        setTimeout(() => {
                            router.push('/');
                            router.refresh();
                        }, 500);
                    }
                });

                // Timeout de segurança
                setTimeout(() => {
                    console.log('[LinkedIn Confirm] Timeout reached, checking final state...');
                    supabase.auth.getSession().then(({ data: { session: finalSession } }) => {
                        if (finalSession) {
                            router.push('/');
                            router.refresh();
                        } else {
                            setError('Tempo esgotado. Por favor, tente fazer login novamente.');
                        }
                    });
                }, 8000);

            } catch (err: any) {
                console.error('[LinkedIn Confirm] Error:', err);
                setError(err.message || 'Falha na autenticação');
            }
        };

        handleAuth();
    }, [router]);

    if (error) {
        return (
            <div className="flex min-h-screen flex-col items-center justify-center bg-gray-900 p-4 text-white">
                <div className="rounded-lg bg-red-900/20 p-6 text-center border border-red-500/50 max-w-md">
                    <h1 className="mb-2 text-xl font-bold text-red-500">Erro na Autenticação</h1>
                    <p className="text-gray-300 mb-4">{error}</p>
                    <button
                        onClick={() => router.push('/')}
                        className="rounded bg-blue-600 px-4 py-2 font-bold text-white hover:bg-blue-700 transition"
                    >
                        Tentar Novamente
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="flex min-h-screen flex-col items-center justify-center bg-gray-900 p-4 text-white">
            <div className="text-center">
                <div className="mb-4 inline-block h-12 w-12 animate-spin rounded-full border-4 border-blue-500 border-t-transparent"></div>
                <h1 className="text-xl font-medium text-blue-400">{status}</h1>
                <p className="mt-2 text-sm text-gray-500">Aguarde enquanto conectamos sua conta LinkedIn...</p>
            </div>
        </div>
    );
}
