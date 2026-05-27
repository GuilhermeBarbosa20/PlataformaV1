'use client';

import { useEffect, useState, ReactNode } from 'react';
import { createClient } from '@/utils/supabase/client';

type ObjectiveType = 'Aumentar seguidores' | 'Aumentar visualizações' | 'Aumentar relevância' | 'Gerar leads' | 'Construir comunidade' | 'Estabelecer autoridade' | 'Networking';

interface Objective {
  id: string;
  objective: ObjectiveType;
  is_active: boolean;
  priority: number;
}

const OBJECTIVE_OPTIONS: ObjectiveType[] = [
  'Aumentar seguidores',
  'Aumentar visualizações',
  'Aumentar relevância',
  'Gerar leads',
  'Construir comunidade',
  'Estabelecer autoridade',
  'Networking',
];

const OBJECTIVE_DESCRIPTIONS: Record<ObjectiveType, string> = {
  'Aumentar seguidores': 'Focar em estratégias para ganhar novos seguidores',
  'Aumentar visualizações': 'Optimizar conteúdo para máximo alcance e impressões',
  'Aumentar relevância': 'Estabelecer-se como autoridade no seu nicho',
  'Gerar leads': 'Converter seguidores em oportunidades de negócio',
  'Construir comunidade': 'Engajar e criar relacionamentos autênticos',
  'Estabelecer autoridade': 'Demonstrar expertise e credibilidade',
  'Networking': 'Expandir conexões profissionais de qualidade',
};

const OBJECTIVE_ICONS: Record<ObjectiveType, ReactNode> = {
  'Aumentar seguidores': <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />,
  'Aumentar visualizações': <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />,
  'Aumentar relevância': <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 10V3L4 14h7v7l9-11h-7z" />,
  'Gerar leads': <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />,
  'Construir comunidade': <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />,
  'Estabelecer autoridade': <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />,
  'Networking': <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />,
};

