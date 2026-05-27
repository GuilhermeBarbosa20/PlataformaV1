'use client';

import { useEffect, useState } from 'react';
import { createClient } from '@/utils/supabase/client';

type CommunicationTone = 'Leve' | 'Simples' | 'Técnico' | 'Profissional' | 'Criativo' | 'Entusiasta';

interface Theme {
  id: string;
  theme_name: string;
  importance_weight: number;
  communication_tone: CommunicationTone;
  description: string;
  is_suggested: boolean;
}

const TONE_OPTIONS: CommunicationTone[] = ['Leve', 'Simples', 'Técnico', 'Profissional', 'Criativo', 'Entusiasta'];
const SUGGESTED_THEMES = ['Tecnologia', 'Inovação', 'Transformação Digital', 'Culinária', 'Saúde', 'Educação', 'Negócios', 'Marketing', 'Desenvolvimento Pessoal', 'Sustentabilidade'];

export default function ThemesPage() {
  const supabase = createClient();
  const [user, setUser] = useState<any>(null);
  const [themes, setThemes] = useState<Theme[]>([]);
  const [loading, setLoading] = useState(true);
  const [newTheme, setNewTheme] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);
  const [formData, setFormData] = useState({
    theme_name: '',
    importance_weight: 50,
    communication_tone: 'Simples' as CommunicationTone,
    description: '',
  });

  useEffect(() => {
    const initPage = async () => {
      const response = await fetch('/api/auth/get-user');
      const data = await response.json();
      setUser(data.user);

      if (data.user) {
        await loadThemes(data.user.id);
      }
    };
    initPage();
  }, []);

  const loadThemes = async (userId: string) => {
    const { data, error } = await supabase
      .from('user_themes')
      .select('*')
      .eq('user_id', userId)
      .order('created_at', { ascending: false });

    if (!error && data) {
      setThemes(data);
    }
    setLoading(false);
  };

  const addTheme = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.theme_name.trim()) {
      alert('Por favor, dê um nome ao tema');
      return;
    }

    if (!user) return;

    const { error } = await supabase.from('user_themes').insert({
      user_id: user.id,
      ...formData,
    });

    if (!error) {
      alert('✅ Tema adicionado com sucesso!');
      setFormData({
        theme_name: '',
        importance_weight: 50,
        communication_tone: 'Simples',
        description: '',
      });
      setShowAddForm(false);
      await loadThemes(user.id);
    } else {
      alert('❌ Erro ao adicionar tema: ' + error.message);
    }
  };

  const updateTheme = async (id: string, updates: Partial<Theme>) => {
    if (!user) return;

    const { error } = await supabase
      .from('user_themes')
      .update(updates)
      .eq('id', id)
      .eq('user_id', user.id);

    if (!error) {
      await loadThemes(user.id);
    } else {
      alert('❌ Erro ao atualizar tema: ' + error.message);
    }
  };

  const deleteTheme = async (id: string) => {
    if (!confirm('Tem a certeza que quer eliminar este tema?')) return;

    if (!user) return;

    const { error } = await supabase
      .from('user_themes')
      .delete()
      .eq('id', id)
      .eq('user_id', user.id);

    if (!error) {
      alert('✅ Tema eliminado!');
      await loadThemes(user.id);
    } else {
      alert('❌ Erro ao eliminar tema');
    }
  };

  const addSuggestedTheme = async (themeName: string) => {
    if (!user) return;

    const exists = themes.some((t) => t.theme_name.toLowerCase() === themeName.toLowerCase());
    if (exists) {
      alert('Este tema já existe na sua lista');
      return;
    }

    const { error } = await supabase.from('user_themes').insert({
      user_id: user.id,
      theme_name: themeName,
      importance_weight: 50,
      communication_tone: 'Simples',
      is_suggested: true,
    });

    if (!error) {
      alert(`✅ Tema "${themeName}" adicionado!`);
      await loadThemes(user.id);
    } else {
      alert('❌ Erro ao adicionar tema');
    }
  };

  if (loading) {
    return (
      <div className="min-h-[80vh] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-neutral-300 border-t-neutral-800 rounded-full animate-spin"></div>
          <p className="text-sm text-neutral-500">Carregando temas...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-[80vh] flex items-center justify-center">
        <p className="text-neutral-500">Faça login para continuar</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-50">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <header className="mb-8 animate-fadeIn">
          <h1 className="text-2xl font-semibold text-neutral-900 tracking-tight">Temas de Conteúdo</h1>
          <p className="text-sm text-neutral-500 mt-1 max-w-xl">
            Defina os pilares da sua estratégia. O agente usará estes temas e pesos para diversificar seus posts.
          </p>
        </header>

        <div className="grid lg:grid-cols-3 gap-6">
          {/* Left Column: Add & Suggested */}
          <div className="space-y-6">
            {/* Add Theme Card */}
            <div className="bg-white border border-neutral-200 rounded-xl p-5">
              <h2 className="text-sm font-medium text-neutral-900 mb-4">Adicionar Novo</h2>
              
              {!showAddForm ? (
                <button
                  onClick={() => setShowAddForm(true)}
                  className="w-full py-3 border border-dashed border-neutral-300 rounded-lg text-neutral-500 text-sm font-medium hover:border-neutral-400 hover:text-neutral-700 hover:bg-neutral-50 transition-all flex items-center justify-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 4v16m8-8H4" />
                  </svg>
                  Criar tema personalizado
                </button>
              ) : (
                <form onSubmit={addTheme} className="space-y-4 animate-fadeIn">
                  <div>
                    <label className="block text-xs font-medium text-neutral-600 mb-1.5">Nome</label>
                    <input
                      type="text"
                      value={formData.theme_name}
                      onChange={(e) => setFormData({ ...formData, theme_name: e.target.value })}
                      placeholder="ex: Inovação..."
                      className="w-full px-3 py-2 bg-neutral-50 border border-neutral-200 rounded-lg text-neutral-900 text-sm focus:ring-2 focus:ring-neutral-200 focus:border-neutral-300 focus:bg-white outline-none transition-all"
                      autoFocus
                    />
                  </div>

                  <div>
                    <div className="flex justify-between text-xs mb-1.5">
                      <label className="font-medium text-neutral-600">Peso</label>
                      <span className="text-neutral-900 font-medium">{formData.importance_weight}%</span>
                    </div>
                    <input
                      type="range"
                      min="0"
                      max="100"
                      value={formData.importance_weight}
                      onChange={(e) => setFormData({ ...formData, importance_weight: parseInt(e.target.value) })}
                      className="w-full h-1.5 bg-neutral-200 rounded-lg appearance-none cursor-pointer accent-neutral-900"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-neutral-600 mb-1.5">Tom</label>
                    <select
                      value={formData.communication_tone}
                      onChange={(e) => setFormData({ ...formData, communication_tone: e.target.value as CommunicationTone })}
                      className="w-full px-3 py-2 bg-neutral-50 border border-neutral-200 rounded-lg text-neutral-900 text-sm focus:ring-2 focus:ring-neutral-200 focus:border-neutral-300 outline-none transition-all"
                    >
                      {TONE_OPTIONS.map((tone) => (
                        <option key={tone} value={tone}>
                          {tone}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-neutral-600 mb-1.5">Descrição</label>
                    <textarea
                      value={formData.description}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      placeholder="Opcional..."
                      rows={3}
                      className="w-full px-3 py-2 bg-neutral-50 border border-neutral-200 rounded-lg text-neutral-900 text-sm focus:ring-2 focus:ring-neutral-200 focus:border-neutral-300 outline-none transition-all resize-none"
                    />
                  </div>

                  <div className="flex gap-2 pt-2">
                    <button type="submit" className="flex-1 py-2 bg-neutral-900 hover:bg-neutral-800 text-white rounded-lg text-sm font-medium transition-colors">
                      Salvar
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowAddForm(false)}
                      className="px-4 py-2 bg-neutral-100 hover:bg-neutral-200 text-neutral-700 rounded-lg text-sm font-medium transition-colors"
                    >
                      Cancelar
                    </button>
                  </div>
                </form>
              )}
            </div>

            {/* Suggested Themes */}
            <div>
              <h2 className="text-xs font-medium text-neutral-500 uppercase tracking-wider mb-3">Sugestões Populares</h2>
              <div className="flex flex-wrap gap-2">
                {SUGGESTED_THEMES.map((theme) => {
                  const exists = themes.some((t) => t.theme_name.toLowerCase() === theme.toLowerCase());
                  return (
                    <button
                      key={theme}
                      onClick={() => !exists && addSuggestedTheme(theme)}
                      disabled={exists}
                      className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                        exists
                          ? 'bg-neutral-100 text-neutral-400 cursor-default'
                          : 'bg-white border border-neutral-200 text-neutral-600 hover:border-neutral-300 hover:bg-neutral-50'
                      }`}
                    >
                      {exists ? '✓ ' : '+ '}{theme}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Right Column: My Themes List */}
          <div className="lg:col-span-2">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-medium text-neutral-900">
                Meus Temas 
                <span className="text-neutral-400 font-normal ml-2">({themes.length})</span>
              </h2>
            </div>

            {themes.length === 0 ? (
              <div className="bg-white border border-dashed border-neutral-300 p-12 rounded-xl text-center">
                <div className="w-12 h-12 bg-neutral-100 rounded-full flex items-center justify-center mx-auto mb-3">
                  <svg className="w-6 h-6 text-neutral-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" />
                  </svg>
                </div>
                <h3 className="text-neutral-900 font-medium text-sm mb-1">Nenhum tema definido</h3>
                <p className="text-neutral-500 text-xs">Adicione temas personalizados ou escolha das sugestões</p>
              </div>
            ) : (
              <div className="space-y-3">
                {themes.map((theme, index) => (
                  <div 
                    key={theme.id} 
                    className="group bg-white border border-neutral-200 p-4 rounded-xl hover:border-neutral-300 transition-all card-hover animate-fadeIn"
                    style={{ animationDelay: `${index * 0.05}s` }}
                  >
                    <div className="flex justify-between items-start mb-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <h3 className="text-sm font-medium text-neutral-900">{theme.theme_name}</h3>
                          {theme.is_suggested && (
                            <span className="text-[10px] bg-neutral-100 text-neutral-500 px-1.5 py-0.5 rounded font-medium">
                              Sugerido
                            </span>
                          )}
                        </div>
                        {theme.description && (
                          <p className="text-neutral-500 text-xs mt-1 line-clamp-1">{theme.description}</p>
                        )}
                      </div>
                      <button
                        onClick={() => deleteTheme(theme.id)}
                        className="text-neutral-300 hover:text-rose-500 p-1 rounded transition-colors opacity-0 group-hover:opacity-100"
                        title="Remover tema"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>

                    <div className="grid sm:grid-cols-2 gap-4 pt-3 border-t border-neutral-100">
                      <div>
                        <div className="flex justify-between text-xs mb-1.5">
                          <span className="text-neutral-500">Importância</span>
                          <span className="text-neutral-900 font-medium">{theme.importance_weight}%</span>
                        </div>
                        <input
                          type="range"
                          min="0"
                          max="100"
                          value={theme.importance_weight}
                          onChange={(e) => updateTheme(theme.id, { importance_weight: parseInt(e.target.value) })}
                          className="w-full h-1 bg-neutral-200 rounded-lg appearance-none cursor-pointer accent-neutral-900"
                        />
                      </div>

                      <div>
                        <label className="block text-xs text-neutral-500 mb-1.5">Tom de Voz</label>
                        <select
                          value={theme.communication_tone}
                          onChange={(e) => updateTheme(theme.id, { communication_tone: e.target.value as CommunicationTone })}
                          className="w-full px-2 py-1.5 bg-neutral-50 border border-neutral-200 rounded text-xs text-neutral-700 focus:ring-1 focus:ring-neutral-300 focus:border-neutral-300 outline-none"
                        >
                          {TONE_OPTIONS.map((tone) => (
                            <option key={tone} value={tone}>
                              {tone}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
