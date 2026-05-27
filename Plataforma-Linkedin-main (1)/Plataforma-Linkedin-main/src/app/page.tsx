import { createClient } from '@/utils/supabase/server';
import { signInWithLinkedIn, signOut } from './(auth)/actions';
import LinkedInCookieCapture from '@/components/LinkedInCookieCapture';
import { redirect } from 'next/navigation';

export const dynamic = 'force-dynamic';

export default async function HomePage() {
  const supabase = await createClient();

  const {
    data: { user },
    error,
  } = await supabase.auth.getUser();

  console.log('HomePage - User:', user);
  console.log('HomePage - Error:', error);

  // If user is logged in, check if onboarding is complete
  if (user) {
    const { data: userAgent } = await supabase
      .from('user_agents')
      .select('onboarding_completed, onboarding_step')
      .eq('user_id', user.id)
      .maybeSingle();

    console.log('HomePage - UserAgent:', userAgent);

    // Redirect to onboarding if not completed
    if (!userAgent?.onboarding_completed) {
      console.log('HomePage - Redirecting to onboarding...');
      redirect('/onboarding');
    }
  }

  const { data: posts } = await supabase
    .from('posts')
    .select('*')
    .order('scheduled_for', { ascending: true })
    .limit(5);

  return (
    <div className="min-h-screen flex flex-col bg-neutral-50">
      {/* LinkedIn Cookie Capture - runs silently after OAuth callback */}
      {user && <LinkedInCookieCapture />}

      <main className="flex flex-1 flex-col items-center justify-center px-4 sm:px-6">
        {!user ? (
          <div className="max-w-xl space-y-8 text-center py-20 animate-fadeIn">
            <div className="space-y-4">
              <h1 className="text-4xl sm:text-5xl font-semibold tracking-tight text-neutral-900 leading-tight">
                Sua estratégia no LinkedIn,
                <br />
                <span className="text-neutral-500">automatizada.</span>
              </h1>
              <p className="text-lg text-neutral-500 leading-relaxed max-w-md mx-auto">
                Planeje, analise e otimize seu conteúdo com um agente autônomo inteligente.
              </p>
            </div>

            <div className="flex items-center justify-center pt-4">
              <form action={signInWithLinkedIn}>
                <button
                  type="submit"
                  className="rounded-xl bg-neutral-900 px-8 py-4 text-base font-medium text-white shadow-sm hover:bg-neutral-800 hover:shadow-md transition-all duration-200"
                >
                  Conectar com LinkedIn
                </button>
              </form>
            </div>

            <p className="text-xs text-neutral-400 pt-4">
              Ao conectar, você concorda com nossos termos de uso
            </p>
          </div>
        ) : (
          <div className="max-w-5xl w-full space-y-8 py-10 animate-fadeIn">
            {/* Welcome Header */}
            <div className="flex justify-between items-end">
              <div>
                <p className="text-sm text-neutral-500 mb-1">Bem-vindo de volta</p>
                <h2 className="text-2xl font-semibold text-neutral-900">Dashboard</h2>
              </div>
              <form action={signOut}>
                <button
                  type="submit"
                  className="text-sm font-medium text-neutral-400 hover:text-neutral-600 transition-colors"
                >
                  Sair
                </button>
              </form>
            </div>

            {/* Quick Actions */}
            <div className="grid md:grid-cols-3 gap-4">
              <a href="/posts" className="group block p-6 bg-white rounded-xl border border-neutral-200 hover:border-neutral-300 hover:shadow-sm transition-all card-hover">
                <div className="w-10 h-10 bg-neutral-100 rounded-lg flex items-center justify-center mb-4 group-hover:bg-neutral-900 group-hover:text-white transition-colors">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                  </svg>
                </div>
                <h3 className="text-base font-medium text-neutral-900 mb-1">Gerenciar Posts</h3>
                <p className="text-sm text-neutral-500">Visualize e aprove o conteúdo planejado</p>
              </a>

              <a href="/themes" className="group block p-6 bg-white rounded-xl border border-neutral-200 hover:border-neutral-300 hover:shadow-sm transition-all card-hover">
                <div className="w-10 h-10 bg-neutral-100 rounded-lg flex items-center justify-center mb-4 group-hover:bg-neutral-900 group-hover:text-white transition-colors">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
                  </svg>
                </div>
                <h3 className="text-base font-medium text-neutral-900 mb-1">Meus Temas</h3>
                <p className="text-sm text-neutral-500">Defina sobre o que você quer falar</p>
              </a>

              <a href="/ssi" className="group block p-6 bg-white rounded-xl border border-neutral-200 hover:border-neutral-300 hover:shadow-sm transition-all card-hover">
                <div className="w-10 h-10 bg-neutral-100 rounded-lg flex items-center justify-center mb-4 group-hover:bg-neutral-900 group-hover:text-white transition-colors">
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                </div>
                <h3 className="text-base font-medium text-neutral-900 mb-1">Métricas SSI</h3>
                <p className="text-sm text-neutral-500">Acompanhe o crescimento do seu perfil</p>
              </a>
            </div>

            {/* Recent Posts */}
            <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
              <div className="px-6 py-4 border-b border-neutral-100">
                <h3 className="text-sm font-medium text-neutral-900">Próximos Posts</h3>
              </div>
              {posts && posts.length > 0 ? (
                <div className="divide-y divide-neutral-100">
                  {posts.map((post: any) => (
                    <div key={post.id} className="flex items-center gap-4 px-6 py-4 hover:bg-neutral-50 transition-colors">
                      <div className="min-w-[80px]">
                        <p className="text-xs font-medium text-neutral-500 uppercase tracking-wide">
                          {new Date(post.scheduled_for).toLocaleDateString('pt-BR', { weekday: 'short', day: 'numeric' })}
                        </p>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-neutral-900 truncate">
                          {post.caption || post.ai_content?.headline || 'Sem conteúdo definido'}
                        </p>
                      </div>
                      <span className={`
                        text-[10px] px-2 py-1 rounded-full font-medium
                        ${post.approval_status === 'aprovado' ? 'bg-emerald-50 text-emerald-700' :
                          post.approval_status === 'revisar' ? 'bg-rose-50 text-rose-700' :
                            'bg-neutral-100 text-neutral-600'}
                      `}>
                        {post.approval_status}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-12">
                  <p className="text-sm text-neutral-400">Nenhum post agendado</p>
                  <a href="/posts" className="text-sm text-neutral-600 font-medium hover:text-neutral-900 transition-colors mt-2 inline-block">
                    Gerar posts →
                  </a>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
