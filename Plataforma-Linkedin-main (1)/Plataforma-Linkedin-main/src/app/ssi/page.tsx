'use client';

import { useEffect, useState } from 'react';
import { createClient } from '@/utils/supabase/client';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

interface SSIMetrics {
  id: string;
  snapshot_date: string;
  profile_views: number;
  search_appearances: number;
  profile_strength_score: number;
  total_post_impressions: number;
  total_engagement_rate: number;
  recent_posts_count: number;
  followers_count: number;
  connection_requests: number;
}

export default function SSIDashboard() {
  const [metrics, setMetrics] = useState<SSIMetrics[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadMetrics();
  }, []);

  async function loadMetrics() {
    try {
      setLoading(true);
      const supabase = createClient();

      const { data, error: fetchError } = await supabase
        .from('linkedin_ssi_metrics')
        .select('*')
        .order('snapshot_date', { ascending: false })
        .limit(30);

      if (fetchError) throw fetchError;
      setMetrics(data || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleRefresh() {
    try {
      setRefreshing(true);
      const response = await fetch('/api/apify/scrape-ssi', {
        method: 'POST',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to scrape SSI');
      }

      await loadMetrics();
      alert('SSI metrics updated successfully!');
    } catch (err: any) {
      setError(err.message);
      alert(`Error: ${err.message}`);
    } finally {
      setRefreshing(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-[80vh] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-neutral-300 border-t-neutral-800 rounded-full animate-spin"></div>
          <p className="text-sm text-neutral-500">Carregando métricas SSI...</p>
        </div>
      </div>
    );
  }

  const latestMetrics = metrics[0];

  return (
    <div className="min-h-screen bg-neutral-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <header className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8 animate-fadeIn">
          <div>
            <h1 className="text-2xl font-semibold text-neutral-900 tracking-tight">
              LinkedIn SSI Dashboard
            </h1>
            <p className="text-sm text-neutral-500 mt-1">
              {latestMetrics
                ? `Última atualização: ${new Date(latestMetrics.snapshot_date).toLocaleDateString()}`
                : 'Sem dados disponíveis'}
            </p>
          </div>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="bg-neutral-900 hover:bg-neutral-800 disabled:bg-neutral-400 text-white font-medium py-2 px-4 rounded-lg transition-colors text-sm flex items-center gap-2"
          >
            {refreshing ? (
               <>
                 <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                 <span>Atualizando...</span>
               </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                <span>Atualizar Dados</span>
              </>
            )}
          </button>
        </header>

        {error && (
          <div className="bg-rose-50 border border-rose-200 text-rose-700 px-4 py-3 rounded-lg mb-6 flex items-start gap-3 animate-fadeIn">
            <svg className="w-5 h-5 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <p className="font-medium text-sm">Erro ao carregar dados</p>
              <p className="text-xs mt-1 opacity-80">{error}</p>
            </div>
          </div>
        )}

        {metrics.length === 0 ? (
          <div className="bg-white border border-dashed border-neutral-300 rounded-xl p-12 text-center animate-fadeIn">
            <div className="w-14 h-14 bg-neutral-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-7 h-7 text-neutral-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            <h3 className="text-neutral-900 font-medium mb-1">Nenhum dado de SSI disponível</h3>
            <p className="text-neutral-500 text-sm max-w-md mx-auto mb-6">
              Clique no botão abaixo para buscar suas métricas do LinkedIn pela primeira vez.
            </p>
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="bg-neutral-900 hover:bg-neutral-800 disabled:bg-neutral-400 text-white font-medium py-2.5 px-6 rounded-lg transition-colors text-sm"
            >
              {refreshing ? 'Buscando dados...' : 'Buscar Dados Agora'}
            </button>
          </div>
        ) : (
          <>
            {/* Key Metrics Cards */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <MetricCard
                title="Visualizações"
                value={latestMetrics?.profile_views || 0}
                icon={
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                }
              />
              <MetricCard
                title="Pesquisas"
                value={latestMetrics?.search_appearances || 0}
                icon={
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                }
              />
              <MetricCard
                title="Força do Perfil"
                value={`${latestMetrics?.profile_strength_score || 0}%`}
                icon={
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                }
              />
              <MetricCard
                title="Seguidores"
                value={latestMetrics?.followers_count || 0}
                icon={
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                }
              />
            </div>

            {/* Charts Row 1 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
              {/* Profile Views Trend */}
              <div className="bg-white border border-neutral-200 rounded-xl p-5 animate-fadeIn">
                <h2 className="text-neutral-900 text-sm font-medium mb-6">
                  Tendência de Visualizações
                </h2>
                <div className="h-[260px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={[...metrics].reverse()}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f5f5f5" vertical={false} />
                      <XAxis
                        dataKey="snapshot_date"
                        stroke="#a3a3a3"
                        tick={{ fontSize: 11 }}
                        tickFormatter={(value) => new Date(value).toLocaleDateString(undefined, { day: '2-digit', month: '2-digit' })}
                        axisLine={false}
                        tickLine={false}
                        dy={10}
                      />
                      <YAxis 
                        stroke="#a3a3a3" 
                        tick={{ fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                        dx={-10}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#ffffff',
                          border: '1px solid #e5e5e5',
                          borderRadius: '8px',
                          boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.05)',
                          color: '#171717',
                          fontSize: '12px'
                        }}
                        labelStyle={{ color: '#737373', marginBottom: '0.25rem' }}
                        labelFormatter={(value) => new Date(value).toLocaleDateString()}
                      />
                      <Line
                        type="monotone"
                        dataKey="profile_views"
                        stroke="#171717"
                        strokeWidth={2}
                        dot={{ fill: '#171717', r: 3, strokeWidth: 2, stroke: '#fff' }}
                        activeDot={{ r: 5, strokeWidth: 0 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Post Impressions */}
              <div className="bg-white border border-neutral-200 rounded-xl p-5 animate-fadeIn" style={{ animationDelay: '0.1s' }}>
                <h2 className="text-neutral-900 text-sm font-medium mb-6">
                  Impressões de Posts
                </h2>
                <div className="h-[260px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={[...metrics].reverse()}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f5f5f5" vertical={false} />
                      <XAxis
                        dataKey="snapshot_date"
                        stroke="#a3a3a3"
                        tick={{ fontSize: 11 }}
                        tickFormatter={(value) => new Date(value).toLocaleDateString(undefined, { day: '2-digit', month: '2-digit' })}
                        axisLine={false}
                        tickLine={false}
                        dy={10}
                      />
                      <YAxis 
                        stroke="#a3a3a3" 
                        tick={{ fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                        dx={-10}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#ffffff',
                          border: '1px solid #e5e5e5',
                          borderRadius: '8px',
                          boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.05)',
                          color: '#171717',
                          fontSize: '12px'
                        }}
                        labelStyle={{ color: '#737373', marginBottom: '0.25rem' }}
                        labelFormatter={(value) => new Date(value).toLocaleDateString()}
                      />
                      <Line
                        type="monotone"
                        dataKey="total_post_impressions"
                        stroke="#525252"
                        strokeWidth={2}
                        dot={{ fill: '#525252', r: 3, strokeWidth: 2, stroke: '#fff' }}
                        activeDot={{ r: 5, strokeWidth: 0 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            {/* Charts Row 2 */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Engagement Rate */}
              <div className="bg-white border border-neutral-200 rounded-xl p-5 animate-fadeIn" style={{ animationDelay: '0.2s' }}>
                <h2 className="text-neutral-900 text-sm font-medium mb-6">
                  Taxa de Engajamento
                </h2>
                <div className="h-[260px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={[...metrics].reverse()}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f5f5f5" vertical={false} />
                      <XAxis
                        dataKey="snapshot_date"
                        stroke="#a3a3a3"
                        tick={{ fontSize: 11 }}
                        tickFormatter={(value) => new Date(value).toLocaleDateString(undefined, { day: '2-digit', month: '2-digit' })}
                        axisLine={false}
                        tickLine={false}
                        dy={10}
                      />
                      <YAxis 
                        stroke="#a3a3a3" 
                        tick={{ fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                        dx={-10}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#ffffff',
                          border: '1px solid #e5e5e5',
                          borderRadius: '8px',
                          boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.05)',
                          color: '#171717',
                          fontSize: '12px'
                        }}
                        labelStyle={{ color: '#737373', marginBottom: '0.25rem' }}
                        labelFormatter={(value) => new Date(value).toLocaleDateString()}
                      />
                      <Bar
                        dataKey="total_engagement_rate"
                        fill="#404040"
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Network Metrics */}
              <div className="bg-white border border-neutral-200 rounded-xl p-5 animate-fadeIn" style={{ animationDelay: '0.3s' }}>
                <h2 className="text-neutral-900 text-sm font-medium mb-6">
                  Solicitações de Conexão
                </h2>
                <div className="h-[260px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={[...metrics].reverse()}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f5f5f5" vertical={false} />
                      <XAxis
                        dataKey="snapshot_date"
                        stroke="#a3a3a3"
                        tick={{ fontSize: 11 }}
                        tickFormatter={(value) => new Date(value).toLocaleDateString(undefined, { day: '2-digit', month: '2-digit' })}
                        axisLine={false}
                        tickLine={false}
                        dy={10}
                      />
                      <YAxis 
                        stroke="#a3a3a3" 
                        tick={{ fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                        dx={-10}
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#ffffff',
                          border: '1px solid #e5e5e5',
                          borderRadius: '8px',
                          boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.05)',
                          color: '#171717',
                          fontSize: '12px'
                        }}
                        labelStyle={{ color: '#737373', marginBottom: '0.25rem' }}
                        labelFormatter={(value) => new Date(value).toLocaleDateString()}
                      />
                      <Bar
                        dataKey="connection_requests"
                        fill="#737373"
                        radius={[4, 4, 0, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function MetricCard({
  title,
  value,
  icon,
}: {
  title: string;
  value: string | number;
  icon: React.ReactNode;
}) {
  return (
    <div className="bg-white border border-neutral-200 rounded-xl p-4 hover:border-neutral-300 transition-all group animate-fadeIn card-hover">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-neutral-500 text-xs font-medium mb-1">{title}</p>
          <p className="text-neutral-900 text-2xl font-semibold tracking-tight">{value}</p>
        </div>
        <div className="w-9 h-9 bg-neutral-100 rounded-lg flex items-center justify-center text-neutral-500 group-hover:bg-neutral-900 group-hover:text-white transition-colors">
          {icon}
        </div>
      </div>
    </div>
  );
}
