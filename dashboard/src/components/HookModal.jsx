import React, { useState } from 'react';
import { Loader2 } from 'lucide-react';
import RemotionPreview from './RemotionPreview';
import Modal from './ui/Modal';
import SegmentedControl from './ui/SegmentedControl';
import { useT } from '../contexts/LangContext';

const ENTRANCE_OPTIONS = [
    { value: 'spring', labelKey: 'hook.ent.spring' },
    { value: 'fade', labelKey: 'hook.ent.fade' },
    { value: 'slide-up', labelKey: 'hook.ent.slide' },
    { value: 'none', labelKey: 'hook.ent.none' },
];

// Must mirror hooks.py HOOK_STYLES.
const HOOK_STYLES = [
    { value: 'classic', labelKey: 'hook.style.classic', box: 'rgba(255,255,255,0.94)', text: '#000' },
    { value: 'dark', labelKey: 'hook.style.dark', box: 'rgba(18,18,20,0.92)', text: '#fff' },
    { value: 'yellow', labelKey: 'hook.style.yellow', box: 'rgba(255,214,0,0.96)', text: '#000' },
    { value: 'red', labelKey: 'hook.style.red', box: 'rgba(220,38,38,0.96)', text: '#fff' },
    { value: 'outline', labelKey: 'hook.style.outline', box: 'transparent', text: '#fff', outline: true },
    { value: 'outline_yellow', labelKey: 'hook.style.outline_yellow', box: 'transparent', text: '#FFD600', outline: true },
];

const POSITION_OPTIONS = [
    { value: 'top', labelKey: 'hook.pos.top' },
    { value: 'center', labelKey: 'hook.pos.center' },
    { value: 'bottom', labelKey: 'hook.pos.bottom' },
];

const SIZE_OPTIONS = [
    { value: 'S', labelKey: 'hook.size.s' },
    { value: 'M', labelKey: 'hook.size.m' },
    { value: 'L', labelKey: 'hook.size.l' },
];

// Last-used hook settings, restored on the next open (style always reset to
// classic otherwise, which users read as the picker being broken).
function loadHookPrefs() {
    try { return JSON.parse(localStorage.getItem('os_hook_prefs')) || {}; } catch { return {}; }
}

