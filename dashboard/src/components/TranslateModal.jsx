import React, { useState } from 'react';
import { Loader2, Languages, AlertCircle } from 'lucide-react';
import Modal from './ui/Modal';
import CreditNote from './CreditNote';
import { useLang } from '../contexts/LangContext';

// Language names come from the browser in the UI language ("Tây Ban Nha"),
// falling back to the English name when Intl.DisplayNames is unavailable.
function languageName(code, fallback, lang) {
    try {
        return new Intl.DisplayNames([lang], { type: 'language' }).of(code) || fallback;
    } catch {
        return fallback;
    }
}

const LANGUAGES = {
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "pl": "Polish",
    "hi": "Hindi",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ar": "Arabic",
    "ru": "Russian",
    "tr": "Turkish",
    "nl": "Dutch",
    "sv": "Swedish",
    "id": "Indonesian",
    "fil": "Filipino",
    "ms": "Malay",
    "vi": "Vietnamese",
    "th": "Thai",
    "uk": "Ukrainian",
    "el": "Greek",
    "cs": "Czech",
    "fi": "Finnish",
    "ro": "Romanian",
    "da": "Danish",
    "bg": "Bulgarian",
    "hr": "Croatian",
    "sk": "Slovak",
    "ta": "Tamil",
    "en": "English",
};

export default function TranslateModal({ isOpen, onClose, onTranslate, isProcessing, videoUrl, hasApiKey }) {
    const { t, lang } = useLang();
    const [targetLanguage, setTargetLanguage] = useState('es');

    if (!isOpen) return null;

    const handleSubmit = () => {
        console.log('[TranslateModal] handleSubmit called, targetLanguage:', targetLanguage);
        onTranslate({ targetLanguage });
    };

    return (
        <Modal
            isOpen={isOpen}
            onClose={isProcessing ? undefined : onClose}
            eyebrow={t('dub.eyebrow')}
            title={t('card.dub')}
            size="md"
            footer={
                <div className="space-y-2">
                <CreditNote cost="dubbing_per_minute" perMinute className="block text-xs text-muted text-right" />
                <div className="flex gap-3">
                    <button
                        onClick={onClose}
                        disabled={isProcessing}
                        className="btn-ghost flex-1"
                    >
                        {t('common.cancel')}
                    </button>
                    <button
                        onClick={handleSubmit}
                        disabled={isProcessing || !hasApiKey}
                        className="btn-primary flex-1"
                    >
                        {isProcessing ? (
                            <>
                                <Loader2 size={16} className="animate-spin" />
                                {t('dub.dubbing')}
                            </>
                        ) : (
                            <>
                                <Languages size={16} />
                                {t('dub.submit')}
                            </>
                        )}
                    </button>
                </div>
                </div>
            }
        >
            <div className="flex items-center gap-3 mb-5">
                <div className="w-10 h-10 rounded-input bg-paper3 flex items-center justify-center shrink-0">
                    <Languages size={18} className="text-brass" />
                </div>
                <p className="text-xs text-muted">{t('dub.by')}</p>
            </div>

            {!hasApiKey && (
                <div className="mb-4 flex items-start gap-2">
                    <span className="badge-warn shrink-0"><AlertCircle size={12} /> {t('dub.keymissing')}</span>
                    <p className="text-sm text-muted">{t('dub.configure')}</p>
                </div>
            )}

            {/* Preview */}
            <div className="mb-5 rounded-card overflow-hidden bg-black aspect-video">
                <video
                    src={videoUrl}
                    className="w-full h-full object-contain"
                    muted
                    playsInline
                />
            </div>

            {/* Language Selection */}
            <div className="mb-5">
                <label className="eyebrow block mb-2">
                    {t('dub.target')}
                </label>
                <select
                    value={targetLanguage}
                    onChange={(e) => setTargetLanguage(e.target.value)}
                    className="input-field appearance-none cursor-pointer"
                    disabled={isProcessing}
                >
                    {Object.entries(LANGUAGES).map(([code, name]) => [code, languageName(code, name, lang)]).sort((a, b) => a[1].localeCompare(b[1], lang)).map(([code, name]) => (
                        <option key={code} value={code}>
                            {name}
                        </option>
                    ))}
                </select>
            </div>

            {/* Info */}
            <p className="text-xs text-muted leading-relaxed mb-2">
                {t('dub.info')}
            </p>

            {/* AI Act art. 50: we mark the file, the person publishing it is the
                one who owes the audience the disclosure. Saying so here is the
                only place they will read it. */}
            <p className="text-xs text-muted leading-relaxed mb-2">
                {t('dub.ai')}
            </p>

            {/* Processing State */}
            {isProcessing && (
                <div className="mt-4 p-3 bg-paper3 rounded-input">
                    <div className="flex items-center gap-3">
                        <Loader2 size={18} className="text-brass animate-spin" />
                        <div>
                            <p className="text-sm text-ink font-medium lowercase">{t('dub.audio')}</p>
                            <p className="text-xs text-muted lowercase">{t('dub.wait')}</p>
                        </div>
                    </div>
                </div>
            )}
        </Modal>
    );
}
