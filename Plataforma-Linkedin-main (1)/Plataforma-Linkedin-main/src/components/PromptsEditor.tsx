'use client';

import { useState, useEffect } from 'react';

interface Prompt {
    type: string;
    name: string;
    description: string;
    variables?: string[];
    default_content: string;
    custom_content: string | null;
    is_customized: boolean;
    is_active: boolean;
}

interface PromptsEditorProps {
    enabled: boolean;
}

export default function PromptsEditor({ enabled }: PromptsEditorProps) {
    const [prompts, setPrompts] = useState<Prompt[]>([]);
    const [loading, setLoading] = useState(false);
    const [editingPrompt, setEditingPrompt] = useState<Prompt | null>(null);
    const [editContent, setEditContent] = useState('');
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        if (enabled) {
            loadPrompts();
        }
    }, [enabled]);

    const loadPrompts = async () => {
        setLoading(true);
        try {
            const response = await fetch('/api/prompts');
            const data = await response.json();
            if (data.success) {
                setPrompts(data.prompts || []);
            }
        } catch (error) {
            console.error('Error loading prompts:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleEdit = (prompt: Prompt) => {
        setEditingPrompt(prompt);
        setEditContent(prompt.custom_content || prompt.default_content);
    };

    const handleSave = async () => {
        if (!editingPrompt) return;

        setSaving(true);
        try {
            const response = await fetch('/api/prompts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prompt_type: editingPrompt.type,
                    prompt_content: editContent,
                }),
            });

            const data = await response.json();
            if (data.success) {
                // Update local state
                setPrompts(prev => prev.map(p =>
                    p.type === editingPrompt.type
                        ? { ...p, custom_content: editContent, is_customized: true }
                        : p
                ));
                setEditingPrompt(null);
                alert('✅ Prompt guardado com sucesso!');
            } else {
                alert(data.error || 'Erro ao guardar prompt');
            }
        } catch (error) {
            console.error('Error saving prompt:', error);
            alert('Erro ao guardar prompt');
        } finally {
            setSaving(false);
        }
    };

    const handleReset = async (promptType: string) => {
        if (!confirm('Tem a certeza que deseja repor este prompt para o padrão?')) return;

        try {
            const response = await fetch(`/api/prompts?type=${promptType}`, {
                method: 'DELETE',
            });

            const data = await response.json();
            if (data.success) {
                setPrompts(prev => prev.map(p =>
                    p.type === promptType
                        ? { ...p, custom_content: null, is_customized: false }
                        : p
                ));
                alert('✅ Prompt reposto para o padrão!');
            }
        } catch (error) {
            console.error('Error resetting prompt:', error);
        }
    };

    if (!enabled) return null;

    if (loading) {
        return (
            <div className="px-6 py-5 flex items-center justify-center">
                <div className="w-5 h-5 border-2 border-neutral-300 border-t-neutral-600 rounded-full animate-spin"></div>
                <span className="ml-2 text-sm text-neutral-500">A carregar prompts...</span>
            </div>
        );
    }

    return (
        <>
            <div className="px-6 py-5">
                <h3 className="text-sm font-medium text-neutral-900 mb-4">
                    Prompts Disponíveis
                </h3>
                <p className="text-xs text-neutral-500 mb-4">
                    Personaliza os prompts de IA para adaptar o conteúdo gerado ao teu estilo.
                </p>

                <div className="space-y-3">
                    {prompts.map((prompt) => (
                        <div
                            key={prompt.type}
                            className="bg-neutral-50 rounded-xl p-4 flex items-center justify-between"
                        >
                            <div className="flex-1">
                                <div className="flex items-center gap-2">
                                    <h4 className="text-sm font-medium text-neutral-900">
                                        {prompt.name}
                                    </h4>
                                    {prompt.is_customized && (
                                        <span className="px-2 py-0.5 text-[10px] font-medium bg-violet-100 text-violet-700 rounded-full">
                                            Personalizado
                                        </span>
                                    )}
                                </div>
                                <p className="text-xs text-neutral-500 mt-1">
                                    {prompt.description}
                                </p>
                            </div>
                            <div className="flex items-center gap-2">
                                {prompt.is_customized && (
                                    <button
                                        onClick={() => handleReset(prompt.type)}
                                        className="px-3 py-1.5 text-xs font-medium text-neutral-600 bg-white border border-neutral-200 rounded-lg hover:bg-neutral-50 transition-colors"
                                    >
                                        Repor
                                    </button>
                                )}
                                <button
                                    onClick={() => handleEdit(prompt)}
                                    className="px-3 py-1.5 text-xs font-medium text-white bg-neutral-900 rounded-lg hover:bg-neutral-800 transition-colors"
                                >
                                    Editar
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {/* Edit Modal */}
            {editingPrompt && (
                <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
                    <div className="bg-white rounded-2xl w-full max-w-3xl max-h-[90vh] overflow-hidden flex flex-col">
                        {/* Modal Header */}
                        <div className="px-6 py-4 border-b border-neutral-200 flex items-center justify-between">
                            <div>
                                <h3 className="text-lg font-semibold text-neutral-900">
                                    Editar: {editingPrompt.name}
                                </h3>
                                <p className="text-sm text-neutral-500 mt-0.5">
                                    {editingPrompt.description}
                                </p>
                            </div>
                            <button
                                onClick={() => setEditingPrompt(null)}
                                className="w-8 h-8 flex items-center justify-center text-neutral-400 hover:text-neutral-600 rounded-lg hover:bg-neutral-100"
                            >
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>

                        {/* Variables Info */}
                        {editingPrompt.variables && editingPrompt.variables.length > 0 && (
                            <div className="px-6 py-3 bg-blue-50 border-b border-blue-100">
                                <p className="text-xs text-blue-700">
                                    <strong>Variáveis disponíveis:</strong>{' '}
                                    {editingPrompt.variables.map(v => `{{${v}}}`).join(', ')}
                                </p>
                            </div>
                        )}

                        {/* Editor */}
                        <div className="flex-1 overflow-auto p-6">
                            <textarea
                                value={editContent}
                                onChange={(e) => setEditContent(e.target.value)}
                                className="w-full h-96 p-4 text-sm font-mono bg-neutral-50 border border-neutral-200 rounded-xl focus:border-neutral-400 focus:ring-2 focus:ring-neutral-100 outline-none resize-none"
                                placeholder="Escreve o teu prompt personalizado aqui..."
                            />
                        </div>

                        {/* Modal Footer */}
                        <div className="px-6 py-4 border-t border-neutral-200 flex items-center justify-between">
                            <button
                                onClick={() => setEditContent(editingPrompt.default_content)}
                                className="text-sm text-neutral-500 hover:text-neutral-700"
                            >
                                Repor prompt padrão
                            </button>
                            <div className="flex items-center gap-3">
                                <button
                                    onClick={() => setEditingPrompt(null)}
                                    className="px-4 py-2 text-sm font-medium text-neutral-600 bg-white border border-neutral-200 rounded-lg hover:bg-neutral-50 transition-colors"
                                >
                                    Cancelar
                                </button>
                                <button
                                    onClick={handleSave}
                                    disabled={saving}
                                    className="px-4 py-2 text-sm font-medium text-white bg-neutral-900 rounded-lg hover:bg-neutral-800 disabled:bg-neutral-300 transition-colors flex items-center gap-2"
                                >
                                    {saving ? (
                                        <>
                                            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                                            A guardar...
                                        </>
                                    ) : (
                                        'Guardar Alterações'
                                    )}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
