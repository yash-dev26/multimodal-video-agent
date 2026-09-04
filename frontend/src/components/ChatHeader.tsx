interface ChatHeaderProps {
  onResetMemory?: () => void;
  hasThread?: boolean;
}

const ChatHeader = ({ onResetMemory, hasThread }: ChatHeaderProps) => {
  return (
    <div className="border-b border-[#2e231c] bg-[#120f0d] p-4">
      <div className="max-w-4xl mx-auto flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[#c59f84] font-mono">ROCKY AI</h1>
          <p className="text-sm text-stone-400 mt-1 font-mono">BLIP-A INTERFACE</p>
        </div>
        <div className="flex items-center gap-3">
          {onResetMemory && hasThread && (
            <button
              onClick={onResetMemory}
              className="text-xs text-stone-500 hover:text-[#c59f84] font-mono transition-colors border border-[#2e231c] hover:border-[#b48263] px-2 py-1 rounded"
              title="Reset conversation memory"
            >
              RESET MEMORY
            </button>
          )}
          <div className="w-3 h-3 bg-[#b48263] rounded-full" />
        </div>
      </div>
    </div>
  );
};

export default ChatHeader;