export default function HookModal({ isOpen, onClose, onGenerate, onRemove, isProcessing, videoUrl, initialText, durationInSeconds, existingSubtitles, hasCaptions, serverRender, burnedHook }) {
    const t = useT();
    const prefs = loadHookPrefs();
    const [text, setText] = useState(initialText || t('hook.default'));
    const [position, setPosition] = useState(prefs.position || 'top');
    const [size, setSize] = useState(prefs.size || 'M');
    const [style, setStyle] = useState(prefs.style || 'classic');
    const [entranceAnimation, setEntranceAnimation] = useState(prefs.entranceAnimation || 'spring');
    const [displayDuration, setDisplayDuration] = useState(5);

    if (!isOpen) return null;

    // Build hook config for Remotion preview
    const labelled = (opts) => opts.map((o) => ({ ...o, label: t(o.labelKey) }));
    const hookConfig = {
        text: text || t('hook.enter'),
        position,
        size,
        style,
        entranceAnimation,
        displayDurationSec: displayDuration,
    };

    const useRemotionPreview = !!videoUrl;

    // Fallback preview logic (same as original)
    const getPositionClass = () => {
        switch (position) {
            case 'center': return 'items-center justify-center';
            case 'bottom': return 'items-center justify-end pb-[20%]';
            case 'top': default: return 'items-center justify-start pt-[20%]';
        }
    };

    const getSizeStyle = () => {
        switch (size) {
            case 'S': return { fontSize: '14px', maxWidth: '80%' };
            case 'L': return { fontSize: '24px', maxWidth: '95%' };
            case 'M': default: return { fontSize: '18px', maxWidth: '90%' };
        }
    };

    return (
        <Modal isOpen={isOpen} onClose={onClose} size="lg" eyebrow={t('hook.eyebrow')} title={t('hook.title')}>
            <div className="flex flex-col md:flex-row gap-6">
                {/* Left: Preview */}
                <div className="flex-1 flex flex-col items-center justify-center bg-black rounded-card border border-rule overflow-hidden relative aspect-[9/16] max-h-[600px]">
                    {useRemotionPreview ? (
                        <RemotionPreview
                            videoUrl={videoUrl}
                            durationInSeconds={durationInSeconds || 30}
                            hook={hookConfig}
                            subtitles={existingSubtitles || null}
                        />
                    ) : (
                        <>
                            <video src={videoUrl} className="w-full h-full object-contain opacity-50" muted playsInline />
                            <div className={`absolute w-full px-8 text-center transition-all duration-300 pointer-events-none flex flex-col h-full ${getPositionClass()}`}>
                                <div
                                    className="text-black font-bold px-3 py-2 rounded-xl shadow-2xl text-center whitespace-pre-wrap transition-all duration-200"
                                    style={{
                                        ...getSizeStyle(),
                                        backgroundColor: 'rgba(255, 255, 255, 0.82)',
                                        fontFamily: 'Noto Serif, serif',
                                        boxShadow: '0 4px 15px rgba(0,0,0,0.5)',
                                        paddingTop: '10px',
                                        paddingBottom: '10px',
                                        paddingLeft: '12px',
                                        paddingRight: '12px'
                                    }}
                                >
                                    {text || t('hook.enter')}
                                </div>
                            </div>
                        </>
                    )}
                </div>

                {/* Right: Controls */}
                <div className="w-full md:w-80 flex flex-col">
                    <div className="space-y-5 flex-1 overflow-y-auto custom-scrollbar pr-1">
                        {/* Text Input */}
                        <div>
                            <p className="eyebrow mb-2">{t('hook.text')}</p>
                            <textarea
                                value={text}
                                onChange={(e) => setText(e.target.value)}
                                rows={4}
                                className="input-field resize-none font-serif"
                                style={{ fontFamily: 'Noto Serif, serif' }}
                                placeholder={t('hook.placeholder')}
                            />
                        </div>

                        {/* Style (new) */}
                        <div>
                            <p className="eyebrow mb-2">{t('hook.style')}</p>
                            <div className="grid grid-cols-3 gap-1.5">
                                {HOOK_STYLES.map((s) => (
                                    <button
                                        key={s.value}
                                        onClick={() => setStyle(s.value)}
                                        className={`px-1 py-2 rounded-input border text-xs transition-colors
                                            ${style === s.value ? 'border-[color:var(--color-accent)]' : 'border-rule2 hover:border-[color:var(--color-accent)]'}`}
                                        title={t(s.labelKey)}
                                    >
                                        <span
                                            className="block rounded px-1 py-1 font-bold"
                                            style={{
                                                backgroundColor: s.box,
                                                color: s.text,
                                                textShadow: s.outline ? '-1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000, 1px 1px 0 #000' : 'none',
                                            }}
                                        >Aa</span>
                                        <span className="block mt-1 text-muted">{t(s.labelKey)}</span>
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Position Control */}
                        <div>
                            <p className="eyebrow mb-2">{t('hook.position')}</p>
                            <SegmentedControl
                                options={labelled(POSITION_OPTIONS)}
                                value={position}
                                onChange={setPosition}
                                size="sm"
                            />
                            {position === 'bottom' && hasCaptions && (
                                <p className="text-[0.6875rem] text-warn mt-1.5 leading-relaxed">
                                    {t('hook.captionwarn')}
                                </p>
                            )}
                        </div>

                        {/* Size Control */}
                        <div>
                            <p className="eyebrow mb-2">{t('hook.size')}</p>
                            <SegmentedControl
                                options={labelled(SIZE_OPTIONS)}
                                value={size}
                                onChange={setSize}
                                size="sm"
                            />
                        </div>

                        {/* Entrance Animation (new) */}
                        <div className={serverRender ? 'opacity-50' : ''}>
                            <p className="eyebrow mb-2">{t('hook.entrance')}</p>
                            <SegmentedControl
                                options={labelled(ENTRANCE_OPTIONS)}
                                value={entranceAnimation}
                                onChange={setEntranceAnimation}
                                columns={2}
                                size="sm"
                            />
                            {serverRender && (
                                <p className="text-[0.6875rem] text-muted mt-1.5 leading-relaxed">
                                    {t('hook.serverwarn')}
                                </p>
                            )}
                        </div>

                        {/* Display Duration (new) */}
                        <div>
                            <div className="flex items-center justify-between mb-2">
                                <p className="eyebrow">{t('hook.duration')}</p>
                                <span className="readout">{displayDuration}S</span>
                            </div>
                            <input
                                type="range"
                                min="2"
                                max="15"
                                value={displayDuration}
                                onChange={(e) => setDisplayDuration(parseInt(e.target.value))}
                                className="w-full accent-[var(--color-accent)]"
                            />
                            <div className="flex justify-between">
                                <span className="readout">2S</span>
                                <span className="readout">15S</span>
                            </div>
                        </div>

                        {burnedHook && (
                            <div className="p-3 border border-rule rounded-input text-xs text-muted space-y-2">
                                <p>
                                    {t('hook.burned', { hook: burnedHook })}
                                </p>
                                {onRemove && (
                                    <button
                                        onClick={onRemove}
                                        disabled={isProcessing}
                                        className="text-warn underline underline-offset-2 hover:opacity-80 transition-opacity"
                                    >
                                        {t('hook.remove')}
                                    </button>
                                )}
                            </div>
                        )}

                        <div className="p-3 border border-rule rounded-input text-xs text-muted">
                            {t('hook.tip')}
                        </div>
                    </div>

                    <div className="flex gap-2 mt-5 shrink-0">
                        <button onClick={onClose} className="btn-ghost">
                            {t('common.cancel')}
                        </button>
                        <button
                            onClick={() => {
                                try {
                                    localStorage.setItem('os_hook_prefs', JSON.stringify({
                                        style, position, size, entranceAnimation,
                                    }));
                                } catch { /* ignore */ }
                                onGenerate({
                                    text, position, size, style,
                                    // Remotion data
                                    remotion: hookConfig,
                                });
                            }}
                            disabled={isProcessing || !text.trim()}
                            className="btn-primary flex-1"
                        >
                            {isProcessing && <Loader2 size={16} className="animate-spin text-brassink" />}
                            {isProcessing ? t('hook.generating') : t('hook.add')}
                        </button>
                    </div>
                </div>
            </div>
        </Modal>
    );
}
