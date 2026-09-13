interface ChatHeaderProps {
  onResetMemory?: () => void;
  hasThread?: boolean;
}

const ChatHeader = ({ onResetMemory, hasThread }: ChatHeaderProps) => {
  return (
    <div className="glass-panel border-x-0 border-t-0 p-4 px-6 sticky top-0 z-30">
      <div className="w-full flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold text-gold-300 font-display tracking-wide">
            Rocky AI
          </h1>
          <p className="text-xs text-ink-400 mt-1 font-mono tracking-[0.15em]">
            Multimodal workspace for understanding and working with video.
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
          
        </div>
      </div>
    </div>
  );
};

export default ChatHeader;
