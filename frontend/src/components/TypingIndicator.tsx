const TypingIndicator = () => {
  return (
    <div className="flex justify-start animate-fade-in font-mono">
      <div className="max-w-[70%] p-4 rounded-lg glass-panel">
        <div className="text-xs mb-2 text-gold-300 font-semibold tracking-wide">ROCKY</div>
        <div className="flex items-center gap-3">
          <div className="w-24 h-[3px] rounded-full bg-obsidian-700 overflow-hidden">
            <div className="h-full w-full bg-gradient-to-r from-transparent via-gold-400 to-transparent animate-shimmer bg-[length:200%_100%]" />
          </div>
          <span className="text-sm text-ink-400 animate-breathe">Rocky is thinking…</span>
        </div>
      </div>
    </div>
  );
};

export default TypingIndicator;
