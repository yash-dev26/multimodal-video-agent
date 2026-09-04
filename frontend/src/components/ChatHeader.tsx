interface ChatHeaderProps {
  onResetMemory?: () => void;
  hasThread?: boolean;
}

const ChatHeader = ({ onResetMemory, hasThread }: ChatHeaderProps) => {
  return (
    <div className="glass-panel border-x-0 border-t-0 p-4 sticky top-0 z-30">
      <div className="max-w-4xl mx-auto flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gold-300 font-display tracking-wide">
            Rocky AI
          </h1>
          <p className="text-xs text-ink-400 mt-1 font-mono tracking-[0.15em]">
            BLIP-A INTERFACE
          </p>
        </div>
        <div className="flex items-center gap-4">
          {onResetMemory && hasThread && (
            <button
              onClick={onResetMemory}
              className="text-xs text-ink-400 hover:text-gold-300 font-mono transition-colors border gold-hairline hover:border-gold-500/50 px-3 py-1.5 rounded-md"
              title="Reset conversation memory"
            >
              Reset memory
            </button>
          )}
          <div className="flex items-center gap-2 text-[11px] font-mono text-ink-400 tracking-wide">
            <span className="w-1.5 h-1.5 rounded-full bg-gold-400 shadow-glow-gold-sm" />
            Synced
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatHeader;