export default function ObjectivesPage() {
  const supabase = createClient();
  const [user, setUser] = useState<any>(null);
  const [objectives, setObjectives] = useState<Objective[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initPage = async () => {
      try {
        const response = await fetch('/api/auth/get-user');
        const data = await response.json();
        setUser(data.user);

        if (data.user) {
          await loadObjectives(data.user.id);
        } else {
          setLoading(false);
        }
      } catch (err) {
        console.error('Error initializing page:', err);
        setLoading(false);
      }
    };
    initPage();
  }, []);

  const loadObjectives = async (userId: string) => {
    try {
      const { data, error } = await supabase
        .from('user_objectives')
        .select('*')
        .eq('user_id', userId)
        .order('priority', { ascending: false });

      if (error) {
        console.error('Error loading objectives:', error);
      }

      if (data) {
        setObjectives(data);
      } else {
        setObjectives([]);
      }
    } catch (err) {
      console.error('Exception loading objectives:', err);
      setObjectives([]);
    } finally {
      setLoading(false);
    }
  };

  const toggleObjective = async (objectiveId: string, objectiveName: ObjectiveType, isActive: boolean) => {
    if (!user) return;

    if (isActive) {
      const { error } = await supabase
        .from('user_objectives')
        .delete()
        .eq('id', objectiveId)
        .eq('user_id', user.id);

      if (!error) {
        await loadObjectives(user.id);
      } else {
        alert('❌ Erro ao remover objetivo');
      }
    } else {
      const { error } = await supabase.from('user_objectives').insert({
        user_id: user.id,
        objective: objectiveName,
        is_active: true,
        priority: objectives.length,
      });

      if (!error) {
        await loadObjectives(user.id);
      } else {
        alert('❌ Erro ao adicionar objetivo');
      }
    }
  };

  const updatePriority = async (objectiveId: string, newPriority: number) => {
    if (!user) return;

    // Update local state immediately for instant UI feedback
    setObjectives(prev =>
      prev.map(obj =>
        obj.id === objectiveId ? { ...obj, priority: newPriority } : obj
      )
    );

    // Persist to database in background (no await, no reload needed)
    supabase
      .from('user_objectives')
      .update({ priority: newPriority })
      .eq('id', objectiveId)
      .eq('user_id', user.id)
      .then(({ error }) => {
        if (error) {
          console.error('Error updating priority:', error);
        }
      });
  };

  if (loading) {
    return (
      <div className="min-h-[80vh] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-neutral-300 border-t-neutral-800 rounded-full animate-spin"></div>
          <p className="text-sm text-neutral-500">Carregando objetivos...</p>
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

  const activeObjectives = objectives.filter((o) => o.is_active);

  return (
    <div className="min-h-screen bg-neutral-50">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <header className="mb-8 animate-fadeIn">
          <h1 className="text-2xl font-semibold text-neutral-900 tracking-tight">Objetivos Estratégicos</h1>
          <p className="text-sm text-neutral-500 mt-1 max-w-xl">
            Defina o que você quer alcançar no LinkedIn. O agente priorizará conteúdos que ajudem a atingir estas metas.
          </p>
        </header>

        <div className="grid lg:grid-cols-2 gap-6">
          {/* Available Objectives */}
          <div>
            <h2 className="text-sm font-medium text-neutral-900 mb-4">Catálogo de Objetivos</h2>
            <div className="space-y-2">
              {OBJECTIVE_OPTIONS.map((objective, index) => {
                const isSelected = objectives.some((o) => o.objective === objective && o.is_active);
                const objectiveData = objectives.find((o) => o.objective === objective && o.is_active);

                return (
                  <button
                    key={objective}
                    onClick={() => toggleObjective(objectiveData?.id || '', objective, isSelected)}
                    className={`w-full p-4 rounded-xl text-left transition-all border animate-fadeIn ${isSelected
                      ? 'bg-neutral-900 border-neutral-900 text-white'
                      : 'bg-white border-neutral-200 text-neutral-600 hover:border-neutral-300 hover:shadow-sm'
                      }`}
                    style={{ animationDelay: `${index * 0.05}s` }}
                  >
                    <div className="flex items-start gap-3">
                      <div className={`mt-0.5 w-5 h-5 rounded-full border-2 flex items-center justify-center transition-colors flex-shrink-0 ${isSelected ? 'bg-white border-white' : 'border-neutral-300'
                        }`}>
                        {isSelected && (
                          <svg className="w-3 h-3 text-neutral-900" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                          </svg>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className={`font-medium text-sm ${isSelected ? 'text-white' : 'text-neutral-900'}`}>{objective}</p>
                        <p className={`text-xs mt-0.5 ${isSelected ? 'text-neutral-300' : 'text-neutral-500'}`}>
                          {OBJECTIVE_DESCRIPTIONS[objective]}
                        </p>
                      </div>
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${isSelected ? 'bg-white/10' : 'bg-neutral-100'
                        }`}>
                        <svg className={`w-4 h-4 ${isSelected ? 'text-white' : 'text-neutral-500'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          {OBJECTIVE_ICONS[objective]}
                        </svg>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Selected Objectives with Priority */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-medium text-neutral-900">
                Meus Objetivos
                <span className="text-neutral-400 font-normal ml-2">({activeObjectives.length})</span>
              </h2>
            </div>

            {activeObjectives.length === 0 ? (
              <div className="bg-white border border-dashed border-neutral-300 p-12 rounded-xl text-center">
                <div className="w-12 h-12 bg-neutral-100 rounded-full flex items-center justify-center mx-auto mb-3">
                  <svg className="w-6 h-6 text-neutral-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
                  </svg>
                </div>
                <h3 className="text-neutral-900 font-medium text-sm mb-1">Nenhum objetivo definido</h3>
                <p className="text-neutral-500 text-xs">Selecione objetivos da lista ao lado</p>
              </div>
            ) : (
              <div className="space-y-3">
                {/* Objectives stay in creation order (static), priority can still be changed */}
                {activeObjectives.map((obj, index) => (
                  <div
                    key={obj.id}
                    className="bg-white border border-neutral-200 p-4 rounded-xl hover:border-neutral-300 transition-all card-hover animate-fadeIn"
                    style={{ animationDelay: `${index * 0.05}s` }}
                  >
                    <div className="flex justify-between items-start mb-4">
                      <div className="flex items-start gap-3">
                        <div className="w-8 h-8 rounded-lg bg-neutral-100 flex items-center justify-center flex-shrink-0">
                          <svg className="w-4 h-4 text-neutral-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            {OBJECTIVE_ICONS[obj.objective]}
                          </svg>
                        </div>
                        <div>
                          <h3 className="text-sm font-medium text-neutral-900">{obj.objective}</h3>
                          <p className="text-xs text-neutral-500 mt-0.5">{OBJECTIVE_DESCRIPTIONS[obj.objective]}</p>
                        </div>
                      </div>
                      <span className="bg-neutral-900 text-white text-[10px] font-medium px-2 py-1 rounded">
                        {obj.priority}
                      </span>
                    </div>

                    <div className="pt-3 border-t border-neutral-100">
                      <div className="flex justify-between text-xs mb-2">
                        <span className="text-neutral-500">Prioridade</span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max="10"
                        step="1"
                        value={obj.priority}
                        onChange={(e) => updatePriority(obj.id, parseInt(e.target.value))}
                        className="w-full h-1.5 bg-neutral-200 rounded-lg appearance-none cursor-pointer accent-neutral-900"
                      />
                      <div className="flex justify-between text-[10px] text-neutral-400 mt-1.5 font-medium">
                        <span>Baixa</span>
                        <span>Alta</span>
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
