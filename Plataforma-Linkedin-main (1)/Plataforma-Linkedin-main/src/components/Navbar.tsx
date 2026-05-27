'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { createClient } from '@/utils/supabase/client';
import { useEffect, useState } from 'react';
import type { User } from '@supabase/supabase-js';

export default function Navbar() {
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [newsEnabled, setNewsEnabled] = useState(false);
  const [trendsEnabled, setTrendsEnabled] = useState(false);

  useEffect(() => {
    const supabase = createClient();

    // Verificar usuário atual
    supabase.auth.getUser().then(({ data: { user } }) => {
      setUser(user);
      setLoading(false);

      // Fetch user settings if logged in
      if (user) {
        fetchSettings();
      }
    });

    // Escutar mudanças de autenticação
    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
      if (session?.user) {
        fetchSettings();
      } else {
        setNewsEnabled(false);
        setTrendsEnabled(false);
      }
    });

    return () => subscription.unsubscribe();
  }, []);

  const fetchSettings = async () => {
    try {
      const response = await fetch('/api/settings');
      const data = await response.json();
      if (data.success && data.settings) {
        setNewsEnabled(data.settings.news_posts_enabled || false);
        setTrendsEnabled(data.settings.trends_monitoring_enabled || false);
      }
    } catch (error) {
      console.error('Error fetching settings:', error);
    }
  };

  const isActive = (path: string) => {
    return pathname === path
      ? 'text-neutral-900 bg-neutral-100'
      : 'text-neutral-500 hover:text-neutral-900 hover:bg-neutral-50';
  };

  // Não mostrar navbar se estiver carregando ou se não tiver usuário logado
  if (loading || !user) {
    return null;
  }

  return (
    <nav className="bg-white/80 backdrop-blur-md border-b border-neutral-200/60 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-14">
          <div className="flex items-center gap-8">
            <div className="flex-shrink-0 flex items-center gap-2.5">
              <div className="w-7 h-7 bg-neutral-900 rounded-md flex items-center justify-center text-white font-semibold text-xs tracking-tight">
                Li
              </div>
              <Link href="/" className="text-base font-semibold text-neutral-900 tracking-tight">
                Agent
              </Link>
            </div>
            <div className="hidden md:flex md:items-center md:gap-6">
              <Link
                href="/"
                className={`inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium transition-all duration-150 ${isActive('/')}`}
              >
                Dashboard
              </Link>
              <Link
                href="/posts"
                className={`inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium transition-all duration-150 ${isActive('/posts')}`}
              >
                Posts
              </Link>
              <Link
                href="/themes"
                className={`inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium transition-all duration-150 ${isActive('/themes')}`}
              >
                Temas
              </Link>
              <Link
                href="/objectives"
                className={`inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium transition-all duration-150 ${isActive('/objectives')}`}
              >
                Objetivos
              </Link>
              <Link
                href="/ssi"
                className={`inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium transition-all duration-150 ${isActive('/ssi')}`}
              >
                SSI
              </Link>
              <Link
                href="/analytics"
                className={`inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium transition-all duration-150 ${isActive('/analytics')}`}
              >
                <svg className="w-4 h-4 mr-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                Análise
              </Link>
              {/* Conditional News Link */}
              {newsEnabled && (
                <Link
                  href="/news"
                  className={`inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium transition-all duration-150 ${isActive('/news')}`}
                >
                  <svg className="w-4 h-4 mr-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
                  </svg>
                  Notícias
                </Link>
              )}
              {/* Conditional Trends Link */}
              {trendsEnabled && (
                <Link
                  href="/trends"
                  className={`inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium transition-all duration-150 ${isActive('/trends')}`}
                >
                  <svg className="w-4 h-4 mr-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
                  </svg>
                  Tendências
                </Link>
              )}
              <Link
                href="/settings"
                className={`inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium transition-all duration-150 ${isActive('/settings')}`}
              >
                <svg className="w-4 h-4 mr-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                Configurações
              </Link>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden sm:block text-xs text-right">
              <p className="text-neutral-800 font-medium">Usuário</p>
              <p className="text-neutral-400">Pro Plan</p>
            </div>
            <div className="w-8 h-8 bg-neutral-100 border border-neutral-200 rounded-full flex items-center justify-center text-neutral-600 font-medium text-xs">
              US
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
